import json
import os
import time

from agenteval.agents import NullAgent, OracleAgent, ScriptedAgent
from agenteval.runner import (
    AGENT_ERROR,
    FAILED,
    FINISH,
    INFRA_ERROR,
    PASSED,
    STEP_LIMIT,
    TAMPERED,
    TIME_LIMIT,
    run_episode,
)
from agenteval.sandbox import SeatbeltSandbox
from agenteval.task import load_task
from agenteval.tools import Bash, Finish, ListDir, ReadFile, WriteFile
from tests.conftest import FIXED, make_task, needs_seatbelt

SOLVE = Bash(f"cat > calc.py <<'EOF'\n{FIXED}EOF")


def test_null_agent_fails_and_oracle_passes(task, sandbox):
    null = run_episode(task, NullAgent(), sandbox)
    oracle = run_episode(task, OracleAgent(task), sandbox)
    assert null.status == FAILED and null.terminated_by == FINISH and not null.passed
    assert oracle.status == PASSED and oracle.verifier_exit == 0 and oracle.passed


def test_a_correct_solution_made_with_file_tools_passes(task, sandbox):
    agent = ScriptedAgent([ReadFile("calc.py"), WriteFile("calc.py", FIXED), Finish("fixed")])
    ep = run_episode(task, agent, sandbox)
    assert ep.status == PASSED and len(ep.steps) == 3
    assert "a - b" in ep.steps[0].observation.text


def test_the_agents_claim_of_success_is_not_trusted(task, sandbox):
    ep = run_episode(task, ScriptedAgent([Finish("I fixed it, all tests pass!")]), sandbox)
    assert ep.status == FAILED


def test_passing_the_visible_test_but_not_the_hidden_ones_fails(task, sandbox):
    hardcode = "def add(a, b):\n    return 2 if (a, b) == (1, 1) else 0\n"
    ep = run_episode(task, ScriptedAgent([WriteFile("calc.py", hardcode)]), sandbox)
    assert ep.status == FAILED and "test_negative" in ep.verifier_output


def test_editing_a_protected_test_file_is_tampering_even_if_everything_passes(task, sandbox):
    agent = ScriptedAgent([SOLVE, WriteFile("test_visible.py", "print('rewritten')\n")])
    ep = run_episode(task, agent, sandbox)
    assert ep.status == TAMPERED and ep.tampered == ["test_visible.py"] and not ep.passed
    assert ep.verifier_exit == 0  # the solution itself was fine; the cheating is what failed it


def test_deleting_a_protected_file_is_tampering(task, sandbox):
    ep = run_episode(task, ScriptedAgent([SOLVE, Bash("rm test_visible.py")]), sandbox)
    assert ep.status == TAMPERED


def test_planted_verifier_files_cannot_override_the_real_verifier(task, sandbox):
    # The agent leaves its own calc.py buggy but plants a correct one where the hidden tests
    # look first. If the planted directory survived into the snapshot, the tests would import
    # that copy and pass.
    plant = Bash(
        "mkdir -p .verifier/tests && "
        "printf 'def add(a, b):\\n    return a + b\\n' > .verifier/tests/calc.py && "
        "echo 'exit 0' > .verifier/verify.sh"
    )
    ep = run_episode(task, ScriptedAgent([plant]), sandbox)
    assert ep.status == FAILED and "test_negative" in ep.verifier_output


def test_the_planted_verifier_attack_works_without_the_defense(task, sandbox, monkeypatch):
    """Control: with the defense off, the same attack passes, so the test above has teeth."""
    from agenteval import runner

    monkeypatch.setattr(runner, "IGNORED_FOR_SNAPSHOT", (".home", ".tmp"))
    plant = Bash(
        "mkdir -p .verifier/tests && "
        "printf 'def add(a, b):\\n    return a + b\\n' > .verifier/tests/calc.py"
    )
    assert run_episode(task, ScriptedAgent([plant]), sandbox).status == PASSED


def test_startup_hook_files_cannot_fake_a_pass(task, sandbox):
    hook = Bash(
        "echo 'import os; os._exit(0)' > sitecustomize.py; "
        "echo 'import os; os._exit(0)' > usercustomize.py; "
        "mkdir -p .home/.local && echo 'import os; os._exit(0)' > .home/.local/usercustomize.py"
    )
    assert run_episode(task, ScriptedAgent([hook]), sandbox).status == FAILED


def test_step_limit_ends_the_episode_but_the_final_state_is_still_judged(task, sandbox):
    agent = ScriptedAgent([SOLVE] + [ListDir(".")] * 20)
    ep = run_episode(task, agent, sandbox)
    assert ep.terminated_by == STEP_LIMIT and len(ep.steps) == task.max_steps
    assert ep.status == PASSED


def test_episode_time_limit(tasks_root, sandbox):
    make_task(tasks_root, "slow", extra_spec={"episode_timeout": 1, "command_timeout": 5})
    slow = load_task(tasks_root / "slow")
    agent = ScriptedAgent([Bash("sleep 3"), Bash("sleep 3"), Bash("true")])
    started = time.monotonic()
    ep = run_episode(slow, agent, sandbox)
    assert ep.terminated_by == TIME_LIMIT and time.monotonic() - started < 10


