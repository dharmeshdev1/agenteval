"""Check that a task is a fair, solvable and non-trivial test before anyone trusts it.

A broken task silently corrupts every result, so these checks run in CI against every task.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from agenteval.agents import NullAgent, OracleAgent, ScriptedAgent
from agenteval.runner import (
    FAILED,
    INFRA_ERROR,
    PASSED,
    prepare_workspace,
    run_episode,
)
from agenteval.sandbox import Sandbox
from agenteval.task import Task, hash_file
from agenteval.tools import Bash

# A python command starts a line or follows an operator, so the word inside an echo message
# or a comment is not mistaken for an invocation.
PYTHON_CALL = re.compile(r"(?:^|[;&|(`]|\$\()\s*(?:env\s+)?python3?\b(?P<rest>[^\n|;&]*)", re.M)
TEST_METHOD = re.compile(r"def (test_\w+)")


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""
    warning: bool = False  # a failed warning is reported but does not fail the task


def _files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]


def check_instruction(task: Task) -> Check:
    words = len(task.instruction.split())
    return Check("instruction", words >= 8, f"{words} words" if words < 8 else "")


def check_verifier_uses_isolated_python(task: Task) -> Check:
    """Every python invocation in a verifier script must pass -I (isolated mode)."""
    bad = []
    for script in task.verifier_dir.rglob("*.sh"):
        code = "\n".join(
            line for line in script.read_text().splitlines() if not line.lstrip().startswith("#")
        )
        for match in PYTHON_CALL.finditer(code):
            if not re.search(r"(^|\s)-\w*I\w*(\s|$)", match.group("rest")):
                bad.append(f"{script.name}: {match.group(0).strip()}")
    return Check("verifier-isolated-python", not bad, "; ".join(bad))


def check_no_leak(task: Task, sandbox: Sandbox, scratch: Path) -> Check:
    """Nothing the verifier relies on may be visible in the agent's workspace."""
    workspace = scratch / "leak-ws"
    try:
        prepare_workspace(task, workspace, sandbox)
    except Exception as exc:
        return Check("no-leak", False, f"workspace could not be prepared: {exc}")
    hidden = {hash_file(p) for p in _files(task.verifier_dir) + _files(task.oracle_dir)}
    leaked = [
        str(p.relative_to(workspace)) for p in _files(workspace) if hash_file(p) in hidden
    ]
    return Check("no-leak", not leaked, f"identical to a hidden file: {leaked}" if leaked else "")


def check_shared_test_names(task: Task, scratch: Path) -> Check:
    """Warn when the visible tests reuse a hidden test's name, which hints at what is hidden."""
    workspace = scratch / "leak-ws"
    if not workspace.exists():
        return Check("distinct-test-names", True, warning=True)
    visible = {m for p in _files(workspace) if p.suffix == ".py"
               for m in TEST_METHOD.findall(p.read_text(errors="replace"))}
    hidden = {m for p in _files(task.verifier_dir) if p.suffix == ".py"
              for m in TEST_METHOD.findall(p.read_text(errors="replace"))}
    shared = sorted(visible & hidden)
    return Check("distinct-test-names", not shared, ", ".join(shared), warning=True)


def check_protected_files_exist(task: Task, scratch: Path) -> Check:
    workspace = scratch / "leak-ws"
    missing = [rel for rel in task.protected if not (workspace / rel).is_file()]
    return Check("protected-files-exist", not missing, ", ".join(missing))


def check_wrong_solutions(task: Task, sandbox: Sandbox) -> Check:
    """Plausible incorrect solutions (wrong/*.sh) must all be rejected by the verifier.

    This tests the verifier itself. A verifier that accepts partial fixes, hardcoded output
    or common mistakes would score agents on luck.
    """
    scripts = sorted((task.root / "wrong").glob("*.sh"))
    if not scripts:
        return Check("rejects-wrong-solutions", False, "the task has no wrong/*.sh examples")
    accepted, broken = [], []
    for script in scripts:
        episode = run_episode(task, ScriptedAgent([Bash(script.read_text())]), sandbox)
        if episode.status == PASSED:
            accepted.append(script.stem)
        elif episode.status == INFRA_ERROR:
            broken.append(script.stem)
    detail = []
    if accepted:
        detail.append(f"verifier ACCEPTED wrong solutions: {accepted}")
    if broken:
        detail.append(f"harness errors on: {broken}")
    return Check("rejects-wrong-solutions", not detail, "; ".join(detail))


def validate_task(task: Task, sandbox: Sandbox, scratch: Path, repeats: int = 2) -> list[Check]:
    checks = [check_instruction(task), check_verifier_uses_isolated_python(task)]
    checks.append(check_no_leak(task, sandbox, scratch))
    checks.append(check_protected_files_exist(task, scratch))
    checks.append(check_shared_test_names(task, scratch))

    null = run_episode(task, NullAgent(), sandbox)
    checks.append(Check(
        "null-agent-fails", null.status == FAILED,
        "" if null.status == FAILED
        else f"status {null.status}: {null.error or null.verifier_output}",
    ))

    try:
        oracle_runs = [run_episode(task, OracleAgent(task), sandbox) for _ in range(repeats)]
    except FileNotFoundError as exc:
        checks.append(Check("oracle-passes", False, str(exc)))
        return checks
    statuses = [e.status for e in oracle_runs]
    detail = "" if statuses == [PASSED] * repeats else (
        f"statuses {statuses}: {oracle_runs[0].error or oracle_runs[0].verifier_output}"
    )
    checks.append(Check("oracle-passes", statuses == [PASSED] * repeats, detail))
    checks.append(Check(
        "oracle-does-not-tamper", not any(e.tampered for e in oracle_runs),
        ", ".join(sorted({t for e in oracle_runs for t in e.tampered})),
    ))
    checks.append(check_wrong_solutions(task, sandbox))
    slowest = max(e.duration for e in oracle_runs)
    checks.append(Check(
        "verifier-has-headroom", slowest < task.verify_timeout * 0.5 + 10,
        f"oracle episode took {slowest:.1f}s against a {task.verify_timeout:.0f}s verifier limit",
    ))
    return checks


def summarize(checks: list[Check]) -> bool:
    return all(c.ok or c.warning for c in checks)


def fingerprint(task: Task) -> str:
    """Stable hash of everything that defines a task, recorded with results."""
    digest = hashlib.sha256()
    for path in sorted(_files(task.root)):
        digest.update(str(path.relative_to(task.root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]
