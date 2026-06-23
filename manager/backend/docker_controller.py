"""Docker runtime control interface for managed agents.

This phase ships a fake implementation so API callers can integrate against a
stable shape before the real Docker API client lands.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol


class DockerController(Protocol):
    def start(self, agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def stop(self, agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def restart(self, agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def status(self, agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def logs(self, agent: dict[str, Any], tail: int = 200) -> dict[str, Any]:
        ...


class FakeDockerController:
    def __init__(self, docker_api_url: str = ""):
        self.docker_api_url = docker_api_url

    def start(self, agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("start", agent, "stubbed")

    def stop(self, agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("stop", agent, "stubbed")

    def restart(self, agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("restart", agent, "stubbed")

    def status(self, agent: dict[str, Any]) -> dict[str, Any]:
        return {
            "agent_id": self._agent_id(agent),
            "state": "unknown",
            "managed": False,
            "controller": "fake",
            "docker_api_url": self.docker_api_url,
            "checked_at": self._now(),
            "details": {
                "message": "Docker status is stubbed until the Docker API runtime phase.",
            },
        }

    def logs(self, agent: dict[str, Any], tail: int = 200) -> dict[str, Any]:
        return {
            "agent_id": self._agent_id(agent),
            "controller": "fake",
            "tail": tail,
            "lines": [],
            "details": {
                "message": "Docker logs are stubbed until the Docker API runtime phase.",
            },
        }

    def _operation(self, operation: str, agent: dict[str, Any], state: str) -> dict[str, Any]:
        return {
            "agent_id": self._agent_id(agent),
            "operation": operation,
            "accepted": True,
            "state": state,
            "controller": "fake",
            "docker_api_url": self.docker_api_url,
            "timestamp": self._now(),
            "details": {
                "message": "Docker control is stubbed until the Docker API runtime phase.",
            },
        }

    def _agent_id(self, agent: dict[str, Any]) -> str:
        return str(agent.get("id") or agent.get("name") or "")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