def test_an_agent_that_crashes_is_an_agent_failure_not_a_harness_failure(task, sandbox):
    class Crasher:
        name = "crasher"

        def start(self, instruction):
            pass

        def act(self, history):
            raise RuntimeError("model API exploded")

    ep = run_episode(task, Crasher(), sandbox)
    assert ep.terminated_by == AGENT_ERROR and ep.status == FAILED
    assert "model API exploded" in ep.error


def test_an_agent_that_fails_to_start_is_handled(task, sandbox):
    class BadStart:
        name = "badstart"

        def start(self, instruction):
            raise ValueError("no credentials")

        def act(self, history):
            return Finish()

    ep = run_episode(task, BadStart(), sandbox)
    assert ep.terminated_by == AGENT_ERROR and "no credentials" in ep.error


def test_invalid_actions_are_reported_back_and_do_not_crash(task, sandbox):
    ep = run_episode(task, ScriptedAgent(["rm -rf /", Finish()]), sandbox)
    assert not ep.steps[0].observation.ok and "invalid action" in ep.steps[0].observation.text


def test_a_failing_setup_script_is_an_infrastructure_error(tasks_root, sandbox):
    make_task(tasks_root, "broken-setup", setup="exit 7\n")
    ep = run_episode(load_task(tasks_root / "broken-setup"), NullAgent(), sandbox)
    assert ep.status == INFRA_ERROR and "setup failed" in ep.error


def test_setup_script_prepares_the_workspace_before_the_agent_sees_it(tasks_root, sandbox):
    make_task(tasks_root, "with-setup", setup="echo prepared > generated.txt\n")
    t = load_task(tasks_root / "with-setup")
    ep = run_episode(t, ScriptedAgent([ReadFile("generated.txt")]), sandbox)
    assert ep.steps[0].observation.text.strip() == "prepared"


def test_each_episode_starts_from_a_pristine_workspace(task, sandbox):
    run_episode(task, ScriptedAgent([Bash("echo leftover > residue.txt")]), sandbox)
    ep = run_episode(task, ScriptedAgent([ListDir(".")]), sandbox)
    assert "residue.txt" not in ep.steps[0].observation.text


def test_the_task_definition_is_never_modified_by_an_episode(task, sandbox):
    before = (task.workspace_dir / "calc.py").read_text()
    run_episode(task, OracleAgent(task), sandbox)
    assert (task.workspace_dir / "calc.py").read_text() == before


def test_workspaces_are_cleaned_up_unless_kept(task, sandbox, tmp_path):
    import glob
    import tempfile

    pattern = os.path.join(tempfile.gettempdir(), f"agenteval-{task.id}-*")
    before = set(glob.glob(pattern))
    run_episode(task, NullAgent(), sandbox)
    assert set(glob.glob(pattern)) == before
    keep = tmp_path / "kept"
    run_episode(task, NullAgent(), sandbox, keep_dir=keep)
    assert (keep / "add-bug-null-0" / "ws" / "calc.py").exists()


def test_episode_serialises_to_json(task, sandbox):
    ep = run_episode(task, OracleAgent(task), sandbox, trial=3)
    data = json.loads(json.dumps(ep.to_dict()))
    assert data["passed"] and data["trial"] == 3 and data["steps"][0]["action"]["type"] == "Bash"
    assert data["isolation"] in {"isolated", "unconfined"}


def test_an_unconfined_run_is_labelled_as_such(task, sandbox):
    assert run_episode(task, NullAgent(), sandbox).isolation == sandbox.isolation.level


# ---- the same attacks against the real isolating sandbox -------------------------------


@needs_seatbelt
def test_the_agent_cannot_read_the_hidden_verifier_or_oracle(tasks_root, task):
    sb = SeatbeltSandbox(hidden=[tasks_root])
    probe = Bash(
        f"cat {task.verifier_dir}/tests/test_hidden.py; cat {task.oracle_dir}/solve.sh; "
        f"ls {tasks_root}"
    )
    ep = run_episode(task, ScriptedAgent([probe]), sb)
    seen = ep.steps[0].observation.text
    assert "test_negative" not in seen and "cat > calc.py" not in seen
    assert ep.isolation == "isolated"


@needs_seatbelt
def test_the_agent_cannot_modify_files_outside_its_workspace(tasks_root, task):
    sb = SeatbeltSandbox(hidden=[tasks_root])
    victim = task.verifier_dir / "tests" / "test_hidden.py"
    original = victim.read_text()
    attack = Bash(
        f"echo 'import sys; sys.exit(0)' > {victim}; echo pwned > {tasks_root}/pwned.txt"
    )
    ep = run_episode(task, ScriptedAgent([attack]), sb)
    assert victim.read_text() == original and not (tasks_root / "pwned.txt").exists()
    assert ep.status == FAILED


@needs_seatbelt
def test_oracle_still_passes_under_full_isolation(tasks_root, task):
    ep = run_episode(task, OracleAgent(task), SeatbeltSandbox(hidden=[tasks_root]))
    assert ep.status == PASSED and ep.isolation == "isolated"


@needs_seatbelt
def test_file_tools_cannot_reach_the_verifier_through_path_tricks(tasks_root, task):
    sb = SeatbeltSandbox(hidden=[tasks_root])
    target = str(task.verifier_dir / "tests" / "test_hidden.py")
    agent = ScriptedAgent([ReadFile(target), ReadFile("../" * 12 + target.lstrip("/"))])
    ep = run_episode(task, agent, sb)
    assert all(not s.observation.ok for s in ep.steps[:2])
    assert all("test_negative" not in s.observation.text for s in ep.steps)
