"""The action space an agent has, and the tool layer that executes it.

Shell commands run inside the sandbox. File tools run in the harness, so every path is
resolved and checked against the workspace first. That includes symlinks, which would
otherwise let ``read_file`` follow a link the agent created out of the workspace.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agenteval.sandbox import Limits, Sandbox

HIDDEN_DIRS = {".home", ".tmp"}


@dataclass(frozen=True)
class Bash:
    command: str


@dataclass(frozen=True)
class ReadFile:
    path: str


@dataclass(frozen=True)
class WriteFile:
    path: str
    content: str


@dataclass(frozen=True)
class ListDir:
    path: str = "."


@dataclass(frozen=True)
class Finish:
    message: str = ""


Action = Bash | ReadFile | WriteFile | ListDir | Finish


@dataclass(frozen=True)
class Observation:
    text: str
    ok: bool = True
    exit_code: int | None = None
    timed_out: bool = False
    duration: float = 0.0


@dataclass(frozen=True)
class Step:
    action: Action
    observation: Observation


class PathEscape(ValueError):
    """A path resolves to somewhere outside the workspace."""


def clip(text: str, limit: int) -> str:
    """Keep the start and end of long text, which is where errors and results usually are."""
    if len(text) <= limit:
        return text
    head, tail = int(limit * 0.6), int(limit * 0.4)
    omitted = len(text) - head - tail
    return f"{text[:head]}\n[... {omitted} characters omitted ...]\n{text[-tail:]}"


def safe_path(workspace: Path, relative: str) -> Path:
    root = workspace.resolve()
    candidate = Path(relative)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise PathEscape(f"path {relative!r} is outside the workspace")
    return resolved


class ToolBox:
    def __init__(
        self,
        workspace: Path,
        sandbox: Sandbox,
        command_timeout: float = 30.0,
        limits: Limits | None = None,
        max_observation_chars: int = 8000,
        max_file_bytes: int = 200_000,
    ) -> None:
        self.workspace = workspace.resolve()
        self.sandbox = sandbox
        self.command_timeout = command_timeout
        self.limits = limits
        self.max_chars = max_observation_chars
        self.max_file_bytes = max_file_bytes

    def execute(self, action: Action, time_left: float | None = None) -> Observation:
        """Run one action. Never raises: failures become an ``Observation`` the agent can read."""
        try:
            if isinstance(action, Bash):
                return self._bash(action.command, time_left)
            if isinstance(action, ReadFile):
                return self._read(action.path)
            if isinstance(action, WriteFile):
                return self._write(action.path, action.content)
            if isinstance(action, ListDir):
                return self._list(action.path)
        except PathEscape as exc:
            return Observation(str(exc), ok=False)
        except OSError as exc:
            return Observation(f"{type(exc).__name__}: {exc}", ok=False)
        return Observation(f"unsupported action {action!r}", ok=False)

    def _bash(self, command: str, time_left: float | None) -> Observation:
        limit = self.command_timeout
        timeout = limit if time_left is None else min(limit, time_left)
        res = self.sandbox.shell(
            command, self.workspace, timeout=max(timeout, 0.1), limits=self.limits
        )
        parts = []
        if res.stdout:
            parts.append(res.stdout)
        if res.stderr:
            parts.append(f"[stderr]\n{res.stderr}")
        if res.timed_out:
            parts.append(f"[command timed out after {timeout:.0f}s and was killed]")
        if res.output_truncated:
            parts.append("[output exceeded the size limit and the command was stopped]")
        parts.append(f"[exit code {res.returncode}]")
        return Observation(
            clip("\n".join(parts), self.max_chars), ok=res.ok, exit_code=res.returncode,
            timed_out=res.timed_out, duration=res.duration,
        )

    def _read(self, relative: str) -> Observation:
        path = safe_path(self.workspace, relative)
        if not path.is_file():
            return Observation(f"{relative}: no such file", ok=False)
        data = path.read_bytes()[: self.max_file_bytes + 1]
        if b"\0" in data[:4096]:
            return Observation(f"{relative}: binary file, not shown", ok=False)
        text = data[: self.max_file_bytes].decode("utf-8", errors="replace")
        note = "\n[file truncated]" if len(data) > self.max_file_bytes else ""
        return Observation(clip(text, self.max_chars) + note)

    def _write(self, relative: str, content: str) -> Observation:
        path = safe_path(self.workspace, relative)
        if path == self.workspace or path.is_dir():
            return Observation(f"{relative}: is a directory", ok=False)
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_file_bytes:
            return Observation(f"content is {len(encoded)} bytes, over the limit", ok=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)
        return Observation(f"wrote {len(encoded)} bytes to {relative}")

    def _list(self, relative: str) -> Observation:
        path = safe_path(self.workspace, relative)
        if not path.is_dir():
            return Observation(f"{relative}: not a directory", ok=False)
        entries = sorted(
            f"{p.name}/" if p.is_dir() else p.name
            for p in path.iterdir()
            if not (path == self.workspace and p.name in HIDDEN_DIRS)
        )
        return Observation("\n".join(entries) if entries else "(empty)")
