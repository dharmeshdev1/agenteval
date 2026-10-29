"""Command execution with resource limits, output caps, process-tree cleanup and, where the
platform allows, real isolation.

Three backends share one interface:

* ``SeatbeltSandbox`` (macOS): the kernel denies network access, writes outside the
  workspace, and reads of listed directories. This is real isolation.
* ``ProcessSandbox``: a scrubbed environment, resource limits, a timeout and process-group
  cleanup, but **no** filesystem or network confinement. It exists so the harness runs
  anywhere, and it refuses to be used for untrusted code unless asked explicitly.

Each backend reports what it actually enforces in ``isolation`` so a result file records
how much a run was protected, instead of implying more than was true.
"""

from __future__ import annotations

import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Runs inside the sandbox, before the real command. It applies resource limits and then
# replaces itself with the command, so nothing is left running as a parent. It is passed with
# -c so no file inside the (possibly unreadable) harness directory is needed.
_TRAMPOLINE = r"""
import json, os, resource, sys
limits = json.loads(sys.argv[1])
def cap(which, value):
    try:
        soft, hard = resource.getrlimit(which)
        if hard != resource.RLIM_INFINITY and value > hard:
            value = hard
        resource.setrlimit(which, (value, value if hard == resource.RLIM_INFINITY else hard))
    except (ValueError, OSError):
        pass
cap(resource.RLIMIT_CORE, 0)
cap(resource.RLIMIT_CPU, limits["cpu_seconds"])
cap(resource.RLIMIT_FSIZE, limits["max_file_bytes"])
cap(resource.RLIMIT_NOFILE, limits["max_open_files"])
if sys.platform.startswith("linux"):
    cap(resource.RLIMIT_AS, limits["max_memory_bytes"])
os.execvp(sys.argv[2], sys.argv[2:])
"""

TRAMPOLINE_PYTHON = "/usr/bin/python3"
# On macOS /usr/bin/make, git and friends are shims that try to write a cache outside the
# workspace. The real binaries in the Command Line Tools directory are used first when present.
SAFE_PATH = (
    "/Library/Developer/CommandLineTools/usr/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
)


@dataclass(frozen=True)
class Limits:
    cpu_seconds: int = 60
    max_file_bytes: int = 64 * 1024 * 1024
    max_open_files: int = 256
    max_memory_bytes: int = 2 * 1024**3  # enforced on Linux only; macOS ignores RLIMIT_AS


@dataclass(frozen=True)
class ExecResult:
    returncode: int | None  # negative means killed by that signal; None if it never started
    stdout: str
    stderr: str
    timed_out: bool = False
    output_truncated: bool = False
    duration: float = 0.0

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


@dataclass(frozen=True)
class Isolation:
    """What a backend genuinely enforces."""

    network_blocked: bool
    writes_confined_to_workspace: bool
    hidden_paths_unreadable: bool
    env_scrubbed: bool = True
    notes: str = ""

    @property
    def level(self) -> str:
        confined = (
            self.network_blocked
            and self.writes_confined_to_workspace
            and self.hidden_paths_unreadable
        )
        return "isolated" if confined else "unconfined"


