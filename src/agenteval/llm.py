"""An agent backed by a language model, over the Anthropic Messages API with tool use.

The API key is read from ``ANTHROPIC_API_KEY`` in the harness process only. It is never
passed to the sandbox, never written to results, and never included in error messages.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from agenteval.task import Task
from agenteval.tools import Action, Bash, Finish, ListDir, ReadFile, Step, WriteFile

API_VERSION = "2023-06-01"
RETRYABLE = {408, 409, 429, 500, 502, 503, 504, 529}

SYSTEM_PROMPT = (
    "You are working in a sandboxed directory on a task. You can only act through the tools "
    "provided.\n\n"
    "- Your commands run in the task's working directory with no network access.\n"
    "- Use bash to explore, edit files and run tests. Use read_file, write_file and list_dir "
    "for files.\n"
    "- Your work is judged afterwards by hidden checks that go beyond the visible tests, so "
    "solve the problem properly instead of special-casing examples. Do not edit files the "
    "task says are off limits.\n"
    "- Call finish when you believe the task is complete, with a short summary."
)

def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {k: {"type": "string"} for k in properties},
            "required": required,
        },
    }


TOOLS = [
    _tool("bash", "Run a shell command in the working directory. Returns stdout, stderr and "
          "the exit code.", {"command": 1}, ["command"]),
    _tool("read_file", "Read a text file.", {"path": 1}, ["path"]),
    _tool("write_file", "Create or overwrite a text file.", {"path": 1, "content": 1},
          ["path", "content"]),
    _tool("list_dir", "List a directory.", {"path": 1}, []),
    _tool("finish", "Declare the task complete.", {"message": 1}, []),
]


class AgentError(RuntimeError):
    """The model API could not be used. Raised so the episode records an agent error."""


@dataclass(frozen=True)
class InvalidToolCall:
    """The model asked for something that is not a valid tool call."""

    reason: str


def _parse_tool_call(block: dict) -> Action | InvalidToolCall:
    name, args = block.get("name"), block.get("input")
    if not isinstance(args, dict):
        return InvalidToolCall(f"tool input for {name!r} must be an object")

    def text(key: str, required: bool = True, default: str = "") -> str | InvalidToolCall:
        value = args.get(key, None)
        if value is None and not required:
            return default
        if not isinstance(value, str):
            return InvalidToolCall(f"{name}: {key!r} must be a string")
        return value

    if name == "bash":
        cmd = text("command")
        return cmd if isinstance(cmd, InvalidToolCall) else Bash(cmd)
    if name == "read_file":
        path = text("path")
        return path if isinstance(path, InvalidToolCall) else ReadFile(path)
    if name == "write_file":
        path, content = text("path"), text("content")
        for bad in (path, content):
            if isinstance(bad, InvalidToolCall):
                return bad
        return WriteFile(path, content)
    if name == "list_dir":
        path = text("path", required=False, default=".")
        return path if isinstance(path, InvalidToolCall) else ListDir(path)
    if name == "finish":
        message = text("message", required=False)
        return message if isinstance(message, InvalidToolCall) else Finish(message)
    return InvalidToolCall(f"unknown tool {name!r}")


class AnthropicAgent:
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 5,
        timeout: float = 120.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.name = f"llm:{model}"
        self.model = model
        self._key = api_key
        self._url = base_url.rstrip("/") + "/v1/messages"
        self.temperature, self.max_tokens = temperature, max_tokens
        self.max_retries, self.timeout, self._sleep = max_retries, timeout, sleep
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
        self.messages: list[dict] = []
        self._pending: list[str] = []

    def start(self, instruction: str) -> None:
        self.messages = [{"role": "user", "content": instruction}]
        self._pending = []
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}

    def act(self, history: list[Step]) -> Action:
        if self._pending:
            self.messages.append({"role": "user", "content": self._tool_results(history)})
        reply = self._request()
        content = reply.get("content") or []
        self.messages.append({"role": "assistant", "content": content})

        calls = [b for b in content if b.get("type") == "tool_use"]
        self._pending = [b["id"] for b in calls]
        if not calls:  # the model replied with text only, so it considers itself done
            text = " ".join(b.get("text", "") for b in content if b.get("type") == "text")
            return Finish(text.strip())
        if reply.get("stop_reason") == "max_tokens":
            # The reply was cut off, so the tool input may be incomplete. Running a partial
            # shell command could do something other than what was meant, so refuse it.
            return InvalidToolCall(
                "your reply was cut off by the token limit before the tool call finished; "
                "keep replies shorter and repeat the call"
            )
        return _parse_tool_call(calls[0])

    # ------------------------------------------------------------------ internals

    def _tool_results(self, history: list[Step]) -> list[dict]:
        obs = history[-1].observation if history else None
        first, *rest = self._pending
        results = [{
            "type": "tool_result", "tool_use_id": first,
            "content": obs.text if obs else "no observation", "is_error": bool(obs and not obs.ok),
        }]
        results += [{
            "type": "tool_result", "tool_use_id": other, "is_error": True,
            "content": "Only one tool call per turn is executed. Repeat this call on its own.",
        } for other in rest]
        self._pending = []
        return results

    def _request(self) -> dict:
        body = json.dumps({
            "model": self.model, "max_tokens": self.max_tokens, "temperature": self.temperature,
            "system": SYSTEM_PROMPT, "tools": TOOLS, "messages": self.messages,
        }).encode()
        headers = {
            "content-type": "application/json", "x-api-key": self._key,
            "anthropic-version": API_VERSION,
        }
        last = "no attempt was made"
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(self._url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read())
                usage = data.get("usage") or {}
                self.usage["input_tokens"] += int(usage.get("input_tokens", 0))
                self.usage["output_tokens"] += int(usage.get("output_tokens", 0))
                self.usage["calls"] += 1
                return data
            except urllib.error.HTTPError as err:
                detail = err.read().decode("utf-8", errors="replace")[:200]
                last = f"HTTP {err.code}: {detail}"
                if err.code not in RETRYABLE:
                    raise AgentError(f"model API rejected the request ({last})") from None
                retry_after = err.headers.get("retry-after") if err.headers else None
                delay = float(retry_after) if retry_after and retry_after.isdigit() else None
            except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
                last, delay = f"{type(exc).__name__}", None
            if attempt < self.max_retries:
                self._sleep(delay if delay is not None else min(2.0**attempt, 30.0))
        raise AgentError(f"model API failed after {self.max_retries + 1} attempts ({last})")


def make_llm_factory(
    model: str | None, base_url: str, temperature: float, max_tokens: int
) -> tuple[str, Callable[[Task], AnthropicAgent]]:
    if not model:
        raise ValueError("--model is required for --agent llm")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("set ANTHROPIC_API_KEY in the environment to use --agent llm")
    return f"llm:{model}", lambda task: AnthropicAgent(
        model, key, base_url, temperature, max_tokens
    )
