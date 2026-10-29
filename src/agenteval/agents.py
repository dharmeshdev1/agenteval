"""Agent interface and the baseline agents used to calibrate the harness."""

from __future__ import annotations

from typing import Protocol

from agenteval.task import Task
from agenteval.tools import Action, Bash, Finish, Step


class Agent(Protocol):
    name: str

    def start(self, instruction: str) -> None:
        """Called once per episode with the task instruction."""

    def act(self, history: list[Step]) -> Action:
        """Choose the next action given every step so far."""


class NullAgent:
    """Does nothing. A task this agent passes is broken, because nothing needed doing."""

    name = "null"

    def start(self, instruction: str) -> None:
        pass

    def act(self, history: list[Step]) -> Action:
        return Finish("nothing to do")


class OracleAgent:
    """Applies the task's known-good solution through the normal shell tool.

    A task this agent fails is broken, because a valid solution does not pass.
    """

    name = "oracle"

    def __init__(self, task: Task) -> None:
        script = task.oracle_dir / "solve.sh"
        if not script.is_file():
            raise FileNotFoundError(f"{task.id}: oracle/solve.sh is missing")
        self._script = script.read_text()

    def start(self, instruction: str) -> None:
        pass

    def act(self, history: list[Step]) -> Action:
        return Bash(self._script) if not history else Finish("oracle solution applied")


class ScriptedAgent:
    """Replays a fixed list of actions. For tests and for building adversarial cases."""

    name = "scripted"

    def __init__(self, actions: list[Action]) -> None:
        self._actions = list(actions)

    def start(self, instruction: str) -> None:
        self.instruction = instruction

    def act(self, history: list[Step]) -> Action:
        return self._actions.pop(0) if self._actions else Finish("script exhausted")
