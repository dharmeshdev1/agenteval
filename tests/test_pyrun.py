"""The hidden-test runner must never let an agent's file replace a standard module."""

import subprocess
import sys
import textwrap
from pathlib import Path

from tests.conftest import SHARED

PYRUN = SHARED / "pyrun.py"
PYTHON = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable


def run(workspace: Path, tests: Path, flags=("-I",), env=None):
    return subprocess.run(
        [PYTHON, *flags, str(PYRUN), str(tests)], cwd=workspace, capture_output=True,
        text=True, env=env or {"PATH": "/usr/bin:/bin"}, timeout=30,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def test_a_workspace_file_cannot_shadow_a_stdlib_module(tmp_path):
    ws, tests = tmp_path / "ws", tmp_path / "tests"
    write(ws / "colorsys.py", "SHADOWED = True\n")  # an agent trying to replace the stdlib
    write(tests / "test_it.py", """
        import colorsys, unittest
        class T(unittest.TestCase):
            def test_real_module(self):
                self.assertFalse(hasattr(colorsys, "SHADOWED"))
                self.assertTrue(hasattr(colorsys, "rgb_to_hsv"))
        """)
    result = run(ws, tests)
    assert result.returncode == 0, result.stderr


def test_the_agents_own_modules_are_importable(tmp_path):
    ws, tests = tmp_path / "ws", tmp_path / "tests"
    write(ws / "mylib.py", "VALUE = 41\n")
    write(tests / "test_it.py", """
        import mylib, unittest
        class T(unittest.TestCase):
            def test_value(self): self.assertEqual(mylib.VALUE + 1, 42)
        """)
    assert run(ws, tests).returncode == 0


def test_failing_tests_give_a_nonzero_exit(tmp_path):
    ws, tests = tmp_path / "ws", tmp_path / "tests"
    ws.mkdir()
    write(tests / "test_it.py", """
        import unittest
        class T(unittest.TestCase):
            def test_fail(self): self.assertEqual(1, 2)
        """)
    assert run(ws, tests).returncode == 1


def test_zero_collected_tests_is_a_failure_not_a_vacuous_pass(tmp_path):
    ws, tests = tmp_path / "ws", tmp_path / "tests"
    ws.mkdir()
    tests.mkdir()
    assert run(ws, tests).returncode == 1


def test_an_import_error_in_the_agents_code_is_a_failure(tmp_path):
    ws, tests = tmp_path / "ws", tmp_path / "tests"
    write(ws / "broken.py", "this is not python(\n")
    write(tests / "test_it.py", """
        import broken, unittest
        class T(unittest.TestCase):
            def test_x(self): pass
        """)
    assert run(ws, tests).returncode == 1


def test_isolated_mode_ignores_pythonpath_while_plain_mode_does_not(tmp_path):
    """Control for the -I flag: the PYTHONPATH vector is live without it."""
    ws, tests, evil = tmp_path / "ws", tmp_path / "tests", tmp_path / "evil"
    ws.mkdir()
    write(evil / "colorsys.py", "SHADOWED = True\n")
    write(tests / "test_it.py", """
        import colorsys, unittest
        class T(unittest.TestCase):
            def test_real_module(self): self.assertFalse(hasattr(colorsys, "SHADOWED"))
        """)
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(evil)}
    assert run(ws, tests, flags=("-I",), env=env).returncode == 0
    assert run(ws, tests, flags=(), env=env).returncode == 1
