import pytest

from agenteval.report import (
    compare,
    format_comparison,
    format_summary,
    per_task_pass_at_k,
    summarize,
)


def row(agent, task, trial, status, steps=3, terminated_by="finish", category="c",
        difficulty="easy"):
    return {
        "agent": agent, "task_id": task, "trial": trial, "status": status,
        "passed": status == "passed", "terminated_by": terminated_by, "num_steps": steps,
        "isolation": "isolated", "category": category, "difficulty": difficulty,
    }


def rows_for(agent, outcomes):
    """outcomes: {task: 'ppf'} means three trials, pass pass fail."""
    out = []
    for task, pattern in outcomes.items():
        for k, ch in enumerate(pattern):
            out.append(row(agent, task, k, {"p": "passed", "f": "failed", "i": "infra_error",
                                            "t": "tampered"}[ch]))
    return out


def test_pass_at_one_is_the_per_task_success_rate():
    outcomes = ["passed", "passed", "failed", "failed"]
    scores = per_task_pass_at_k({"a": [row("x", "a", i, s) for i, s in enumerate(outcomes)]})
    assert scores == {"a": 0.5}


def test_pass_at_k_uses_the_unbiased_estimator():
    eps = rows_for("x", {"t": "pfff"})
    assert per_task_pass_at_k({"t": eps}, k=2)["t"] == pytest.approx(0.5)  # 1 - C(3,2)/C(4,2)


def test_infrastructure_errors_are_excluded_not_counted_as_failures():
    eps = rows_for("x", {"t": "pii"})
    assert per_task_pass_at_k({"t": eps}) == {"t": 1.0}
    assert per_task_pass_at_k({"t": rows_for("x", {"t": "iii"})}) == {}  # no valid sample


def test_too_few_valid_trials_for_k_is_an_error():
    with pytest.raises(ValueError, match="fewer than k"):
        per_task_pass_at_k({"t": rows_for("x", {"t": "pi"})}, k=2)


def test_summary_reports_rate_interval_and_breakdowns():
    rows = rows_for("agent", {"a": "pp", "b": "pf", "c": "ff", "d": "pp"})
    rows[3]["terminated_by"] = "step_limit"
    s = summarize(rows)["agent"]
    assert s["tasks"] == 4 and s["episodes"] == 8
    assert s["pass_rate"] == pytest.approx((1 + 0.5 + 0 + 1) / 4)
    lo, hi = s["ci"]
    assert lo <= s["pass_rate"] <= hi
    assert s["failure_breakdown"] == {"finish": 2, "step_limit": 1}


def test_tampering_and_infra_errors_are_surfaced_in_the_summary():
    rows = rows_for("agent", {"a": "pt", "b": "pi"})
    s = summarize(rows)["agent"]
    assert s["tampered"] == 1 and s["infra_errors"] == 1
    text = format_summary({"agent": s})
    assert "WARNING: 1 infrastructure errors were excluded" in text
    assert "edited protected files" in text


def test_category_and_difficulty_breakdowns():
    rows = [row("a", "t1", 0, "passed", category="git", difficulty="hard"),
            row("a", "t2", 0, "failed", category="git", difficulty="easy"),
            row("a", "t3", 0, "passed", category="sql", difficulty="easy")]
    s = summarize(rows)["a"]
    assert s["by_category"] == {"git": 0.5, "sql": 1.0}
    assert s["by_difficulty"] == {"easy": 0.5, "hard": 1.0}


def test_each_agent_is_summarised_separately():
    rows = rows_for("a", {"t": "pp"}) + rows_for("b", {"t": "ff"})
    s = summarize(rows)
    assert s["a"]["pass_rate"] == 1.0 and s["b"]["pass_rate"] == 0.0


def test_compare_reports_paired_difference_and_sign_test():
    tasks = {f"t{i}": "p" for i in range(10)}
    a = rows_for("a", tasks)
    b = rows_for("b", {**tasks, "t0": "f", "t1": "f", "t2": "f"})
    c = compare(a + b, "a", "b")
    assert c["tasks"] == 10 and c["diff"] == pytest.approx(0.3)
    assert (c["wins_a"], c["wins_b"], c["ties"]) == (3, 0, 7)
    assert c["sign_test_p"] == pytest.approx(0.25)  # exact two-sided: 2 * (1/2)^3
    assert "a - b" in format_comparison(c)


def test_compare_only_uses_shared_tasks_and_validates_agents():
    rows = rows_for("a", {"x": "p", "y": "p"}) + rows_for("b", {"y": "f", "z": "p"})
    assert compare(rows, "a", "b")["tasks"] == 1
    with pytest.raises(ValueError, match="no results for agent"):
        compare(rows, "a", "nobody")
    with pytest.raises(ValueError, match="in common"):
        compare(rows_for("a", {"x": "p"}) + rows_for("b", {"y": "p"}), "a", "b")


def test_formatting_handles_an_agent_with_no_passes():
    text = format_summary(summarize(rows_for("a", {"t": "ff"})))
    assert "pass@1 = 0.000" in text and "mean steps" not in text
