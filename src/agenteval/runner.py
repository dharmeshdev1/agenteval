"""Run one agent on one task in a fresh sandboxed workspace, then judge the outcome.

The outcome depends only on the final state of the workspace, checked by a verifier the
agent could never read. Nothing the agent says about its own success is trusted.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from agenteval.agents import Agent
from agenteval.sandbox import Sandbox
from agenteval.task import Task, hash_file
from agenteval.tools import (
    Action,
    Bash,
    Finish,
    ListDir,
    Observation,
    ReadFile,
    Step,
    ToolBox,
    WriteFile,
    clip,
)

PASSED, FAILED, TAMPERED, INFRA_ERROR = "passed", "failed", "tampered", "infra_error"
FINISH, STEP_LIMIT, TIME_LIMIT, AGENT_ERROR = "finish", "step_limit", "time_limit", "agent_error"
VERIFIER_DIR_NAME = ".verifier"
# Never carried into the verification snapshot: the harness's scratch directories, and any
# directory the agent made that looks like the verifier's, so planted files cannot survive.
IGNORED_FOR_SNAPSHOT = (".home", ".tmp", VERIFIER_DIR_NAME)
SHARED_DIR_NAME = "_shared"


@dataclass
class Episode:
    task_id: str
    agent: str
    trial: int
    status: str
    terminated_by: str
    steps: list[Step] = field(default_factory=list)
    tampered: list[str] = field(default_factory=list)
    verifier_exit: int | None = None
    verifier_output: str = ""
    isolation: str = "unknown"
    duration: float = 0.0
    error: str = ""
    usage: dict | None = None  # model token counts, when the agent reports them

    @property
    def passed(self) -> bool:
        return self.status == PASSED

    def to_dict(self) -> dict:
        def action(a: Action) -> dict:
            kind = type(a).__name__
            body = {k: v for k, v in vars(a).items()}
            return {"type": kind, **body}

        return {
            "task_id": self.task_id, "agent": self.agent, "trial": self.trial,
            "status": self.status, "passed": self.passed, "terminated_by": self.terminated_by,
            "num_steps": len(self.steps), "duration": round(self.duration, 3),
            "tampered": self.tampered, "isolation": self.isolation, "error": self.error,
            "usage": self.usage,
            "verifier": {"exit": self.verifier_exit, "output": self.verifier_output},
            "steps": [
                {"action": action(s.action), "observation": vars(s.observation)}
                for s in self.steps
            ],
        }


def _copy_tree(src: Path, dst: Path, skip: tuple[str, ...] = ()) -> None:
    def ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n in skip]

    shutil.copytree(src, dst, symlinks=True, ignore=ignore, dirs_exist_ok=True)


def prepare_workspace(task: Task, dest: Path, sandbox: Sandbox) -> dict[str, str | None]:
    """Copy the task's files in, run its setup script, and fingerprint protected files."""
    _copy_tree(task.workspace_dir, dest)
    if task.setup_script.is_file():
        res = sandbox.shell(task.setup_script.read_text(), dest, timeout=60)
        if not res.ok:
            raise RuntimeError(f"setup failed (exit {res.returncode}): {res.stderr or res.stdout}")
    return {rel: hash_file(dest / rel) for rel in task.protected}


def verify(task: Task, workspace: Path, sandbox: Sandbox, work: Path) -> tuple[int | None, str]:
    """Judge a snapshot of the final workspace with the hidden verifier."""
    snapshot = work / "verify"
    _copy_tree(workspace, snapshot, skip=IGNORED_FOR_SNAPSHOT)
    _copy_tree(task.verifier_dir, snapshot / VERIFIER_DIR_NAME)
    shared = task.root.parent / SHARED_DIR_NAME
    if shared.is_dir():
        _copy_tree(shared, snapshot / VERIFIER_DIR_NAME / SHARED_DIR_NAME)
    res = sandbox.run(
        ["/bin/sh", f"{VERIFIER_DIR_NAME}/verify.sh"], snapshot, timeout=task.verify_timeout
    )
    output = res.stdout + (f"\n[stderr]\n{res.stderr}" if res.stderr else "")
    if res.timed_out:
        output += f"\n[verifier timed out after {task.verify_timeout:.0f}s]"
    return (None if res.returncode is None else res.returncode), clip(output.strip(), 4000)


def run_episode(
    task: Task, agent: Agent, sandbox: Sandbox, trial: int = 0, keep_dir: Path | None = None
) -> Episode:
    started = time.monotonic()
    work = Path(tempfile.mkdtemp(prefix=f"agenteval-{task.id}-")).resolve()
    episode = Episode(
        task.id, agent.name, trial, INFRA_ERROR, AGENT_ERROR, isolation=sandbox.isolation.level
    )
    try:
        workspace = work / "ws"
        try:
            hashes = prepare_workspace(task, workspace, sandbox)
        except Exception as exc:
            episode.error = f"could not prepare workspace: {exc}"
            return episode

        tools = ToolBox(workspace, sandbox, task.command_timeout)
        episode.terminated_by = _interact(task, agent, tools, episode, started)
        episode.usage = getattr(agent, "usage", None)

        episode.tampered = [
            rel for rel, digest in hashes.items() if hash_file(workspace / rel) != digest
        ]
        code, output = verify(task, workspace, sandbox, work)
        episode.verifier_exit, episode.verifier_output = code, output
        if code is None:
            episode.status, episode.error = INFRA_ERROR, "the verifier could not be started"
        elif episode.tampered:
            episode.status = TAMPERED
        else:
            episode.status = PASSED if code == 0 else FAILED
        return episode
    except Exception as exc:  # the harness failing is never reported as the agent failing
        episode.status, episode.error = INFRA_ERROR, f"{type(exc).__name__}: {exc}"
        return episode
    finally:
        episode.duration = time.monotonic() - started
        if keep_dir is not None:
            keep_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(work), str(keep_dir / f"{task.id}-{agent.name}-{trial}"))
        else:
            shutil.rmtree(work, ignore_errors=True)


def _interact(task: Task, agent: Agent, tools: ToolBox, episode: Episode, started: float) -> str:
    try:
        agent.start(task.instruction)
    except Exception as exc:
        episode.error = f"agent failed to start: {type(exc).__name__}: {exc}"
        return AGENT_ERROR
    for _ in range(task.max_steps):
        remaining = task.episode_timeout - (time.monotonic() - started)
        if remaining <= 0:
            return TIME_LIMIT
        try:
            action = agent.act(list(episode.steps))
        except Exception as exc:
            episode.error = f"agent raised {type(exc).__name__}: {exc}"
            return AGENT_ERROR
        if isinstance(action, Finish):
            episode.steps.append(Step(action, Observation("finished")))
            return FINISH
        if not isinstance(action, (Bash, ReadFile, WriteFile, ListDir)):
            reason = getattr(action, "reason", None) or repr(action)
            obs = Observation(f"invalid action: {reason}", ok=False)
        else:
            obs = tools.execute(action, time_left=remaining)
        episode.steps.append(Step(action, obs))
    return STEP_LIMIT
