"""Turn raw episode records into numbers that do not overstate what was measured."""

from __future__ import annotations

from collections import Counter, defaultdict

from evalkit.passk import pass_at_k
from evalkit.stats import bootstrap_ci, paired_bootstrap_diff, sign_test


def _group(rows: list[dict]) -> dict[str, dict[str, list[dict]]]:
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["agent"]][row["task_id"]].append(row)
    return grouped


def per_task_pass_at_k(episodes_by_task: dict[str, list[dict]], k: int = 1) -> dict[str, float]:
    """Unbiased pass@k per task. Infrastructure errors are excluded, not counted as failures.

    A task whose every trial hit an infrastructure error has no valid sample and is dropped.
    Raises if a task has fewer valid trials than ``k``.
    """
    scores: dict[str, float] = {}
    for task, episodes in episodes_by_task.items():
        valid = [e for e in episodes if e["status"] != "infra_error"]
        if not valid:
            continue
        if len(valid) < k:
            raise ValueError(f"task {task!r} has {len(valid)} valid trials, fewer than k={k}")
        scores[task] = pass_at_k(len(valid), sum(e["passed"] for e in valid), k)
    return scores


def summarize_agent(episodes_by_task: dict[str, list[dict]], k: int = 1) -> dict:
    rows = [e for eps in episodes_by_task.values() for e in eps]
    scores = per_task_pass_at_k(episodes_by_task, k)
    values = list(scores.values())
    mean = sum(values) / len(values) if values else float("nan")
    lo, hi = bootstrap_ci(values) if len(values) > 1 else (mean, mean)

    failures = Counter(
        e["terminated_by"] if e["status"] == "failed" else e["status"]
        for e in rows if not e["passed"]
    )
    by_group: dict[str, dict[str, float]] = {}
    for key in ("category", "difficulty"):
        buckets: dict[str, list[float]] = defaultdict(list)
        for task, eps in episodes_by_task.items():
            if task in scores:
                buckets[eps[0].get(key, "unknown")].append(scores[task])
        by_group[key] = {name: sum(v) / len(v) for name, v in sorted(buckets.items())}

    steps = [e["num_steps"] for e in rows if e["passed"]]
    return {
        "tasks": len(scores), "episodes": len(rows), "k": k,
        "pass_rate": mean, "ci": (lo, hi),
        "infra_errors": sum(e["status"] == "infra_error" for e in rows),
        "tampered": sum(e["status"] == "tampered" for e in rows),
        "isolation": sorted({e["isolation"] for e in rows}),
        "failure_breakdown": dict(failures),
        "by_category": by_group["category"], "by_difficulty": by_group["difficulty"],
        "mean_steps_when_passed": sum(steps) / len(steps) if steps else None,
        "per_task": scores,
    }


def summarize(rows: list[dict], k: int = 1) -> dict[str, dict]:
    return {agent: summarize_agent(tasks, k) for agent, tasks in _group(rows).items()}


def compare(rows: list[dict], a: str, b: str, k: int = 1) -> dict:
    """Paired comparison of two agents on the tasks both have valid results for."""
    grouped = _group(rows)
    for name in (a, b):
        if name not in grouped:
            raise ValueError(f"no results for agent {name!r}")
    sa = per_task_pass_at_k(grouped[a], k)
    sb = per_task_pass_at_k(grouped[b], k)
    shared = sorted(set(sa) & set(sb))
    if not shared:
        raise ValueError("the two agents have no tasks in common")
    va, vb = [sa[t] for t in shared], [sb[t] for t in shared]
    diff, (lo, hi) = paired_bootstrap_diff(va, vb)
    wins_a = sum(x > y for x, y in zip(va, vb, strict=True))
    wins_b = sum(y > x for x, y in zip(va, vb, strict=True))
    return {
        "a": a, "b": b, "k": k, "tasks": len(shared),
        "pass_a": sum(va) / len(va), "pass_b": sum(vb) / len(vb),
        "diff": diff, "ci": (lo, hi), "wins_a": wins_a, "wins_b": wins_b,
        "ties": len(shared) - wins_a - wins_b, "sign_test_p": sign_test(wins_a, wins_b),
    }


def format_summary(summary: dict[str, dict]) -> str:
    lines = []
    for agent, s in sorted(summary.items()):
        lo, hi = s["ci"]
        lines.append(f"{agent}: pass@{s['k']} = {s['pass_rate']:.3f}  95% CI [{lo:.3f}, {hi:.3f}]"
                     f"  over {s['tasks']} tasks, {s['episodes']} episodes")
        lines.append(f"  isolation: {', '.join(s['isolation'])}")
        if s["infra_errors"]:
            lines.append(f"  WARNING: {s['infra_errors']} infrastructure errors were excluded")
        if s["tampered"]:
            lines.append(f"  {s['tampered']} episodes edited protected files and were failed")
        if s["failure_breakdown"]:
            parts = ", ".join(f"{k} {v}" for k, v in sorted(s["failure_breakdown"].items()))
            lines.append(f"  not passed: {parts}")
        for key in ("by_difficulty", "by_category"):
            parts = ", ".join(f"{n} {v:.2f}" for n, v in s[key].items())
            lines.append(f"  {key.replace('by_', '')}: {parts}")
        if s["mean_steps_when_passed"] is not None:
            lines.append(f"  mean steps when passed: {s['mean_steps_when_passed']:.1f}")
    return "\n".join(lines)


def format_comparison(c: dict) -> str:
    lo, hi = c["ci"]
    return "\n".join([
        f"pass@{c['k']} over {c['tasks']} shared tasks",
        f"  {c['a']} {c['pass_a']:.3f}   {c['b']} {c['pass_b']:.3f}",
        f"  {c['a']} - {c['b']} = {c['diff']:+.3f}  95% paired CI [{lo:+.3f}, {hi:+.3f}]",
        f"  tasks won: {c['a']} {c['wins_a']}, {c['b']} {c['wins_b']}, tied {c['ties']}",
        f"  sign test p = {c['sign_test_p']:.4f}",
    ])
