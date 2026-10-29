import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agenteval.llm import (
    TOOLS,
    AgentError,
    AnthropicAgent,
    InvalidToolCall,
    make_llm_factory,
)
from agenteval.runner import PASSED, run_episode
from agenteval.tools import Bash, Finish, ListDir, Observation, ReadFile, Step, WriteFile
from tests.conftest import FIXED


class MockAPI:
    """A local stand-in for the Messages API that replays scripted replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                headers = {k.lower(): v for k, v in self.headers.items()}
                outer.requests.append({"headers": headers, "body": body})
                reply = outer.replies.pop(0) if outer.replies else {"status": 500, "json": {}}
                status = reply.get("status", 200)
                payload = json.dumps(reply.get("json", {})).encode()
                self.send_response(status)
                for k, v in reply.get("headers", {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def tool_use(name, tool_input, tool_id="tu_1", **extra):
    return {"json": {
        "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}],
        "stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 5}, **extra}}


def agent_for(api, **kw):
    return AnthropicAgent("test-model", "sk-test-key", api.url, sleep=lambda s: None, **kw)


@pytest.fixture
def api():
    servers = []

    def make(replies):
        server = MockAPI(replies)
        servers.append(server)
        return server

    yield make
    for s in servers:
        s.close()


def test_request_carries_the_model_tools_system_prompt_and_credentials(api):
    server = api([tool_use("bash", {"command": "ls"})])
    agent = agent_for(server)
    agent.start("Fix the bug.")
    action = agent.act([])
    req = server.requests[0]
    assert action == Bash("ls")
    assert req["headers"]["x-api-key"] == "sk-test-key"
    assert req["headers"]["anthropic-version"] == "2023-06-01"
    body = req["body"]
    assert body["model"] == "test-model" and body["messages"] == [
        {"role": "user", "content": "Fix the bug."}
    ]
    names = {t["name"] for t in body["tools"]}
    assert names == {"bash", "read_file", "write_file", "list_dir", "finish"}
    assert "hidden checks" in body["system"] and body["temperature"] == 0.0


def test_the_observation_is_returned_as_a_tool_result_with_the_matching_id(api):
    server = api(
        [tool_use("bash", {"command": "ls"}, "tu_A"), tool_use("finish", {"message": "ok"})]
    )
    agent = agent_for(server)
    agent.start("task")
    first = agent.act([])
    obs = Observation("file.txt\n[exit code 0]", ok=True)
    assert agent.act([Step(first, obs)]) == Finish("ok")
    second = server.requests[1]["body"]["messages"]
    assert second[1]["role"] == "assistant" and second[1]["content"][0]["id"] == "tu_A"
    result = second[2]["content"][0]
    assert result == {"type": "tool_result", "tool_use_id": "tu_A",
                      "content": "file.txt\n[exit code 0]", "is_error": False}


def test_failed_observations_are_marked_as_errors(api):
    server = api([tool_use("bash", {"command": "false"}), tool_use("finish", {})])
    agent = agent_for(server)
    agent.start("t")
    step = Step(agent.act([]), Observation("[exit code 1]", ok=False))
    agent.act([step])
    assert server.requests[1]["body"]["messages"][2]["content"][0]["is_error"] is True


@pytest.mark.parametrize(
    "name,tool_input,expected",
    [
        ("read_file", {"path": "a.py"}, ReadFile("a.py")),
        ("write_file", {"path": "a.py", "content": "x"}, WriteFile("a.py", "x")),
        ("list_dir", {}, ListDir(".")),
        ("list_dir", {"path": "src"}, ListDir("src")),
        ("finish", {}, Finish("")),
    ],
)
def test_each_tool_maps_to_its_action(api, name, tool_input, expected):
    agent = agent_for(api([tool_use(name, tool_input)]))
    agent.start("t")
    assert agent.act([]) == expected


@pytest.mark.parametrize(
    "name,tool_input",
    [("bash", {}), ("bash", {"command": 5}), ("write_file", {"path": "a"}), ("nope", {}),
     ("bash", "not-an-object")],
)
def test_malformed_tool_calls_become_invalid_actions_not_crashes(api, name, tool_input):
    agent = agent_for(api([tool_use(name, tool_input)]))
    agent.start("t")
    assert isinstance(agent.act([]), InvalidToolCall)


def test_a_text_only_reply_is_treated_as_finishing(api):
    reply = {
        "json": {"content": [{"type": "text", "text": "All done."}], "stop_reason": "end_turn"}
    }
    agent = agent_for(api([reply]))
    agent.start("t")
    assert agent.act([]) == Finish("All done.")


def test_extra_tool_calls_in_one_turn_get_error_results_so_the_conversation_stays_valid(api):
    two = {"json": {"content": [
        {"type": "tool_use", "id": "t1", "name": "bash", "input": {"command": "ls"}},
        {"type": "tool_use", "id": "t2", "name": "bash", "input": {"command": "pwd"}},
    ], "stop_reason": "tool_use"}}
    server = api([two, tool_use("finish", {})])
    agent = agent_for(server)
    agent.start("t")
    first = agent.act([])
    assert first == Bash("ls")
    agent.act([Step(first, Observation("out", ok=True))])
    results = server.requests[1]["body"]["messages"][2]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert results[0]["is_error"] is False and results[1]["is_error"] is True


def test_a_reply_cut_off_by_max_tokens_is_never_executed(api):
    truncated = tool_use(
        "bash", {"command": "rm -rf important && echo par"}, stop_reason="max_tokens"
    )
    agent = agent_for(api([truncated]))
    agent.start("t")
    action = agent.act([])
    assert isinstance(action, InvalidToolCall) and "cut off" in action.reason


def test_token_usage_is_accumulated(api):
    server = api([tool_use("bash", {"command": "ls"}), tool_use("finish", {})])
    agent = agent_for(server)
    agent.start("t")
    step = Step(agent.act([]), Observation("x"))
    agent.act([step])
    assert agent.usage == {"input_tokens": 20, "output_tokens": 10, "calls": 2}


def test_transient_errors_are_retried_with_backoff(api):
    delays = []
    server = api([{"status": 429, "headers": {"retry-after": "3"}}, {"status": 503},
                  tool_use("finish", {"message": "ok"})])
    agent = AnthropicAgent("m", "k", server.url, sleep=delays.append)
    agent.start("t")
    assert agent.act([]) == Finish("ok")
    assert delays == [3.0, 2.0] and len(server.requests) == 3


def test_retries_are_bounded(api):
    server = api([{"status": 500}] * 10)
    agent = AnthropicAgent("m", "k", server.url, max_retries=2, sleep=lambda s: None)
    agent.start("t")
    with pytest.raises(AgentError, match="after 3 attempts"):
        agent.act([])
    assert len(server.requests) == 3


def test_client_errors_are_not_retried_and_never_leak_the_key(api):
    server = api([{"status": 401, "json": {"error": "invalid key"}}])
    agent = AnthropicAgent("m", "sk-super-secret", server.url, sleep=lambda s: None)
    agent.start("t")
    with pytest.raises(AgentError) as exc:
        agent.act([])
    assert "sk-super-secret" not in str(exc.value) and "401" in str(exc.value)
    assert len(server.requests) == 1


def test_unreachable_server_is_an_agent_error_that_does_not_leak_the_key():
    agent = AnthropicAgent("m", "sk-secret", "http://127.0.0.1:9", max_retries=1,
                           timeout=1, sleep=lambda s: None)
    agent.start("t")
    with pytest.raises(AgentError) as exc:
        agent.act([])
    assert "sk-secret" not in str(exc.value)
    assert isinstance(exc.value, RuntimeError) and not isinstance(exc.value, urllib.error.URLError)


def test_start_resets_conversation_and_usage_between_episodes(api):
    server = api([tool_use("finish", {}), tool_use("finish", {})])
    agent = agent_for(server)
    agent.start("first")
    agent.act([])
    agent.start("second")
    agent.act([])
    assert server.requests[1]["body"]["messages"] == [{"role": "user", "content": "second"}]
    assert agent.usage["calls"] == 1


def test_factory_requires_a_model_and_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="--model"):
        make_llm_factory(None, "http://x", 0.0, 100)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        make_llm_factory("m", "http://x", 0.0, 100)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    name, factory = make_llm_factory("m", "http://x", 0.0, 100)
    assert name == "llm:m" and factory(None).model == "m"


def test_tool_schemas_are_well_formed():
    for tool in TOOLS:
        schema = tool["input_schema"]
        assert schema["type"] == "object" and set(schema["required"]) <= set(schema["properties"])


def test_a_full_episode_driven_through_the_model_adapter_passes(api, task, sandbox):
    server = api([
        tool_use("read_file", {"path": "calc.py"}, "t1"),
        tool_use("write_file", {"path": "calc.py", "content": FIXED}, "t2"),
        tool_use("finish", {"message": "fixed add"}, "t3"),
    ])
    agent = agent_for(server)
    episode = run_episode(task, agent, sandbox)
    assert episode.status == PASSED and len(episode.steps) == 3
    assert episode.usage == {"input_tokens": 30, "output_tokens": 15, "calls": 3}
    sent = json.dumps(server.requests[2]["body"])
    assert "a - b" in sent  # the file contents reached the model as a tool result
    assert "sk-test-key" not in json.dumps(episode.to_dict())


def test_an_api_failure_mid_episode_is_an_agent_error_not_a_harness_failure(api, task, sandbox):
    server = api([tool_use("list_dir", {}), {"status": 400, "json": {"error": "bad request"}}])
    episode = run_episode(task, agent_for(server), sandbox)
    assert episode.terminated_by == "agent_error" and episode.status == "failed"
    assert "400" in episode.error
