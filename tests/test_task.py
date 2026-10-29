import json
import shutil

import pytest

from agenteval.task import TaskError, hash_file, load_task, load_tasks
from tests.conftest import SHARED, make_task


def test_valid_task_loads_with_defaults(task):
    assert task.id == "add-bug" and task.max_steps == 6 and task.protected == ("test_visible.py",)
    assert task.episode_timeout == 300.0 and task.workspace_dir.is_dir()


def test_load_tasks_skips_shared_and_hidden_directories(tasks_root):
    (tasks_root / ".cache").mkdir()
    assert [t.id for t in load_tasks(tasks_root)] == ["add-bug"]


def test_only_filter_and_unknown_ids(tasks_root):
    assert len(load_tasks(tasks_root, only=["add-bug"])) == 1
    with pytest.raises(TaskError, match="unknown task ids"):
        load_tasks(tasks_root, only=["nope"])


@pytest.mark.parametrize(
    "spec,match",
    [
        ({"instruction": " "}, "missing or empty"),
        ({"difficulty": "impossible"}, "difficulty"),
        ({"id": "other"}, "must match the directory name"),
        ({"max_steps": 0}, "max_steps"),
        ({"max_steps": "ten"}, "must be a number"),
        ({"command_timeout": 100000}, "command_timeout"),
        ({"protected": "calc.py"}, "list of paths"),
        ({"protected": ["../escape"]}, "relative and inside"),
        ({"protected": ["/etc/passwd"]}, "relative and inside"),
    ],
)
def test_malformed_specs_are_rejected_with_a_clear_message(tmp_path, spec, match):
    root = tmp_path / "t"
    root.mkdir()
    make_task(root, extra_spec=spec)
    with pytest.raises(TaskError, match=match):
        load_task(root / "add-bug")


def test_missing_pieces_are_rejected(tasks_root):
    base = tasks_root / "add-bug"
    (base / "verifier" / "verify.sh").unlink()
    with pytest.raises(TaskError, match="verify.sh"):
        load_task(base)
    shutil.rmtree(base / "verifier")
    with pytest.raises(TaskError, match="verifier/"):
        load_task(base)
    (base / "task.json").write_text("{not json")
    with pytest.raises(TaskError, match="not valid JSON"):
        load_task(base)
    (base / "task.json").unlink()
    with pytest.raises(TaskError, match="missing task.json"):
        load_task(base)


def test_task_json_must_be_an_object(tasks_root):
    (tasks_root / "add-bug" / "task.json").write_text(json.dumps([1, 2]))
    with pytest.raises(TaskError, match="must be an object"):
        load_task(tasks_root / "add-bug")


def test_hash_file(tmp_path):
    f = tmp_path / "f"
    f.write_text("abc")
    assert hash_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert hash_file(tmp_path / "missing") is None


def test_shared_runner_exists():
    assert (SHARED / "pyrun.py").is_file()
