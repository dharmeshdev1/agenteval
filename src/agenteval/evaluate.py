"""Run a suite of tasks with an agent, in parallel, writing results as they arrive."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agenteval.agents import Agent
from agenteval.runner import Episode, run_episode
from agenteval.sandbox import Sandbox
from agenteval.task import Task
from agenteval.validate import fingerprint

AgentFactory = Callable[[Task], Agent]


def load_results(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON ({exc})") from exc
    return rows


def run_suite(
    tasks: list[Task],
    factory: AgentFactory,
    agent_name: str,
    sandbox: Sandbox,
    trials: int = 1,
    workers: int = 1,
    results_path: str | Path | None = None,
    resume: bool = False,
    on_result: Callable[[dict], None] | None = None,
) -> list[dict]:
    """Run every task ``trials`` times. Results are appended to ``results_path`` immediately,
    so an interrupted run loses at most the episodes in flight, and ``resume`` skips
    episodes that already have a record. A fresh agent is built for every episode.
    """
    if trials < 1 or workers < 1:
        raise ValueError("trials and workers must be at least 1")
    done: set[tuple[str, int]] = set()
    if results_path is not None and resume:
        done = {
            (r["task_id"], r["trial"]) for r in load_results(results_path)
            if r["agent"] == agent_name
        }
    jobs = [(t, k) for t in tasks for k in range(trials) if (t.id, k) not in done]
    prints = {t.id: fingerprint(t) for t in tasks}
    lock = threading.Lock()
    rows: list[dict] = []

    def work(task: Task, trial: int) -> dict:
        episode: Episode = run_episode(task, factory(task), sandbox, trial=trial)
        row = episode.to_dict()
        row["agent"] = agent_name
        row["task_fingerprint"] = prints[task.id]
        row["category"], row["difficulty"] = task.category, task.difficulty
        return row

    out = Path(results_path) if results_path is not None else None
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, t, k) for t, k in jobs]
        for future in as_completed(futures):
            row = future.result()
            with lock:
                rows.append(row)
                if out is not None:
                    with out.open("a") as handle:
                        handle.write(json.dumps(row) + "\n")
            if on_result is not None:
                on_result(row)
    return rows
