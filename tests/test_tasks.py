"""Integration test: every bundled task must be fair, solvable and non-trivial."""

from pathlib import Path

import pytest

from agenteval.sandbox import choose_sandbox
from agenteval.task import load_tasks
from agenteval.validate import validate_task

TASKS = Path(__file__).resolve().parent.parent / "src" / "agenteval" / "tasks"
ALL = load_tasks(TASKS)


def test_there_are_enough_diverse_tasks():
    assert len(ALL) >= 12
    assert len({t.category for t in ALL}) >= 6
    assert {t.difficulty for t in ALL} == {"easy", "medium", "hard"}


@pytest.mark.parametrize("task", ALL, ids=lambda t: t.id)
def test_bundled_task_is_valid(task, tmp_path):
    sandbox = choose_sandbox([TASKS], allow_unconfined=True)
    checks = validate_task(task, sandbox, tmp_path)
    bad = {c.name: c.detail for c in checks if not c.ok and not c.warning}
    assert not bad, bad


@pytest.mark.parametrize("task", ALL, ids=lambda t: t.id)
def test_every_task_documents_what_the_hidden_checks_require(task):
    assert len(task.instruction.split()) >= 25, "the instruction must state the requirements"
    assert list((task.root / "wrong").glob("*.sh")), "wrong-solution examples are required"
