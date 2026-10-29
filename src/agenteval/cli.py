from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from agenteval.agents import NullAgent, OracleAgent
from agenteval.evaluate import load_results, run_suite
from agenteval.report import compare, format_comparison, format_summary, summarize
from agenteval.sandbox import choose_sandbox
from agenteval.task import TaskError, load_tasks
from agenteval.validate import summarize as checks_ok
from agenteval.validate import validate_task

DEFAULT_TASKS = Path(__file__).resolve().parent / "tasks"


def _sandbox(a: argparse.Namespace, tasks_root: Path, extra_hidden: list[Path] | None = None):
    hidden = [tasks_root.resolve(), *(extra_hidden or [])]
    return choose_sandbox(hidden, allow_unconfined=a.allow_unconfined)


def cmd_list(a: argparse.Namespace) -> int:
    for t in load_tasks(Path(a.tasks)):
        print(f"{t.id:<28}{t.category:<18}{t.difficulty:<8}{t.title}")
    return 0


def cmd_validate(a: argparse.Namespace) -> int:
    tasks_root = Path(a.tasks)
    tasks = load_tasks(tasks_root, a.only or None)
    sandbox = _sandbox(a, tasks_root)
    print(f"sandbox: {sandbox.name} ({sandbox.isolation.level})\n")
    failed = 0
    for task in tasks:
        with tempfile.TemporaryDirectory(prefix="agenteval-validate-") as scratch:
            checks = validate_task(task, sandbox, Path(scratch), repeats=a.repeats)
        ok = checks_ok(checks)
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {task.id}")
        for c in checks:
            if not c.ok:
                tag = "warn" if c.warning else "FAIL"
                print(f"        {tag}  {c.name}: {c.detail}")
    print(f"\n{len(tasks) - failed}/{len(tasks)} tasks valid")
    return 1 if failed else 0


def _agent(a: argparse.Namespace):
    if a.agent == "null":
        return "null", lambda task: NullAgent()
    if a.agent == "oracle":
        return "oracle", lambda task: OracleAgent(task)
    from agenteval.llm import make_llm_factory

    return make_llm_factory(a.model, a.base_url, a.temperature, a.max_tokens)


def cmd_run(a: argparse.Namespace) -> int:
    tasks_root, out = Path(a.tasks), Path(a.out)
    tasks = load_tasks(tasks_root, a.only or None)
    sandbox = _sandbox(a, tasks_root, [out.resolve().parent])
    name, factory = _agent(a)
    print(
        f"{name}: {len(tasks)} tasks x {a.trials} trials, sandbox {sandbox.name} "
        f"({sandbox.isolation.level}), {a.workers} workers"
    )

    def show(row: dict) -> None:
        print(f"  {row['status']:<10} {row['task_id']:<28} trial {row['trial']}  "
              f"{row['num_steps']:>2} steps  {row['duration']:.1f}s", flush=True)

    rows = run_suite(tasks, factory, name, sandbox, a.trials, a.workers, out, a.resume, show)
    summary = summarize(load_results(out), a.k)
    print()
    if name in summary:
        print(format_summary({name: summary[name]}))
    return 1 if any(r["status"] == "infra_error" for r in rows) else 0


def cmd_report(a: argparse.Namespace) -> int:
    rows = load_results(a.results)
    if not rows:
        raise ValueError(f"{a.results} contains no results")
    print(format_summary(summarize(rows, a.k)))
    return 0


def cmd_compare(a: argparse.Namespace) -> int:
    print(format_comparison(compare(load_results(a.results), a.a, a.b, a.k)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agenteval", description="Agent evaluation harness")
    sub = p.add_subparsers(dest="command", required=True)

    def common(s: argparse.ArgumentParser) -> None:
        s.add_argument("--tasks", default=str(DEFAULT_TASKS))
        s.add_argument("--only", nargs="+", help="task ids to include")
        s.add_argument(
            "--allow-unconfined", action="store_true",
            help="run without OS-level isolation when none is available (trusted tasks only)",
        )

    s = sub.add_parser("list", help="list tasks")
    s.add_argument("--tasks", default=str(DEFAULT_TASKS))
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("validate", help="check every task is solvable, fair and non-trivial")
    common(s)
    s.add_argument("--repeats", type=int, default=2, help="oracle runs, to catch flaky tasks")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("run", help="run an agent on the tasks and record every episode")
    common(s)
    s.add_argument("--agent", choices=["null", "oracle", "llm"], required=True)
    s.add_argument("--model", help="model id, for --agent llm")
    s.add_argument("--base-url", default="https://api.anthropic.com")
    s.add_argument("--temperature", type=float, default=0.0)
    s.add_argument("--max-tokens", type=int, default=4096)
    s.add_argument("--trials", type=int, default=1)
    s.add_argument("--workers", type=int, default=2)
    s.add_argument("--k", type=int, default=1)
    s.add_argument("--out", default="runs/results.jsonl")
    s.add_argument("--resume", action="store_true", help="skip episodes already in --out")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("report", help="summarise a results file")
    s.add_argument("results")
    s.add_argument("--k", type=int, default=1)
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("compare", help="paired comparison of two agents in one results file")
    s.add_argument("results")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--k", type=int, default=1)
    s.set_defaults(func=cmd_compare)
    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = args.func(args)
    except (TaskError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"agenteval: error: {exc}\n")
    sys.exit(code)


if __name__ == "__main__":
    main()
