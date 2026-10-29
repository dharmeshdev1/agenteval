import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from agenteval.sandbox import (
    Limits,
    ProcessSandbox,
    SeatbeltSandbox,
    choose_sandbox,
    clean_env,
    run_process,
)

needs_seatbelt = pytest.mark.skipif(
    not SeatbeltSandbox.available(), reason="needs macOS sandbox-exec"
)


@pytest.fixture
def ws(tmp_path):
    path = tmp_path / "ws"
    path.mkdir()
    return path


@pytest.fixture(params=["process", pytest.param("seatbelt", marks=needs_seatbelt)])
def sandbox(request, tmp_path):
    if request.param == "process":
        return ProcessSandbox()
    hidden = tmp_path / "hidden"
    hidden.mkdir(exist_ok=True)
    return SeatbeltSandbox(hidden=[hidden])


# ---- behaviour every backend must have ------------------------------------------------


def test_runs_a_command_in_the_workspace(sandbox, ws):
    res = sandbox.shell("pwd && echo hello", ws)
    assert res.ok and "hello" in res.stdout
    assert Path(res.stdout.splitlines()[0]).resolve() == ws.resolve()


def test_exit_code_and_streams_are_reported_separately(sandbox, ws):
    res = sandbox.shell("echo out; echo err >&2; exit 3", ws)
    assert res.returncode == 3 and not res.ok
    assert res.stdout.strip() == "out" and res.stderr.strip() == "err"


def test_stdin_is_closed_so_interactive_programs_cannot_hang(sandbox, ws):
    res = sandbox.shell("cat", ws, timeout=5)
    assert res.ok and res.stdout == "" and not res.timed_out


