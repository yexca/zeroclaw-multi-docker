"""Docker runtime control for manager-owned ZeroClaw agent containers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen

try:
    from agent_renderer import AgentRenderer
    from config_store import ConfigError, item_id, redact
    from config_validator import ConfigValidator
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from .agent_renderer import AgentRenderer
    from .config_store import ConfigError, item_id, redact
    from .config_validator import ConfigValidator


MANAGER_LABEL = "zeroclaw.manager"
AGENT_ID_LABEL = "zeroclaw.agent.id"
AGENT_NAME_LABEL = "zeroclaw.agent.name"
SPEC_HASH_LABEL = "zeroclaw.agent.spec_hash"
DEFAULT_IMAGE = "ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian"
CONTAINER_PORT = "42617/tcp"


class DockerController(Protocol):
    def start(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def stop(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def restart(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def delete(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def status(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def logs(self, config: dict[str, Any], agent: dict[str, Any], tail: int = 200) -> dict[str, Any]:
        ...


class DockerApiError(Exception):
    def __init__(self, status: int, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details or {}


class DockerApiClient:
    def __init__(self, base_url: str, timeout_secs: int = 30):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout_secs = timeout_secs

    def request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        query: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        url = urljoin(self.base_url, path.lstrip("/"))
        if query:
            url = f"{url}?{urlencode(query, doseq=True)}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_secs) as response:
                body = response.read()
                if raw:
                    return body
                if not body:
                    return {}
                content_type = response.headers.get("Content-Type", "")
                if "json" in content_type:
                    return json.loads(body.decode("utf-8"))
                return body.decode("utf-8", errors="replace")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            details: dict[str, Any] = {"status": exc.code, "body": body}
            try:
                decoded = json.loads(body)
                details["body"] = decoded
                message = decoded.get("message") or body
            except json.JSONDecodeError:
                message = body or exc.reason
            raise DockerApiError(exc.code, str(message), details) from exc
        except URLError as exc:
            raise DockerApiError(503, "Unable to reach Docker API proxy.", {"reason": str(exc.reason)}) from exc


class DockerApiController:
    def __init__(self, docker_api_url: str, project_root: Path, timeout_secs: int = 30):
        self.docker_api_url = docker_api_url
        self.project_root = project_root
        self.client = DockerApiClient(docker_api_url, timeout_secs=timeout_secs)
        self.renderer = AgentRenderer(project_root)
        self.validator = ConfigValidator(project_root)

    def start(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        self.validator.ensure_valid_for_start(config, agent)
        spec = self.build_container_spec(config, agent)
        self.ensure_network(spec.network_name)
        self.pull_image(spec.image)
        existing = self.find_container(spec)
        actions: list[str] = []

        if existing and not self.is_managed_container(existing, spec):
            raise ConfigError(
                "container_not_manager_owned",
                "Refusing to modify a container without the manager label.",
                {"container": spec.container_name},
                409,
            )

        if existing and self.needs_recreate(existing, spec):
            self.remove_container(existing["Id"], force=True)
            actions.append("recreated")
            existing = None

        if not existing:
            self.ensure_host_port_available(spec, exclude_container_id=None)
            created = self.create_container(spec)
            existing = self.inspect_container(created["Id"])
            actions.append("created")
        else:
            self.ensure_host_port_available(spec, exclude_container_id=existing.get("Id"))

        state = existing.get("State", {}) if isinstance(existing, dict) else {}
        if not state.get("Running"):
            self.client.request("POST", f"/containers/{existing['Id']}/start")
            actions.append("started")
            existing = self.inspect_container(existing["Id"])

        return self.operation_result("start", spec, existing, actions)

    def stop(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        spec = self.build_container_spec(config, agent)
        container = self.require_managed_container(spec)
        state = container.get("State", {})
        actions: list[str] = []
        if state.get("Running"):
            self.client.request("POST", f"/containers/{container['Id']}/stop", query={"t": 10})
            actions.append("stopped")
            container = self.inspect_container(container["Id"])
        return self.operation_result("stop", spec, container, actions or ["already_stopped"])

    def restart(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        self.validator.ensure_valid_for_start(config, agent)
        start_result = self.start(config, agent)
        spec = self.build_container_spec(config, agent)
        container = self.require_managed_container(spec)
        self.client.request("POST", f"/containers/{container['Id']}/restart", query={"t": 10})
        container = self.inspect_container(container["Id"])
        actions = list(start_result.get("actions", [])) + ["restarted"]
        return self.operation_result("restart", spec, container, actions)

    def delete(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        spec = self.build_container_spec(config, agent)
        container = self.find_container(spec)
        if not container:
            return {
                "agent_id": spec.agent_id,
                "agent_name": spec.agent_name,
                "container_name": spec.container_name,
                "operation": "delete",
                "actions": ["not_found"],
                "state": "absent",
                "managed": False,
                "controller": "docker-api",
            }
        if not self.is_managed_container(container, spec):
            raise ConfigError(
                "container_not_manager_owned",
                "Refusing to delete a container without the manager label.",
                {"container": spec.container_name},
                409,
            )
        self.remove_container(container["Id"], force=True)
        return {
            "agent_id": spec.agent_id,
            "agent_name": spec.agent_name,
            "container_name": spec.container_name,
            "operation": "delete",
            "actions": ["deleted"],
            "state": "absent",
            "managed": True,
            "controller": "docker-api",
            "timestamp": self._now(),
        }

    def status(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        spec = self.build_container_spec(config, agent)
        container = self.find_container(spec)
        if not container:
            return {
                "agent_id": spec.agent_id,
                "agent_name": spec.agent_name,
                "container_name": spec.container_name,
                "state": "absent",
                "running": False,
                "managed": False,
                "controller": "docker-api",
                "checked_at": self._now(),
            }
        managed = self.is_managed_container(container, spec)
        state = container.get("State", {})
        config_labels = container.get("Config", {}).get("Labels") or {}
        return {
            "agent_id": spec.agent_id,
            "agent_name": spec.agent_name,
            "container_id": container.get("Id"),
            "container_name": spec.container_name,
            "image": container.get("Config", {}).get("Image"),
            "state": state.get("Status") or "unknown",
            "running": bool(state.get("Running")),
            "managed": managed,
            "needs_recreate": managed and self.needs_recreate(container, spec),
            "spec_hash": config_labels.get(SPEC_HASH_LABEL),
            "expected_spec_hash": spec.spec_hash,
            "ports": container.get("NetworkSettings", {}).get("Ports") or {},
            "controller": "docker-api",
            "checked_at": self._now(),
        }

    def logs(self, config: dict[str, Any], agent: dict[str, Any], tail: int = 200) -> dict[str, Any]:
        self.configure_client(config)
        spec = self.build_container_spec(config, agent)
        container = self.require_managed_container(spec)
        body = self.client.request(
            "GET",
            f"/containers/{container['Id']}/logs",
            query={"stdout": 1, "stderr": 1, "timestamps": 1, "tail": tail},
            raw=True,
        )
        text = decode_docker_log_stream(body)
        return {
            "agent_id": spec.agent_id,
            "agent_name": spec.agent_name,
            "container_name": spec.container_name,
            "controller": "docker-api",
            "tail": tail,
            "lines": text.splitlines(),
        }

    def build_container_spec(self, config: dict[str, Any], agent: dict[str, Any]) -> "ContainerSpec":
        resolved = self.renderer.resolve_agent(config, agent)
        agent_identifier = item_id(resolved)
        if not agent_identifier:
            raise ConfigError("invalid_agent", "Agent requires an id or name.")
        agent_name = str(resolved.get("name") or agent_identifier)
        safe_name = safe_container_part(agent_name)
        host_port = resolved.get("host_port")
        if not isinstance(host_port, int):
            raise ConfigError("invalid_agent", "Agent host_port must be an integer.", {"agent": agent_identifier})

        docker_config = config.get("docker") if isinstance(config.get("docker"), dict) else {}
        paths = config.get("paths") if isinstance(config.get("paths"), dict) else {}
        defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}

        image = str(resolved.get("image") or defaults.get("zeroclaw_image") or os.getenv("ZEROCLAW_IMAGE") or DEFAULT_IMAGE)
        project_name = str(docker_config.get("project_name") or "zeroclaw-matrix-multi")
        network_name = str(docker_config.get("runtime_network") or f"{project_name}_default")
        project_root = Path(str(paths.get("host_project_dir") or os.getenv("HOST_PROJECT_DIR") or self.project_root)).resolve()
        instances_dir = Path(str(paths.get("host_instances_dir") or project_root / "instances")).resolve()
        bootstrap_dir = Path(str(paths.get("host_bootstrap_dir") or project_root / "bootstrap")).resolve()
        env = self.renderer.render_env(config, resolved)
        matrix_host_ip = env.get("MATRIX_HOST_IP", "127.0.0.1")

        labels = {
            MANAGER_LABEL: "true",
            AGENT_ID_LABEL: str(agent_identifier),
            AGENT_NAME_LABEL: agent_name,
        }
        spec_payload = {
            "image": image,
            "agent_id": agent_identifier,
            "agent_name": agent_name,
            "host_port": host_port,
            "network_name": network_name,
            "env": env,
            "mounts": [
                {"Type": "bind", "Source": str(bootstrap_dir), "Target": "/bootstrap", "ReadOnly": True},
                {"Type": "bind", "Source": str(instances_dir / safe_name), "Target": "/zeroclaw-data"},
            ],
            "extra_hosts": [f"host.docker.internal:host-gateway", f"matrix-host:{matrix_host_ip}"],
        }
        spec_hash = stable_hash(spec_payload)
        labels[SPEC_HASH_LABEL] = spec_hash
        return ContainerSpec(
            agent_id=str(agent_identifier),
            agent_name=agent_name,
            safe_name=safe_name,
            container_name=f"zeroclaw-matrix-{safe_name}",
            image=image,
            host_port=host_port,
            network_name=network_name,
            bootstrap_dir=bootstrap_dir,
            instance_dir=instances_dir / safe_name,
            environment=env,
            labels=labels,
            extra_hosts=spec_payload["extra_hosts"],
            spec_hash=spec_hash,
        )

    def configure_client(self, config: dict[str, Any]) -> None:
        docker_config = config.get("docker") if isinstance(config.get("docker"), dict) else {}
        proxy_url = str(docker_config.get("proxy_url") or self.docker_api_url)
        if proxy_url != self.docker_api_url:
            self.docker_api_url = proxy_url
            self.client = DockerApiClient(proxy_url, timeout_secs=self.client.timeout_secs)

    def create_container(self, spec: "ContainerSpec") -> dict[str, Any]:
        spec.instance_dir.mkdir(parents=True, exist_ok=True)
        (spec.instance_dir / "workspace").mkdir(parents=True, exist_ok=True)
        payload = {
            "Image": spec.image,
            "User": "0:0",
            "WorkingDir": "/zeroclaw-data/workspace",
            "Entrypoint": ["/bin/sh", "/bootstrap/render-config.sh"],
            "Env": [f"{key}={value}" for key, value in sorted(spec.environment.items())],
            "Labels": spec.labels,
            "ExposedPorts": {CONTAINER_PORT: {}},
            "HostConfig": {
                "RestartPolicy": {"Name": "unless-stopped"},
                "Mounts": [
                    {"Type": "bind", "Source": str(spec.bootstrap_dir), "Target": "/bootstrap", "ReadOnly": True},
                    {"Type": "bind", "Source": str(spec.instance_dir), "Target": "/zeroclaw-data"},
                ],
                "PortBindings": {
                    CONTAINER_PORT: [{"HostIp": "127.0.0.1", "HostPort": str(spec.host_port)}],
                },
                "ExtraHosts": spec.extra_hosts,
            },
            "NetworkingConfig": {
                "EndpointsConfig": {
                    spec.network_name: {},
                },
            },
        }
        return self.client.request("POST", "/containers/create", payload=payload, query={"name": spec.container_name})

    def ensure_network(self, network_name: str) -> None:
        try:
            self.client.request("GET", f"/networks/{quote(network_name, safe='')}")
            return
        except DockerApiError as exc:
            if exc.status != 404:
                raise
        self.client.request(
            "POST",
            "/networks/create",
            payload={
                "Name": network_name,
                "CheckDuplicate": True,
                "Labels": {MANAGER_LABEL: "true"},
            },
        )

    def pull_image(self, image: str) -> None:
        query = {"fromImage": image}
        if ":" in image.rsplit("/", 1)[-1]:
            repository, tag = image.rsplit(":", 1)
            query = {"fromImage": repository, "tag": tag}
        self.client.request("POST", "/images/create", query=query, raw=True)

    def find_container(self, spec: "ContainerSpec") -> dict[str, Any] | None:
        try:
            return self.inspect_container(spec.container_name)
        except DockerApiError as exc:
            if exc.status == 404:
                return None
            raise

    def inspect_container(self, identifier: str) -> dict[str, Any]:
        return self.client.request("GET", f"/containers/{quote(identifier, safe='')}/json")

    def require_managed_container(self, spec: "ContainerSpec") -> dict[str, Any]:
        container = self.find_container(spec)
        if not container:
            raise ConfigError("container_not_found", "Managed agent container was not found.", {"container": spec.container_name}, 404)
        if not self.is_managed_container(container, spec):
            raise ConfigError(
                "container_not_manager_owned",
                "Refusing to operate on a container without the manager label.",
                {"container": spec.container_name},
                409,
            )
        return container

    def remove_container(self, container_id: str, force: bool = False) -> None:
        self.client.request("DELETE", f"/containers/{container_id}", query={"force": 1 if force else 0, "v": 0})

    def ensure_host_port_available(self, spec: "ContainerSpec", exclude_container_id: str | None) -> None:
        filters = json.dumps({"publish": [str(spec.host_port)]})
        containers = self.client.request("GET", "/containers/json", query={"all": 1, "filters": filters})
        for container in containers:
            container_id = container.get("Id")
            if exclude_container_id and container_id == exclude_container_id:
                continue
            ports = container.get("Ports") or []
            for port in ports:
                if port.get("PublicPort") == spec.host_port and port.get("IP") in {"127.0.0.1", "0.0.0.0", "::"}:
                    raise ConfigError(
                        "host_port_conflict",
                        "Host port is already published by another container.",
                        {"host_port": spec.host_port, "container_id": container_id, "names": container.get("Names")},
                        409,
                    )

    def is_managed_container(self, container: dict[str, Any], spec: "ContainerSpec") -> bool:
        labels = container.get("Config", {}).get("Labels") or container.get("Labels") or {}
        return (
            labels.get(MANAGER_LABEL) == "true"
            and labels.get(AGENT_ID_LABEL) == spec.agent_id
            and labels.get(AGENT_NAME_LABEL) == spec.agent_name
        )

    def needs_recreate(self, container: dict[str, Any], spec: "ContainerSpec") -> bool:
        labels = container.get("Config", {}).get("Labels") or container.get("Labels") or {}
        return labels.get(SPEC_HASH_LABEL) != spec.spec_hash

    def operation_result(self, operation: str, spec: "ContainerSpec", container: dict[str, Any], actions: list[str]) -> dict[str, Any]:
        state = container.get("State", {})
        return {
            "agent_id": spec.agent_id,
            "agent_name": spec.agent_name,
            "container_id": container.get("Id"),
            "container_name": spec.container_name,
            "operation": operation,
            "actions": actions,
            "accepted": True,
            "state": state.get("Status") or "unknown",
            "running": bool(state.get("Running")),
            "managed": True,
            "controller": "docker-api",
            "image": spec.image,
            "host_port": spec.host_port,
            "network": spec.network_name,
            "timestamp": self._now(),
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class FakeDockerController:
    def __init__(self, docker_api_url: str = ""):
        self.docker_api_url = docker_api_url

    def start(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("start", agent, "stubbed")

    def stop(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("stop", agent, "stubbed")

    def restart(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("restart", agent, "stubbed")

    def delete(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("delete", agent, "stubbed")

    def status(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        return {
            "agent_id": self._agent_id(agent),
            "state": "unknown",
            "managed": False,
            "controller": "fake",
            "docker_api_url": self.docker_api_url,
            "checked_at": self._now(),
            "details": {
                "message": "Docker status is stubbed.",
            },
        }

    def logs(self, config: dict[str, Any], agent: dict[str, Any], tail: int = 200) -> dict[str, Any]:
        return {
            "agent_id": self._agent_id(agent),
            "controller": "fake",
            "tail": tail,
            "lines": [],
            "details": {
                "message": "Docker logs are stubbed.",
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
        }

    def _agent_id(self, agent: dict[str, Any]) -> str:
        return str(agent.get("id") or agent.get("name") or "")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class ContainerSpec:
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        safe_name: str,
        container_name: str,
        image: str,
        host_port: int,
        network_name: str,
        bootstrap_dir: Path,
        instance_dir: Path,
        environment: dict[str, str],
        labels: dict[str, str],
        extra_hosts: list[str],
        spec_hash: str,
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.safe_name = safe_name
        self.container_name = container_name
        self.image = image
        self.host_port = host_port
        self.network_name = network_name
        self.bootstrap_dir = bootstrap_dir
        self.instance_dir = instance_dir
        self.environment = environment
        self.labels = labels
        self.extra_hosts = extra_hosts
        self.spec_hash = spec_hash


def build_controller_from_env(project_root: Path) -> DockerController:
    docker_api_url = os.getenv("DOCKER_API_URL", "http://docker-socket-proxy:2375")
    mode = os.getenv("DOCKER_CONTROLLER", "api").lower()
    if mode == "fake":
        return FakeDockerController(docker_api_url)
    host_project_dir = Path(os.getenv("HOST_PROJECT_DIR", str(project_root))).resolve()
    timeout_secs = int(os.getenv("DOCKER_API_TIMEOUT_SECS", "30"))
    return DockerApiController(docker_api_url, host_project_dir, timeout_secs=timeout_secs)


def safe_container_part(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-._")
    return safe.lower() or "agent"


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def decode_docker_log_stream(body: bytes) -> str:
    if not body:
        return ""
    frames: list[bytes] = []
    index = 0
    while index + 8 <= len(body):
        stream_type = body[index]
        size = int.from_bytes(body[index + 4 : index + 8], "big")
        next_index = index + 8 + size
        if stream_type not in {0, 1, 2} or next_index > len(body):
            break
        frames.append(body[index + 8 : next_index])
        index = next_index
    if frames and index == len(body):
        return b"".join(frames).decode("utf-8", errors="replace")
    return body.decode("utf-8", errors="replace")
