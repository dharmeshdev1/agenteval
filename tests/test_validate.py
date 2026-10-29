import shutil

import pytest

from agenteval.task import load_task
from agenteval.validate import fingerprint, summarize, validate_task
from tests.conftest import make_task, write


def run(tasks_root, sandbox, tmp_path, task_id="add-bug", repeats=1):
    task = load_task(tasks_root / task_id)
    scratch = tmp_path / f"scratch-{task_id}"
    scratch.mkdir(exist_ok=True)
    return {c.name: c for c in validate_task(task, sandbox, scratch, repeats=repeats)}


def failing(checks):
    return sorted(n for n, c in checks.items() if not c.ok and not c.warning)


def test_a_well_formed_task_passes_every_check(tasks_root, sandbox, tmp_path):
    checks = run(tasks_root, sandbox, tmp_path)
    assert failing(checks) == [], {n: c.detail for n, c in checks.items() if not c.ok}
    assert summarize(list(checks.values()))


def test_a_verifier_that_always_passes_is_caught(tasks_root, sandbox, tmp_path):
    write(tasks_root / "add-bug" / "verifier" / "verify.sh", "exit 0\n")
    checks = run(tasks_root, sandbox, tmp_path)
    assert "null-agent-fails" in failing(checks)
    assert "rejects-wrong-solutions" in failing(checks)
    assert "ACCEPTED" in checks["rejects-wrong-solutions"].detail


def test_a_verifier_that_always_fails_is_caught(tasks_root, sandbox, tmp_path):
    write(tasks_root / "add-bug" / "verifier" / "verify.sh", "exit 1\n")
    assert "oracle-passes" in failing(run(tasks_root, sandbox, tmp_path))


def test_an_oracle_that_does_not_solve_the_task_is_caught(tasks_root, sandbox, tmp_path):
    write(tasks_root / "add-bug" / "oracle" / "solve.sh", "true\n")
    assert "oracle-passes" in failing(run(tasks_root, sandbox, tmp_path))


def test_a_missing_oracle_is_reported(tasks_root, sandbox, tmp_path):
    (tasks_root / "add-bug" / "oracle" / "solve.sh").unlink()
    checks = run(tasks_root, sandbox, tmp_path)
    assert "oracle-passes" in failing(checks)
    assert "oracle/solve.sh" in checks["oracle-passes"].detail


def test_an_oracle_that_edits_protected_files_is_caught(tasks_root, sandbox, tmp_path):
    solve = tasks_root / "add-bug" / "oracle" / "solve.sh"
    solve.write_text(solve.read_text() + "echo tweak >> test_visible.py\n")
    assert "oracle-does-not-tamper" in failing(run(tasks_root, sandbox, tmp_path))


def test_python_without_isolated_mode_in_a_verifier_is_flagged(tasks_root, sandbox, tmp_path):
    write(tasks_root / "add-bug" / "verifier" / "verify.sh",
          "python3 .verifier/_shared/pyrun.py .verifier/tests\n")
    checks = run(tasks_root, sandbox, tmp_path)
    assert "verifier-isolated-python" in failing(checks)
    assert "python3" in checks["verifier-isolated-python"].detail


@pytest.mark.parametrize(
    "script",
    [
        "python3 -I a.py",
        "python3 -I -c 'x'",
        "python3 -Ib a.py",
        "echo no python here",
        "# python3 in a comment",
        "echo 'python3 is mentioned in a message'",
        "grep -q python3 notes.txt",
    ],
)
def test_isolated_python_invocations_are_accepted(tasks_root, sandbox, tmp_path, script):
    write(tasks_root / "add-bug" / "verifier" / "extra.sh", script + "\n")
    assert run(tasks_root, sandbox, tmp_path)["verifier-isolated-python"].ok


@pytest.mark.parametrize(
    "script",
    [
        "python3 a.py",
        "x=1; python3 a.py",
        "true && python3 a.py",
        "cat f | python3 a.py",
        "out=$(python3 a.py)",
        "env python3 a.py",
        "if true; then\n  python3 a.py\nfi",
    ],
)
def test_every_unisolated_way_of_starting_python_is_still_caught(
    tasks_root, sandbox, tmp_path, script
):
    write(tasks_root / "add-bug" / "verifier" / "extra.sh", script + "\n")
    assert not run(tasks_root, sandbox, tmp_path)["verifier-isolated-python"].ok


def test_a_hidden_file_copied_into_the_workspace_is_a_leak(tasks_root, sandbox, tmp_path):
    hidden = tasks_root / "add-bug" / "verifier" / "tests" / "test_hidden.py"
    shutil.copy(hidden, tasks_root / "add-bug" / "workspace" / "copy_of_hidden_tests.py")
    checks = run(tasks_root, sandbox, tmp_path)
    assert "no-leak" in failing(checks) and "copy_of_hidden_tests.py" in checks["no-leak"].detail


def test_visible_tests_reusing_hidden_test_names_only_warn(tasks_root, sandbox, tmp_path):
    visible = tasks_root / "add-bug" / "workspace" / "test_visible.py"
    visible.write_text(visible.read_text() + "\n    def test_negative(self): pass\n")
    checks = run(tasks_root, sandbox, tmp_path)
    assert checks["distinct-test-names"].warning and not checks["distinct-test-names"].ok
    assert "test_negative" in checks["distinct-test-names"].detail
    assert failing(checks) == []  # a warning does not fail the task


def test_a_missing_protected_file_is_caught(tasks_root, sandbox, tmp_path):
    (tasks_root / "add-bug" / "workspace" / "test_visible.py").unlink()
    assert "protected-files-exist" in failing(run(tasks_root, sandbox, tmp_path))


def test_a_task_without_wrong_solutions_is_not_valid(tasks_root, sandbox, tmp_path):
    shutil.rmtree(tasks_root / "add-bug" / "wrong")
    checks = run(tasks_root, sandbox, tmp_path)
    assert "rejects-wrong-solutions" in failing(checks)
    assert "no wrong/*.sh" in checks["rejects-wrong-solutions"].detail


def test_a_wrong_solution_that_the_verifier_accepts_is_named(tasks_root, sandbox, tmp_path):
    write(tasks_root / "add-bug" / "wrong" / "actually-correct.sh", "cp /dev/null /dev/null\n")
    # a script that fixes the bug is "wrong" only by name, so the verifier rightly accepts it
    write(tasks_root / "add-bug" / "wrong" / "actually-correct.sh",
          "printf 'def add(a, b):\\n    return a + b\\n' > calc.py\n")
    checks = run(tasks_root, sandbox, tmp_path)
    assert "actually-correct" in checks["rejects-wrong-solutions"].detail


def test_a_very_short_instruction_is_flagged(tasks_root, sandbox, tmp_path):
    make_task(tasks_root, "terse", extra_spec={"instruction": "Fix it."})
    assert "instruction" in failing(run(tasks_root, sandbox, tmp_path, "terse"))


def test_fingerprint_is_stable_and_sensitive_to_every_part(tasks_root):
    task = load_task(tasks_root / "add-bug")
    first = fingerprint(task)
    assert fingerprint(load_task(tasks_root / "add-bug")) == first
    for rel in ("verifier/tests/test_hidden.py", "workspace/calc.py", "oracle/solve.sh"):
        path = tasks_root / "add-bug" / rel
        original = path.read_text()
        path.write_text(original + "# change\n")
        assert fingerprint(load_task(tasks_root / "add-bug")) != first, rel
        path.write_text(original)
    assert fingerprint(load_task(tasks_root / "add-bug")) == first
