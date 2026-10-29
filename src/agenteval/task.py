"""Task definitions: a directory with the agent-visible workspace and everything hidden.

    <task>/
      task.json    id, instruction, limits, protected files
      workspace/   copied into the sandbox for the agent
      verifier/    HIDDEN. verify.sh decides pass or fail after the episode ends
      oracle/      HIDDEN. solve.sh is a known-good solution, used only to validate the task
      setup.sh     optional, run inside the sandbox before the agent starts
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED = ("id", "title", "instruction", "category", "difficulty")
DIFFICULTIES = ("easy", "medium", "hard")


class TaskError(ValueError):
    """A task definition is malformed."""


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    instruction: str
    category: str
    difficulty: str
    root: Path
    command_timeout: float = 30.0
    episode_timeout: float = 300.0
    verify_timeout: float = 60.0
    max_steps: int = 30
    protected: tuple[str, ...] = ()

    @property
    def workspace_dir(self) -> Path:
        return self.root / "workspace"

    @property
    def verifier_dir(self) -> Path:
        return self.root / "verifier"

    @property
    def oracle_dir(self) -> Path:
        return self.root / "oracle"

    @property
    def setup_script(self) -> Path:
        return self.root / "setup.sh"


def load_task(root: Path) -> Task:
    root = Path(root).resolve()
    spec_path = root / "task.json"
    if not spec_path.is_file():
        raise TaskError(f"{root.name}: missing task.json")
    try:
        spec = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise TaskError(f"{root.name}: task.json is not valid JSON ({exc})") from exc
    if not isinstance(spec, dict):
        raise TaskError(f"{root.name}: task.json must be an object")

    missing = [k for k in REQUIRED if not isinstance(spec.get(k), str) or not spec[k].strip()]
    if missing:
        raise TaskError(f"{root.name}: missing or empty fields {missing}")
    if spec["id"] != root.name:
        raise TaskError(f"{root.name}: id {spec['id']!r} must match the directory name")
    if spec["difficulty"] not in DIFFICULTIES:
        raise TaskError(f"{spec['id']}: difficulty must be one of {DIFFICULTIES}")

    numbers = {
        "command_timeout": (float, 0.5, 600),
        "episode_timeout": (float, 1, 7200),
        "verify_timeout": (float, 1, 600),
        "max_steps": (int, 1, 500),
    }
    values: dict = {}
    for key, (kind, low, high) in numbers.items():
        if key in spec:
            value = spec[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TaskError(f"{spec['id']}: {key} must be a number")
            if not low <= value <= high:
                raise TaskError(f"{spec['id']}: {key} must be between {low} and {high}")
            values[key] = kind(value)

    protected = spec.get("protected", [])
    if not isinstance(protected, list) or not all(isinstance(p, str) for p in protected):
        raise TaskError(f"{spec['id']}: protected must be a list of paths")
    for rel in protected:
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise TaskError(f"{spec['id']}: protected path {rel!r} must be relative and inside")

    for needed in ("workspace", "verifier"):
        if not (root / needed).is_dir():
            raise TaskError(f"{spec['id']}: missing {needed}/ directory")
    if not (root / "verifier" / "verify.sh").is_file():
        raise TaskError(f"{spec['id']}: verifier/verify.sh is required")

    return Task(
        id=spec["id"], title=spec["title"], instruction=spec["instruction"].strip(),
        category=spec["category"], difficulty=spec["difficulty"], root=root,
        protected=tuple(protected), **values,
    )


def load_tasks(tasks_root: Path, only: list[str] | None = None) -> list[Task]:
    tasks_root = Path(tasks_root)
    dirs = sorted(
        d for d in tasks_root.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))
    )
    tasks = [load_task(d) for d in dirs]
    ids = [t.id for t in tasks]
    if len(set(ids)) != len(ids):
        raise TaskError("duplicate task ids")
    if only:
        unknown = sorted(set(only) - set(ids))
        if unknown:
            raise TaskError(f"unknown task ids: {unknown}")
        tasks = [t for t in tasks if t.id in only]
    return tasks


def hash_file(path: Path) -> str | None:
    """SHA-256 of a file, or ``None`` if it does not exist."""
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()
