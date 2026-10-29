import os

import pytest

from agenteval.sandbox import ProcessSandbox
from agenteval.tools import (
    Bash,
    ListDir,
    PathEscape,
    ReadFile,
    ToolBox,
    WriteFile,
    clip,
    safe_path,
)


@pytest.fixture
def ws(tmp_path):
    path = tmp_path / "ws"
    path.mkdir()
    return path


@pytest.fixture
def tools(ws):
    return ToolBox(ws, ProcessSandbox(), command_timeout=10, max_observation_chars=500)


def test_write_then_read_roundtrip_and_list(tools):
    assert tools.execute(WriteFile("a/b.txt", "hello")).ok
    assert tools.execute(ReadFile("a/b.txt")).text == "hello"
    assert tools.execute(ListDir(".")).text == "a/"
    assert tools.execute(ListDir("a")).text == "b.txt"


def test_internal_scratch_directories_are_not_listed(tools):
    tools.execute(Bash("true"))  # creates .home and .tmp
    assert tools.execute(ListDir(".")).text == "(empty)"


@pytest.mark.parametrize("bad", ["../outside.txt", "/etc/passwd", "a/../../x", "/"])
def test_paths_outside_the_workspace_are_refused(tools, bad):
    assert not tools.execute(ReadFile(bad)).ok
    assert not tools.execute(WriteFile(bad, "x")).ok
    assert "outside the workspace" in tools.execute(ReadFile(bad)).text


def test_a_symlink_to_outside_cannot_be_followed_by_file_tools(tools, ws, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("do not read")
    os.symlink(outside, ws / "link.txt")
    os.symlink(tmp_path, ws / "dirlink")
    assert not tools.execute(ReadFile("link.txt")).ok
    assert not tools.execute(WriteFile("link.txt", "x")).ok
    assert not tools.execute(WriteFile("dirlink/new.txt", "x")).ok
    assert not tools.execute(ListDir("dirlink")).ok
    assert outside.read_text() == "do not read" and not (tmp_path / "new.txt").exists()


def test_safe_path_allows_nested_and_absolute_paths_inside(ws):
    assert safe_path(ws, "x/y") == ws.resolve() / "x" / "y"
    assert safe_path(ws, str(ws / "z")) == ws.resolve() / "z"
    with pytest.raises(PathEscape):
        safe_path(ws, "..")


def test_missing_binary_and_directory_cases_are_observations_not_exceptions(tools):
    assert "no such file" in tools.execute(ReadFile("nope")).text
    assert "not a directory" in tools.execute(ListDir("nope")).text
    tools.execute(WriteFile("d/f", "x"))
    assert "is a directory" in tools.execute(WriteFile("d", "x")).text
    assert not tools.execute(WriteFile(".", "x")).ok


def test_binary_files_are_not_dumped(tools, ws):
    (ws / "blob").write_bytes(b"\x00\x01\x02binary")
    assert "binary file" in tools.execute(ReadFile("blob")).text


def test_oversized_writes_and_reads_are_limited(ws):
    small = ToolBox(ws, ProcessSandbox(), max_file_bytes=100)
    assert not small.execute(WriteFile("big", "x" * 101)).ok
    (ws / "long").write_text("y" * 500)
    assert "[file truncated]" in small.execute(ReadFile("long")).text


def test_bash_reports_exit_code_and_streams(tools):
    obs = tools.execute(Bash("echo out; echo err >&2; exit 4"))
    assert obs.exit_code == 4 and not obs.ok
    assert "out" in obs.text and "[stderr]" in obs.text and "[exit code 4]" in obs.text


def test_bash_timeout_is_reported_to_the_agent(ws):
    tb = ToolBox(ws, ProcessSandbox(), command_timeout=0.5)
    obs = tb.execute(Bash("sleep 20"))
    assert obs.timed_out and "timed out" in obs.text


def test_remaining_episode_time_caps_the_command_timeout(tools):
    obs = tools.execute(Bash("sleep 20"), time_left=0.4)
    assert obs.timed_out and obs.duration < 5


def test_long_observations_keep_both_ends(tools):
    obs = tools.execute(Bash("seq 1 5000"))
    assert len(obs.text) < 700 and "characters omitted" in obs.text
    assert obs.text.startswith("1\n") and "[exit code 0]" in obs.text


def test_clip_behaviour():
    assert clip("short", 100) == "short"
    head, tail = clip("a" * 1000, 100).split("\n[... 900 characters omitted ...]\n")
    assert len(head) + len(tail) == 100 and head == "a" * 60 and tail == "a" * 40


def test_unsupported_actions_are_reported(tools):
    assert not tools.execute(object()).ok
