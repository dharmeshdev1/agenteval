import json

import pytest

from agenteval.agents import NullAgent, OracleAgent
from agenteval.evaluate import load_results, run_suite
from agenteval.task import load_tasks
from tests.conftest import make_task


@pytest.fixture
def tasks(tasks_root):
    make_task(tasks_root, "second-bug")
    return load_tasks(tasks_root)


def test_every_task_and_trial_is_run_and_recorded(tasks, sandbox, tmp_path):
    out = tmp_path / "r.jsonl"
    rows = run_suite(tasks, lambda t: OracleAgent(t), "oracle", sandbox, trials=3, workers=3,
                     results_path=out)
    assert len(rows) == 6 and all(r["passed"] for r in rows)
    on_disk = load_results(out)
    assert sorted((r["task_id"], r["trial"]) for r in on_disk) == sorted(
        (t, k) for t in ("add-bug", "second-bug") for k in range(3)
    )
    assert all(r["agent"] == "oracle" and len(r["task_fingerprint"]) == 16 for r in on_disk)
    assert all(r["category"] == "python-bugfix" and r["difficulty"] == "easy" for r in on_disk)


def test_a_fresh_agent_is_built_for_every_episode(tasks, sandbox):
    built = []

    def factory(task):
        built.append(task.id)
        return NullAgent()

    run_suite(tasks, factory, "null", sandbox, trials=2)
    assert sorted(built) == ["add-bug", "add-bug", "second-bug", "second-bug"]


def test_resume_skips_finished_episodes_and_only_runs_the_rest(tasks, sandbox, tmp_path):
    out = tmp_path / "r.jsonl"
    run_suite(tasks, lambda t: NullAgent(), "null", sandbox, trials=1, results_path=out)
    built = []
    run_suite(tasks, lambda t: built.append(t.id) or NullAgent(), "null", sandbox, trials=2,
              results_path=out, resume=True)
    assert sorted(built) == ["add-bug", "second-bug"]  # only trial 1 was new
    assert len(load_results(out)) == 4


def test_resume_does_not_confuse_different_agents(tasks, sandbox, tmp_path):
    out = tmp_path / "r.jsonl"
    run_suite(tasks, lambda t: NullAgent(), "null", sandbox, results_path=out)
    rows = run_suite(tasks, lambda t: OracleAgent(t), "oracle", sandbox, results_path=out,
                     resume=True)
    assert len(rows) == 2 and len(load_results(out)) == 4


def test_without_resume_results_are_appended_not_replaced(tasks, sandbox, tmp_path):
    out = tmp_path / "r.jsonl"
    for _ in range(2):
        run_suite(tasks, lambda t: NullAgent(), "null", sandbox, results_path=out)
    assert len(load_results(out)) == 4


def test_results_written_as_they_arrive_so_an_interruption_keeps_finished_work(
    tasks, sandbox, tmp_path
):
    out = tmp_path / "r.jsonl"
    seen = []

    def stop_after_first(row):
        seen.append(len(load_results(out)))

    run_suite(tasks, lambda t: NullAgent(), "null", sandbox, results_path=out,
              on_result=stop_after_first)
    assert seen == [1, 2]  # the file already held each result when the callback ran


def test_invalid_parameters_are_rejected(tasks, sandbox):
    for kw in (dict(trials=0), dict(workers=0)):
        with pytest.raises(ValueError):
            run_suite(tasks, lambda t: NullAgent(), "null", sandbox, **kw)


def test_load_results_handles_missing_files_and_reports_corruption(tmp_path):
    assert load_results(tmp_path / "nope.jsonl") == []
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"ok": 1}\n{broken\n')
    with pytest.raises(ValueError, match="bad.jsonl:2"):
        load_results(bad)


def test_parallel_episodes_do_not_interfere_with_each_other(tasks_root, sandbox):
    for i in range(6):
        make_task(tasks_root, f"par-{i}")
    many = load_tasks(tasks_root)
    rows = run_suite(many, lambda t: OracleAgent(t), "oracle", sandbox, trials=2, workers=8)
    assert len(rows) == len(many) * 2 and all(r["passed"] for r in rows)
    assert json.loads(json.dumps(rows))