def test_environment_is_scrubbed_of_parent_secrets(sandbox, ws, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    res = sandbox.shell("env", ws)
    assert "secret" not in res.stdout.lower()
    assert "HOME=" + str(ws.resolve() / ".home") in res.stdout


def test_a_timeout_kills_the_command(sandbox, ws):
    res = sandbox.shell("sleep 30", ws, timeout=0.5)
    assert res.timed_out and not res.ok and res.duration < 5


def test_a_timeout_kills_the_whole_process_tree(sandbox, ws):
    marker = ws / "survivor.txt"
    sandbox.shell(f"(sleep 1.5; echo alive > {marker}) & sleep 30", ws, timeout=0.4)
    time.sleep(2.5)
    assert not marker.exists(), "a background child outlived the step"


def test_background_processes_are_killed_even_after_a_normal_exit(sandbox, ws):
    marker = ws / "daemon.txt"
    res = sandbox.shell(f"(sleep 1.5; echo alive > {marker}) & echo done", ws, timeout=10)
    assert res.ok and "done" in res.stdout and not res.timed_out
    time.sleep(2.5)
    assert not marker.exists(), "a daemonised child survived the step"


def test_a_background_child_holding_the_pipes_does_not_cause_a_false_timeout(sandbox, ws):
    res = sandbox.shell("sleep 20 & echo started", ws, timeout=10)
    assert res.ok and not res.timed_out and res.duration < 5


def test_output_is_capped_and_the_producer_is_stopped(sandbox, ws):
    res = sandbox.shell("yes | head -c 5000000", ws, max_output=10_000, timeout=20)
    assert res.output_truncated and len(res.stdout) <= 10_000


def test_infinite_output_does_not_hang_or_exhaust_memory(sandbox, ws):
    res = sandbox.shell("yes", ws, max_output=10_000, timeout=20)
    assert res.output_truncated and res.duration < 15


def test_file_size_limit_stops_runaway_writes(sandbox, ws):
    res = sandbox.shell(
        "head -c 5000000 /dev/zero > big.bin", ws, limits=Limits(max_file_bytes=1_000_000)
    )
    assert not res.ok
    assert (ws / "big.bin").stat().st_size <= 1_000_000


def test_cpu_limit_stops_a_busy_loop(sandbox, ws):
    res = sandbox.shell("while :; do :; done", ws, timeout=20, limits=Limits(cpu_seconds=1))
    assert not res.ok and not res.timed_out and res.duration < 10


def test_invalid_utf8_output_does_not_crash_the_harness(sandbox, ws):
    res = sandbox.shell("printf '\\377\\376ok'", ws)
    assert res.ok and "ok" in res.stdout


def test_missing_executable_is_a_clean_failure(ws):
    res = run_process(["/definitely/not/a/binary"], ws, clean_env(ws), 5, 1000)
    assert res.returncode is None and "failed to start" in res.stderr


def test_clean_env_contains_only_what_it_should(ws):
    env = clean_env(ws, {"EXTRA": "1"})
    assert env["EXTRA"] == "1" and env["PATH"] and "USER" not in env
    assert all(not k.startswith(("ANTHROPIC", "AWS", "OPENAI")) for k in env)


# ---- isolation that only the seatbelt backend provides --------------------------------


@needs_seatbelt
def test_seatbelt_blocks_writes_outside_the_workspace(ws, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sb = SeatbeltSandbox()
    inside = sb.shell("echo ok > inside.txt", ws)
    escape = sb.shell(f"echo pwned > {outside}/escape.txt", ws)
    assert inside.ok and (ws / "inside.txt").exists()
    assert not escape.ok and not (outside / "escape.txt").exists()


@needs_seatbelt
def test_seatbelt_blocks_writes_to_the_home_directory(ws):
    target = Path.home() / ".agenteval_escape_probe"
    res = SeatbeltSandbox().shell(f"echo x > {target}", ws)
    try:
        assert not res.ok and not target.exists()
    finally:
        target.unlink(missing_ok=True)


@needs_seatbelt
def test_seatbelt_blocks_reading_hidden_paths(ws, tmp_path):
    hidden = tmp_path / "verifier"
    hidden.mkdir()
    (hidden / "answers.txt").write_text("the hidden answer")
    sb = SeatbeltSandbox(hidden=[hidden])
    res = sb.shell(f"cat {hidden}/answers.txt", ws)
    assert not res.ok and "hidden answer" not in res.stdout


@needs_seatbelt
def test_seatbelt_blocks_listing_a_hidden_directory(ws, tmp_path):
    hidden = tmp_path / "verifier"
    hidden.mkdir()
    (hidden / "x").write_text("1")
    res = SeatbeltSandbox(hidden=[hidden]).shell(f"ls {hidden}", ws)
    assert not res.ok


@needs_seatbelt
def test_seatbelt_blocks_reading_home(ws):
    res = SeatbeltSandbox().shell(f"ls {Path.home()}", ws)
    assert not res.ok


@needs_seatbelt
def test_seatbelt_blocks_network_while_the_same_connection_works_outside(ws):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    port = server.getsockname()[1]

    def accept_quietly():
        try:
            while True:
                server.accept()
        except OSError:  # the listening socket is closed at the end of the test
            pass

    threading.Thread(target=accept_quietly, daemon=True).start()
    snippet = (
        f"import socket; socket.create_connection(('127.0.0.1', {port}), 3); print('connected')"
    )
    # Control: the identical connection succeeds without a sandbox, so a failure below is
    # caused by the sandbox and not by the test setup.
    assert socket.create_connection(("127.0.0.1", port), 3)
    res = SeatbeltSandbox().run(["/usr/bin/python3", "-c", snippet], ws, timeout=10)
    assert "connected" not in res.stdout and not res.ok
    server.close()


@needs_seatbelt
def test_seatbelt_blocks_escape_through_a_symlink(ws, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sb = SeatbeltSandbox()
    res = sb.shell(f"ln -s {outside} link && echo pwned > link/escape.txt", ws)
    assert not (outside / "escape.txt").exists()
    assert not res.ok


@needs_seatbelt
def test_seatbelt_still_runs_ordinary_programs(ws):
    sb = SeatbeltSandbox()
    py = sb.run(["/usr/bin/python3", "-c", "print(sum(range(100)))"], ws)
    git = sb.shell("git init -q . && git status --short && echo git-ok", ws)
    assert py.ok and py.stdout.strip() == "4950"
    assert git.ok and "git-ok" in git.stdout


@needs_seatbelt
def test_seatbelt_reading_the_workspace_works_even_when_it_lives_under_home(tmp_path):
    ws = Path.home() / f".agenteval_ws_probe_{os.getpid()}"
    ws.mkdir()
    try:
        (ws / "data.txt").write_text("readable")
        res = SeatbeltSandbox().shell("cat data.txt", ws)
        assert res.ok and res.stdout == "readable"
    finally:
        for f in ws.rglob("*"):
            if f.is_file():
                f.unlink()
        for d in sorted((p for p in ws.rglob("*") if p.is_dir()), reverse=True):
            d.rmdir()
        ws.rmdir()


@needs_seatbelt
def test_isolation_is_reported_truthfully():
    assert SeatbeltSandbox().isolation.level == "isolated"
    assert ProcessSandbox().isolation.level == "unconfined"


def test_choose_sandbox_refuses_to_run_unconfined_unless_asked(monkeypatch):
    monkeypatch.setattr(SeatbeltSandbox, "available", staticmethod(lambda: False))
    with pytest.raises(RuntimeError, match="allow_unconfined"):
        choose_sandbox([])
    assert isinstance(choose_sandbox([], allow_unconfined=True), ProcessSandbox)


def test_choose_sandbox_prefers_isolation_when_available(monkeypatch):
    monkeypatch.setattr(SeatbeltSandbox, "available", staticmethod(lambda: True))
    assert isinstance(choose_sandbox([Path("/tmp")]), SeatbeltSandbox)


def test_platform_marker():
    assert sys.platform in {"darwin", "linux", "win32"}
