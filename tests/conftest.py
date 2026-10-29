import shutil
import textwrap
from pathlib import Path

import pytest

from agenteval.sandbox import SeatbeltSandbox, choose_sandbox
from agenteval.task import load_task

SHARED = Path(__file__).resolve().parent.parent / "src" / "agenteval" / "tasks" / "_shared"

BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"


def write(path: Path, text: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"))
    if mode:
        path.chmod(mode)


def make_task(root: Path, task_id="add-bug", extra_spec=None, setup=None) -> Path:
    """A tiny but complete task: fix ``add``. Hidden tests check cases the visible test does not."""
    import json

    task = root / task_id
    spec = {
        "id": task_id, "title": "Fix add", "category": "python-bugfix", "difficulty": "easy",
        "instruction": "The function calc.add returns the wrong result for most inputs. "
        "Fix calc.py so that add(a, b) returns the sum of a and b. Do not edit test_visible.py.",
        "protected": ["test_visible.py"], "max_steps": 6, "command_timeout": 20,
        "verify_timeout": 30,
    }
    spec.update(extra_spec or {})
    write(task / "task.json", json.dumps(spec))
    write(task / "workspace" / "calc.py", BUGGY)
    write(task / "workspace" / "test_visible.py", """
        import calc, unittest
        class T(unittest.TestCase):
            def test_one(self): self.assertEqual(calc.add(1, 1), 2)
        """)
    write(
        task / "verifier" / "verify.sh",
        "python3 -I .verifier/_shared/pyrun.py .verifier/tests\n",
    )
    write(task / "verifier" / "tests" / "test_hidden.py", """
        import calc, unittest
        class T(unittest.TestCase):
            def test_negative(self): self.assertEqual(calc.add(-5, 2), -3)
            def test_zero(self): self.assertEqual(calc.add(0, 0), 0)
        """)
    write(task / "oracle" / "solve.sh", f"cat > calc.py <<'EOF'\n{FIXED}EOF\n")
    write(task / "wrong" / "does-nothing.sh", "true\n")
    write(task / "wrong" / "hardcodes.sh", "printf 'def add(a, b):\\n    return 2\\n' > calc.py\n")
    if setup:
        write(task / "setup.sh", setup)
    return task


@pytest.fixture
def tasks_root(tmp_path):
    root = tmp_path / "tasks"
    root.mkdir()
    shutil.copytree(SHARED, root / "_shared")
    make_task(root)
    return root


@pytest.fixture
def task(tasks_root):
    return load_task(tasks_root / "add-bug")


@pytest.fixture
def sandbox(tasks_root):
    return choose_sandbox([tasks_root], allow_unconfined=True)


needs_seatbelt = pytest.mark.skipif(
    not SeatbeltSandbox.available(), reason="needs macOS sandbox-exec"
)