def clean_env(workspace: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    """A minimal environment. Nothing from the parent process leaks in, secrets included."""
    env = {
        "PATH": SAFE_PATH,
        "HOME": str(workspace / ".home"),
        "TMPDIR": str(workspace / ".tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "agent",
        "GIT_AUTHOR_EMAIL": "agent@example.invalid",
        "GIT_COMMITTER_NAME": "agent",
        "GIT_COMMITTER_EMAIL": "agent@example.invalid",
    }
    env.update(extra or {})
    return env


def run_process(
    argv: list[str], cwd: Path, env: dict[str, str], timeout: float, max_output: int
) -> ExecResult:
    """Run ``argv`` in its own process group and always clean the whole group up.

    The group is killed on timeout, on exceeding the output cap, and after a normal exit,
    so a command that leaves a background process behind cannot outlive its step.
    """
    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True,
        )
    except OSError as exc:
        return ExecResult(None, "", f"failed to start: {exc}", duration=time.monotonic() - start)

    def kill_group() -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    out_fd, err_fd = proc.stdout.fileno(), proc.stderr.fileno()
    chunks: dict[int, list[bytes]] = {out_fd: [], err_fd: []}
    sizes = {out_fd: 0, err_fd: 0}
    selector = selectors.DefaultSelector()
    for stream in (proc.stdout, proc.stderr):
        selector.register(stream, selectors.EVENT_READ)

    deadline = start + timeout
    timed_out = truncated = False
    open_streams = 2
    while open_streams:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        exited = proc.poll() is not None
        for key, _ in selector.select(timeout=0.0 if exited else min(remaining, 0.05)):
            fd = key.fileobj.fileno()
            data = os.read(fd, 65536)
            if not data:
                selector.unregister(key.fileobj)
                open_streams -= 1
                continue
            room = max_output - sizes[fd]
            if room > 0:
                chunks[fd].append(data[:room])
            sizes[fd] += len(data)
            if sizes[fd] > max_output:
                truncated = True
        if truncated or (exited and not selector.select(timeout=0.0)):
            break
    kill_group()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        kill_group()
        proc.wait()
    for stream in (proc.stdout, proc.stderr):
        stream.close()

    def text(fd: int) -> str:
        return b"".join(chunks[fd]).decode("utf-8", errors="replace")

    return ExecResult(
        returncode=proc.returncode,
        stdout=text(out_fd),
        stderr=text(err_fd),
        timed_out=timed_out,
        output_truncated=truncated,
        duration=time.monotonic() - start,
    )


class Sandbox:
    name = "base"
    isolation = Isolation(False, False, False)

    def command(self, argv: list[str], workspace: Path, limits: Limits) -> list[str]:
        raise NotImplementedError

    def run(
        self,
        argv: list[str],
        workspace: Path,
        timeout: float = 30.0,
        limits: Limits | None = None,
        max_output: int = 64 * 1024,
        extra_env: dict[str, str] | None = None,
    ) -> ExecResult:
        workspace = workspace.resolve()
        for sub in (".home", ".tmp"):
            (workspace / sub).mkdir(exist_ok=True)
        limits = limits or Limits()
        wrapped = self.command(argv, workspace, limits)
        return run_process(wrapped, workspace, clean_env(workspace, extra_env), timeout, max_output)

    def shell(self, command: str, workspace: Path, **kw) -> ExecResult:
        return self.run(["/bin/sh", "-c", command], workspace, **kw)

    @staticmethod
    def _limited(argv: list[str], limits: Limits) -> list[str]:
        payload = json.dumps({
            "cpu_seconds": limits.cpu_seconds,
            "max_file_bytes": limits.max_file_bytes,
            "max_open_files": limits.max_open_files,
            "max_memory_bytes": limits.max_memory_bytes,
        })
        return [TRAMPOLINE_PYTHON, "-c", _TRAMPOLINE, payload, *argv]


class ProcessSandbox(Sandbox):
    """Limits and cleanup only. Not isolation. Use for trusted code."""

    name = "process"
    isolation = Isolation(
        network_blocked=False,
        writes_confined_to_workspace=False,
        hidden_paths_unreadable=False,
        notes="resource limits, scrubbed environment and process-group cleanup only",
    )

    def command(self, argv: list[str], workspace: Path, limits: Limits) -> list[str]:
        return self._limited(argv, limits)


@dataclass
class SeatbeltSandbox(Sandbox):
    """macOS ``sandbox-exec``: kernel-enforced confinement.

    Writes are allowed only inside the workspace, the network is denied, and each path in
    ``hidden`` (task definitions, verifiers, results) plus every user home directory is
    unreadable. ``sandbox-exec`` is deprecated by Apple but remains functional.
    """

    hidden: list[Path] = field(default_factory=list)
    name = "seatbelt"
    isolation = Isolation(
        network_blocked=True,
        writes_confined_to_workspace=True,
        hidden_paths_unreadable=True,
        notes="macOS sandbox-exec profile; memory is not limited on macOS",
    )

    @staticmethod
    def available() -> bool:
        return sys.platform == "darwin" and shutil.which("sandbox-exec") is not None

    def profile(self, workspace: Path) -> str:
        def sub(path: Path) -> str:
            return f'(subpath "{str(path.resolve()).replace(chr(34), "")}")'

        lines = [
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny file-write*)",
            f"(allow file-write* {sub(workspace)} (literal \"/dev/null\"))",
            '(deny file-read* (subpath "/Users"))',
            f"(allow file-read* {sub(workspace)})",
        ]
        lines += [f"(deny file-read* {sub(p)})" for p in self.hidden]
        return "\n".join(lines)

    def command(self, argv: list[str], workspace: Path, limits: Limits) -> list[str]:
        return ["sandbox-exec", "-p", self.profile(workspace), *self._limited(argv, limits)]


def choose_sandbox(hidden: list[Path], allow_unconfined: bool = False) -> Sandbox:
    """Best available backend. Falls back to an unconfined one only when explicitly allowed."""
    if SeatbeltSandbox.available():
        return SeatbeltSandbox(hidden=hidden)
    if allow_unconfined:
        return ProcessSandbox()
    raise RuntimeError(
        "no isolating sandbox is available on this machine; pass allow_unconfined=True "
        "(--allow-unconfined) to run trusted tasks without isolation"
    )
