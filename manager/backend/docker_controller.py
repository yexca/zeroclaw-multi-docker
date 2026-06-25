"""Docker runtime control for manager-owned ZeroClaw agent containers."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tarfile
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
ROLE_LABEL = "zeroclaw.role"
DEFAULT_IMAGE = "ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian"
DEFAULT_PYTHON_IMAGE = "zeroclaw-python:v0.8.1-debian"
DEFAULT_ROOT_IMAGE = "zeroclaw-root:v0.8.1-debian"
DEFAULT_PROACTIVE_IMAGE = "python:3.12-alpine"
SYNC_HELPER_IMAGE = "python:3.12-alpine"
CONTAINER_PORT = "42617/tcp"
MANAGED_IMAGE_LABEL = "zeroclaw.image.managed"
IMAGE_KIND_LABEL = "zeroclaw.image.kind"


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

    def sync_to_runtime(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def sync_from_runtime(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def reset_matrix_state(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        ...

    def audit_resources(self, config: dict[str, Any], decisions: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def resource_action(self, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def image_inventory(self, config: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def image_action(self, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
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

    def request_bytes(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        url = urljoin(self.base_url, path.lstrip("/"))
        if query:
            url = f"{url}?{urlencode(query, doseq=True)}"
        request = Request(url, data=body, headers=headers or {}, method=method)
        try:
            with urlopen(request, timeout=self.timeout_secs) as response:
                response_body = response.read()
                if raw:
                    return response_body
                if not response_body:
                    return {}
                content_type = response.headers.get("Content-Type", "")
                if "json" in content_type:
                    return json.loads(response_body.decode("utf-8"))
                return response_body.decode("utf-8", errors="replace")
        except HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            details: dict[str, Any] = {"status": exc.code, "body": body_text}
            try:
                decoded = json.loads(body_text)
                details["body"] = decoded
                message = decoded.get("message") or body_text
            except json.JSONDecodeError:
                message = body_text or exc.reason
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
        self._manager_mounts: dict[str, str] | None = None

    def start(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        self.validator.ensure_valid_for_start(config, agent)
        resolved = self.renderer.resolve_agent(config, agent)
        spec = self.build_container_spec(config, resolved)
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
            if spec.storage_driver == "volume":
                self.sync_runtime_to_local(spec)
                actions.append("runtime_synced_to_local")
            self.remove_container(existing["Id"], force=True)
            actions.append("recreated")
            existing = None

        if spec.storage_driver == "volume" and (not existing or not (existing.get("State", {}) or {}).get("Running")):
            self.sync_local_to_runtime(spec)
            actions.append("local_synced_to_runtime")

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

        actions.extend(self.reconcile_proactive_container(config, resolved, spec))
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
        proactive_spec = self.build_proactive_spec(config, agent) or self.build_disabled_proactive_spec(config, agent)
        proactive = self.find_container(proactive_spec)
        if proactive and self.is_managed_container(proactive, proactive_spec):
            proactive_state = proactive.get("State", {}) if isinstance(proactive, dict) else {}
            if proactive_state.get("Running"):
                self.client.request("POST", f"/containers/{proactive['Id']}/stop", query={"t": 10})
                actions.append("proactive_stopped")
        if spec.storage_driver == "volume":
            self.sync_runtime_to_local(spec)
            actions.append("runtime_synced_to_local")
        return self.operation_result("stop", spec, container, actions or ["already_stopped"])

    def restart(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        self.validator.ensure_valid_for_start(config, agent)
        start_result = self.start(config, agent)
        spec = self.build_container_spec(config, agent)
        if spec.storage_driver == "volume":
            self.sync_local_to_runtime(spec)
        container = self.require_managed_container(spec)
        self.client.request("POST", f"/containers/{container['Id']}/restart", query={"t": 10})
        container = self.inspect_container(container["Id"])
        actions = list(start_result.get("actions", [])) + ["restarted"]
        if spec.storage_driver == "volume" and "local_synced_to_runtime" not in actions:
            actions.insert(-1, "local_synced_to_runtime")
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
        proactive_spec = self.build_proactive_spec(config, agent) or self.build_disabled_proactive_spec(config, agent)
        proactive = self.find_container(proactive_spec)
        if proactive and self.is_managed_container(proactive, proactive_spec):
            self.remove_container(proactive["Id"], force=True)
        actions = ["deleted"]
        if spec.storage_driver == "volume":
            self.sync_runtime_to_local(spec)
            actions.append("runtime_synced_to_local")
        return {
            "agent_id": spec.agent_id,
            "agent_name": spec.agent_name,
            "container_name": spec.container_name,
            "operation": "delete",
            "actions": actions,
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
                "image": spec.image,
                "host_port": spec.host_port,
                "network": spec.network_name,
                "state": "absent",
                "running": False,
                "managed": False,
                "expected_spec_hash": spec.spec_hash,
                "controller": "docker-api",
                "checked_at": self._now(),
            }
        managed = self.is_managed_container(container, spec)
        state = container.get("State", {})
        config_labels = container.get("Config", {}).get("Labels") or {}
        health = state.get("Health") if isinstance(state.get("Health"), dict) else {}
        return {
            "agent_id": spec.agent_id,
            "agent_name": spec.agent_name,
            "container_id": container.get("Id"),
            "container_name": spec.container_name,
            "image": container.get("Config", {}).get("Image"),
            "state": state.get("Status") or "unknown",
            "running": bool(state.get("Running")),
            "created_at": container.get("Created"),
            "started_at": state.get("StartedAt"),
            "finished_at": state.get("FinishedAt"),
            "health_status": health.get("Status") or "",
            "restart_count": container.get("RestartCount", 0),
            "managed": managed,
            "needs_recreate": managed and self.needs_recreate(container, spec),
            "spec_hash": config_labels.get(SPEC_HASH_LABEL),
            "expected_spec_hash": spec.spec_hash,
            "host_port": spec.host_port,
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
            "fetched_at": self._now(),
            "lines": text.splitlines(),
        }

    def sync_to_runtime(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        spec = self.build_container_spec(config, agent)
        if spec.storage_driver != "volume":
            return self.operation_result("sync-to-runtime", spec, {}, ["bind_storage_noop"])
        self.sync_local_to_runtime(spec)
        return self.operation_result("sync-to-runtime", spec, {}, ["local_synced_to_runtime"])

    def sync_from_runtime(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        spec = self.build_container_spec(config, agent)
        if spec.storage_driver != "volume":
            return self.operation_result("sync-from-runtime", spec, {}, ["bind_storage_noop"])
        self.sync_runtime_to_local(spec)
        return self.operation_result("sync-from-runtime", spec, {}, ["runtime_synced_to_local"])

    def reset_matrix_state(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        spec = self.build_container_spec(config, agent)
        container = self.find_container(spec)
        if container and self.is_managed_container(container, spec):
            state = container.get("State", {}) if isinstance(container, dict) else {}
            if state.get("Running"):
                raise ConfigError(
                    "agent_running",
                    "Agent container is running. Stop it before resetting Matrix state.",
                    {"agent": spec.agent_id, "container": spec.container_name},
                    409,
                )
        elif container:
            raise ConfigError(
                "container_not_manager_owned",
                "Refusing to inspect a container without the manager label.",
                {"container": spec.container_name},
                409,
            )

        actions: list[str] = []
        if spec.storage_driver == "volume":
            self.run_matrix_reset_helper(spec)
            actions.append("matrix_state_removed_from_local_and_runtime")
        else:
            matrix_dir = (spec.instance_dir / ".zeroclaw" / "state" / "matrix").resolve()
            instance_dir = spec.instance_dir.resolve()
            if instance_dir != matrix_dir and instance_dir not in matrix_dir.parents:
                raise ConfigError("unsafe_matrix_state_path", "Refusing to delete Matrix state outside the agent instance directory.", {"path": str(matrix_dir)}, 409)
            if matrix_dir.exists():
                shutil.rmtree(matrix_dir)
            actions.append("matrix_state_removed_from_local")
        return self.operation_result("reset-matrix-state", spec, container or {}, actions)

    def audit_resources(self, config: dict[str, Any], decisions: dict[str, Any] | None = None) -> dict[str, Any]:
        self.configure_client(config)
        decisions = decisions or {"ignored": [], "adopted": []}
        agents = config.get("agents") if isinstance(config.get("agents"), list) else []
        expected_containers: dict[str, dict[str, Any]] = {}
        expected_volumes: dict[str, dict[str, Any]] = {}
        expected_networks: dict[str, dict[str, Any]] = {}
        expected_errors: list[dict[str, Any]] = []

        for agent in agents:
            if not isinstance(agent, dict):
                continue
            try:
                spec = self.build_container_spec(config, agent)
            except Exception as exc:
                expected_errors.append({"agent": item_id(agent), "error": str(exc), "type": type(exc).__name__})
                continue
            expected_containers[spec.container_name] = {
                "name": spec.container_name,
                "role": "agent",
                "agent_id": spec.agent_id,
                "agent_name": spec.agent_name,
                "expected": True,
            }
            proactive_spec = self.build_proactive_spec(config, agent, agent_spec=spec)
            if proactive_spec:
                expected_containers[proactive_spec.container_name] = {
                    "name": proactive_spec.container_name,
                    "role": "proactive",
                    "agent_id": proactive_spec.agent_id,
                    "agent_name": proactive_spec.agent_name,
                    "expected": True,
                }
            if spec.storage_driver == "volume":
                expected_volumes[spec.volume_name] = {
                    "name": spec.volume_name,
                    "role": "volume",
                    "agent_id": spec.agent_id,
                    "agent_name": spec.agent_name,
                    "expected": True,
                }
            expected_networks[spec.network_name] = {
                "name": spec.network_name,
                "role": "network",
                "expected": True,
            }

        containers = self.list_containers_for_audit(expected_containers)
        volumes = self.list_volumes_for_audit(expected_volumes)
        networks = self.list_networks_for_audit(expected_networks)

        return {
            "checked_at": self._now(),
            "expected": {
                "containers": list(expected_containers.values()),
                "volumes": list(expected_volumes.values()),
                "networks": list(expected_networks.values()),
                "errors": expected_errors,
            },
            "containers": self.apply_resource_decisions(self.classify_container_resources(containers, expected_containers), "container", decisions),
            "volumes": self.apply_resource_decisions(self.classify_named_resources(volumes, expected_volumes), "volume", decisions),
            "networks": self.apply_resource_decisions(self.classify_named_resources(networks, expected_networks), "network", decisions),
        }

    def resource_action(self, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        kind = str(payload.get("kind") or "")
        name = str(payload.get("name") or "")
        action = str(payload.get("action") or "")
        if kind not in {"container", "volume", "network"}:
            raise ConfigError("invalid_resource_kind", "Unsupported Docker resource kind.", {"kind": kind}, 422)
        if action not in {"delete", "migrate"}:
            raise ConfigError("invalid_resource_action", "Unsupported Docker resource action.", {"action": action}, 422)
        if not name:
            raise ConfigError("missing_resource_name", "Docker resource name is required.", status=422)
        if action == "delete":
            self.ensure_resource_delete_allowed(config, kind, name)
            return self.delete_resource(kind, name)
        target_name = str(payload.get("target_name") or "")
        if kind != "volume":
            raise ConfigError("unsupported_migration", "Only volume migration is currently supported.", {"kind": kind}, 422)
        return self.migrate_volume(name, target_name)

    def image_inventory(self, config: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
        self.configure_client(config)
        defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
        official = str(defaults.get("zeroclaw_image") or os.getenv("ZEROCLAW_IMAGE") or DEFAULT_IMAGE)
        references: list[tuple[str, str]] = [
            ("official", official),
            ("python", DEFAULT_PYTHON_IMAGE),
            ("root", DEFAULT_ROOT_IMAGE),
        ]
        agents = config.get("agents") if isinstance(config.get("agents"), list) else []
        for agent in agents:
            if isinstance(agent, dict) and agent.get("image"):
                references.append(("agent", str(agent.get("image"))))
        seen: set[str] = set()
        images: list[dict[str, Any]] = []
        for kind, reference in references:
            if not reference or reference in seen:
                continue
            seen.add(reference)
            images.append(self.image_summary(reference, kind))
        return {
            "checked_at": self._now(),
            "default_image": official,
            "recommended": {
                "official": official,
                "python": DEFAULT_PYTHON_IMAGE,
                "root": DEFAULT_ROOT_IMAGE,
            },
            "build_enabled_hint": "Set DOCKER_SOCKET_PROXY_BUILD=1 in .env and restart docker compose to enable builds.",
            "state": state or {"acknowledged": {}},
            "images": images,
            "controller": "docker-api",
        }

    def image_action(self, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.configure_client(config)
        action = str(payload.get("action") or "")
        if action == "pull-official":
            defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
            image = str(payload.get("image") or defaults.get("zeroclaw_image") or os.getenv("ZEROCLAW_IMAGE") or DEFAULT_IMAGE)
            self.pull_image(image)
            return {"action": action, "image": image, "summary": self.image_summary(image, "official"), "timestamp": self._now()}
        if action == "build-python":
            return self.build_derived_image(
                kind="python",
                base_image=str(payload.get("base_image") or DEFAULT_IMAGE),
                target_image=str(payload.get("target_image") or DEFAULT_PYTHON_IMAGE),
            )
        if action == "build-root":
            return self.build_derived_image(
                kind="root",
                base_image=str(payload.get("base_image") or DEFAULT_IMAGE),
                target_image=str(payload.get("target_image") or DEFAULT_ROOT_IMAGE),
            )
        raise ConfigError("invalid_image_action", "Unsupported Docker image action.", {"action": action}, 422)

    def reconcile_proactive_container(self, config: dict[str, Any], agent: dict[str, Any], agent_spec: "ContainerSpec") -> list[str]:
        proactive_spec = self.build_proactive_spec(config, agent, agent_spec=agent_spec)
        existing = self.find_container(proactive_spec) if proactive_spec else None
        if not proactive_spec:
            disabled_spec = self.build_disabled_proactive_spec(config, agent, agent_spec=agent_spec)
            disabled = self.find_container(disabled_spec)
            if disabled and self.is_managed_container(disabled, disabled_spec):
                self.remove_container(disabled["Id"], force=True)
                return ["proactive_removed"]
            return []
        actions: list[str] = []
        self.pull_image(proactive_spec.image)
        if existing and not self.is_managed_container(existing, proactive_spec):
            raise ConfigError(
                "container_not_manager_owned",
                "Refusing to modify a proactive container without the manager label.",
                {"container": proactive_spec.container_name},
                409,
            )
        if existing and self.needs_recreate(existing, proactive_spec):
            self.remove_container(existing["Id"], force=True)
            actions.append("proactive_recreated")
            existing = None
        if not existing:
            created = self.create_proactive_container(proactive_spec)
            existing = self.inspect_container(created["Id"])
            actions.append("proactive_created")
        state = existing.get("State", {}) if isinstance(existing, dict) else {}
        if not state.get("Running"):
            self.client.request("POST", f"/containers/{existing['Id']}/start")
            actions.append("proactive_started")
        return actions

    def build_container_spec(self, config: dict[str, Any], agent: dict[str, Any]) -> "ContainerSpec":
        resolved = self.renderer.resolve_agent(config, agent)
        agent_identifier = item_id(resolved)
        if not agent_identifier:
            raise ConfigError("invalid_agent", "Agent requires an id or name.")
        agent_name = str(agent_identifier)
        safe_name = safe_container_part(agent_name)
        host_port = resolved.get("host_port")
        if not isinstance(host_port, int):
            raise ConfigError("invalid_agent", "Agent host_port must be an integer.", {"agent": agent_identifier})

        docker_config = config.get("docker") if isinstance(config.get("docker"), dict) else {}
        paths = config.get("paths") if isinstance(config.get("paths"), dict) else {}
        defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}

        image = str(resolved.get("image") or defaults.get("zeroclaw_image") or os.getenv("ZEROCLAW_IMAGE") or DEFAULT_IMAGE)
        project_name = str(docker_config.get("project_name") or "zeroclaw-dockyard")
        network_name = str(docker_config.get("runtime_network") or f"{project_name}_default")
        storage_driver = str(docker_config.get("storage_driver") or "volume").lower()
        if storage_driver not in {"volume", "bind"}:
            raise ConfigError("invalid_storage_driver", "Docker storage_driver must be volume or bind.", {"storage_driver": storage_driver})
        volume_prefix = safe_volume_part(str(docker_config.get("volume_prefix") or project_name))
        volume_name = f"{volume_prefix}-agent-{safe_name}-data"
        manager_mounts = self.manager_mount_sources()
        project_root = Path(str(paths.get("host_project_dir") or os.getenv("HOST_PROJECT_DIR") or self.project_root)).resolve()
        local_instances_dir = Path(str(paths.get("instances_dir") or "/app/instances"))
        instance_dir = local_instances_dir / safe_name
        host_instances_dir = Path(str(paths.get("host_instances_dir") or manager_mounts.get("/app/instances") or project_root / "instances")).resolve()
        host_bootstrap_dir = Path(str(paths.get("host_bootstrap_dir") or manager_mounts.get("/app/bootstrap") or project_root / "bootstrap")).resolve()
        host_shared_dir = Path(str(paths.get("host_shared_dir") or manager_mounts.get("/app/shared") or project_root / "shared")).resolve()
        bootstrap_dir = Path("/app/bootstrap" if storage_driver == "volume" else str(host_bootstrap_dir))
        runtime_instance_dir = instance_dir if storage_driver == "volume" else host_instances_dir / safe_name
        env = self.renderer.render_env(config, resolved)
        matrix_host_ip = env.get("MATRIX_HOST_IP", "127.0.0.1")

        labels = {
            MANAGER_LABEL: "true",
            AGENT_ID_LABEL: str(agent_identifier),
            AGENT_NAME_LABEL: agent_name,
            ROLE_LABEL: "agent",
        }
        spec_payload = {
            "image": image,
            "agent_id": agent_identifier,
            "agent_name": agent_name,
            "host_port": host_port,
            "network_name": network_name,
            "env": env,
            "mounts": self.runtime_mounts_payload(storage_driver, volume_name, str(host_bootstrap_dir), str(host_shared_dir), str(runtime_instance_dir)),
            "extra_hosts": [f"host.docker.internal:host-gateway", f"matrix-host:{matrix_host_ip}"],
            "storage_driver": storage_driver,
            "volume_name": volume_name if storage_driver == "volume" else "",
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
            shared_dir=Path("/app/shared" if storage_driver == "volume" else str(host_shared_dir)),
            instance_dir=runtime_instance_dir,
            local_instance_dir=instance_dir,
            storage_driver=storage_driver,
            volume_name=volume_name,
            environment=env,
            labels=labels,
            extra_hosts=spec_payload["extra_hosts"],
            spec_hash=spec_hash,
        )

    def build_proactive_spec(self, config: dict[str, Any], agent: dict[str, Any], agent_spec: "ContainerSpec" | None = None) -> "ContainerSpec | None":
        resolved = self.renderer.resolve_agent(config, agent)
        proactive = resolved.get("proactive") if isinstance(resolved.get("proactive"), dict) else {}
        if not bool(proactive.get("enabled")):
            return None
        agent_spec = agent_spec or self.build_container_spec(config, resolved)
        target = str(proactive.get("target") or first_item((resolved.get("matrix") or {}).get("external_peers")) or "").strip()
        if not target:
            raise ConfigError("missing_proactive_target", "Proactive target must be configured.", {"agent": agent_spec.agent_id}, 422)

        docker_config = config.get("docker") if isinstance(config.get("docker"), dict) else {}
        paths = config.get("paths") if isinstance(config.get("paths"), dict) else {}
        manager_mounts = self.manager_mount_sources()
        project_name = str(docker_config.get("project_name") or "zeroclaw-dockyard")
        network_name = str(docker_config.get("runtime_network") or f"{project_name}_default")
        project_root = Path(str(paths.get("host_project_dir") or os.getenv("HOST_PROJECT_DIR") or self.project_root)).resolve()
        storage_driver = agent_spec.storage_driver
        host_bootstrap_dir = Path(str(paths.get("host_bootstrap_dir") or manager_mounts.get("/app/bootstrap") or project_root / "bootstrap")).resolve()
        bootstrap_dir = Path("/app/bootstrap" if storage_driver == "volume" else str(host_bootstrap_dir))
        image = str(proactive.get("image") or DEFAULT_PROACTIVE_IMAGE)
        gateway_host = str(proactive.get("gateway_host") or "host.docker.internal")
        default_agent_url = f"http://{gateway_host}:{agent_spec.host_port}/webhook?{urlencode({'agent': agent_spec.agent_id})}"
        agent_url = str(proactive.get("agent_url") or default_agent_url)
        env = {
            "PROACTIVE_ENABLED": "true",
            "PROACTIVE_AGENT": agent_spec.agent_id,
            "PROACTIVE_AGENT_URL": agent_url,
            "PROACTIVE_CHANNEL": str(proactive.get("channel") or "matrix.home"),
            "PROACTIVE_TARGET": target,
            "PROACTIVE_PROMPT": str(proactive.get("prompt") or ""),
            "PROACTIVE_POLL_SECONDS": str(proactive.get("poll_seconds") or 300),
            "PROACTIVE_RANDOM_MIN_MINUTES": str(proactive.get("random_min_minutes") or 120),
            "PROACTIVE_RANDOM_MAX_MINUTES": str(proactive.get("random_max_minutes") or 240),
            "PROACTIVE_TIMEZONE": str(proactive.get("timezone") or "Asia/Tokyo"),
            "PROACTIVE_QUIET_HOURS": str(proactive.get("quiet_hours") or "23-8"),
            "PROACTIVE_STATE_DIR": "/state/proactive",
        }
        labels = {
            MANAGER_LABEL: "true",
            AGENT_ID_LABEL: agent_spec.agent_id,
            AGENT_NAME_LABEL: agent_spec.agent_name,
            ROLE_LABEL: "proactive",
        }
        spec_payload = {
            "image": image,
            "agent_id": agent_spec.agent_id,
            "agent_name": agent_spec.agent_name,
            "network_name": network_name,
            "env": env,
            "mounts": [
                self.runtime_mount_payload(storage_driver, agent_spec.volume_name, str(host_bootstrap_dir), str(agent_spec.instance_dir), "/state"),
            ],
            "storage_driver": storage_driver,
            "volume_name": agent_spec.volume_name if storage_driver == "volume" else "",
        }
        spec_hash = stable_hash(spec_payload)
        labels[SPEC_HASH_LABEL] = spec_hash
        return ContainerSpec(
            agent_id=agent_spec.agent_id,
            agent_name=agent_spec.agent_name,
            safe_name=agent_spec.safe_name,
            container_name=f"zeroclaw-proactive-{agent_spec.safe_name}",
            image=image,
            host_port=0,
            network_name=network_name,
            bootstrap_dir=bootstrap_dir,
            shared_dir=agent_spec.shared_dir,
            instance_dir=agent_spec.instance_dir,
            local_instance_dir=agent_spec.local_instance_dir,
            storage_driver=agent_spec.storage_driver,
            volume_name=agent_spec.volume_name,
            environment=env,
            labels=labels,
            extra_hosts=["host.docker.internal:host-gateway"],
            spec_hash=spec_hash,
        )

    def build_disabled_proactive_spec(self, config: dict[str, Any], agent: dict[str, Any], agent_spec: "ContainerSpec" | None = None) -> "ContainerSpec":
        agent_spec = agent_spec or self.build_container_spec(config, agent)
        return ContainerSpec(
            agent_id=agent_spec.agent_id,
            agent_name=agent_spec.agent_name,
            safe_name=agent_spec.safe_name,
            container_name=f"zeroclaw-proactive-{agent_spec.safe_name}",
            image=DEFAULT_PROACTIVE_IMAGE,
            host_port=0,
            network_name=agent_spec.network_name,
            bootstrap_dir=agent_spec.bootstrap_dir,
            shared_dir=agent_spec.shared_dir,
            instance_dir=agent_spec.instance_dir,
            local_instance_dir=agent_spec.local_instance_dir,
            storage_driver=agent_spec.storage_driver,
            volume_name=agent_spec.volume_name,
            environment={},
            labels={MANAGER_LABEL: "true", AGENT_ID_LABEL: agent_spec.agent_id, AGENT_NAME_LABEL: agent_spec.agent_name, ROLE_LABEL: "proactive"},
            extra_hosts=["host.docker.internal:host-gateway"],
            spec_hash="",
        )

    def configure_client(self, config: dict[str, Any]) -> None:
        docker_config = config.get("docker") if isinstance(config.get("docker"), dict) else {}
        proxy_url = str(docker_config.get("proxy_url") or self.docker_api_url)
        if proxy_url != self.docker_api_url:
            self.docker_api_url = proxy_url
            self.client = DockerApiClient(proxy_url, timeout_secs=self.client.timeout_secs)
            self._manager_mounts = None

    def manager_mount_sources(self) -> dict[str, str]:
        if self._manager_mounts is not None:
            return self._manager_mounts
        container_name = os.getenv("MANAGER_CONTAINER_NAME", "zeroclaw-dockyard")
        try:
            container = self.client.request("GET", f"/containers/{quote(container_name, safe='')}/json")
        except DockerApiError:
            self._manager_mounts = {}
            return self._manager_mounts
        mounts = container.get("Mounts") if isinstance(container, dict) else []
        result: dict[str, str] = {}
        if isinstance(mounts, list):
            for mount in mounts:
                if not isinstance(mount, dict):
                    continue
                destination = mount.get("Destination")
                source = mount.get("Source")
                if isinstance(destination, str) and isinstance(source, str):
                    result[destination] = source
        self._manager_mounts = result
        return result

    def runtime_mount_payload(self, storage_driver: str, volume_name: str, bootstrap_source: str, instance_source: str, target: str) -> dict[str, Any]:
        if storage_driver == "volume":
            return {"Type": "volume", "Source": volume_name, "Target": target}
        return {"Type": "bind", "Source": instance_source, "Target": target}

    def runtime_mounts_payload(self, storage_driver: str, volume_name: str, bootstrap_source: str, shared_source: str, instance_source: str) -> list[dict[str, Any]]:
        if storage_driver == "volume":
            return [{"Type": "volume", "Source": volume_name, "Target": "/zeroclaw-data"}]
        return [
            {"Type": "bind", "Source": instance_source, "Target": "/zeroclaw-data"},
            {"Type": "bind", "Source": bootstrap_source, "Target": "/bootstrap", "ReadOnly": True},
            {"Type": "bind", "Source": shared_source, "Target": "/zeroclaw-data/shared"},
        ]

    def create_container(self, spec: "ContainerSpec") -> dict[str, Any]:
        if spec.storage_driver == "bind":
            spec.instance_dir.mkdir(parents=True, exist_ok=True)
            (spec.instance_dir / "workspace").mkdir(parents=True, exist_ok=True)
        entrypoint = ["/bin/sh", "/zeroclaw-data/bootstrap/render-config.sh"] if spec.storage_driver == "volume" else ["/bin/sh", "/bootstrap/render-config.sh"]
        mounts = [{"Type": "volume", "Source": spec.volume_name, "Target": "/zeroclaw-data"}] if spec.storage_driver == "volume" else [
            {"Type": "bind", "Source": str(spec.bootstrap_dir), "Target": "/bootstrap", "ReadOnly": True},
            {"Type": "bind", "Source": str(spec.instance_dir), "Target": "/zeroclaw-data"},
            {"Type": "bind", "Source": str(spec.shared_dir), "Target": "/zeroclaw-data/shared"},
        ]
        payload = {
            "Image": spec.image,
            "User": "0:0",
            "WorkingDir": "/zeroclaw-data/workspace",
            "Entrypoint": entrypoint,
            "Env": [f"{key}={value}" for key, value in sorted(spec.environment.items())],
            "Labels": spec.labels,
            "ExposedPorts": {CONTAINER_PORT: {}},
            "HostConfig": {
                "RestartPolicy": {"Name": "unless-stopped"},
                "Mounts": mounts,
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

    def create_proactive_container(self, spec: "ContainerSpec") -> dict[str, Any]:
        if spec.storage_driver == "bind":
            (spec.instance_dir / "proactive").mkdir(parents=True, exist_ok=True)
        entrypoint = ["python", "/state/bootstrap/proactive.py"] if spec.storage_driver == "volume" else ["python", "/bootstrap/proactive.py"]
        mounts = [{"Type": "volume", "Source": spec.volume_name, "Target": "/state"}] if spec.storage_driver == "volume" else [
            {"Type": "bind", "Source": str(spec.bootstrap_dir), "Target": "/bootstrap", "ReadOnly": True},
            {"Type": "bind", "Source": str(spec.instance_dir), "Target": "/state"},
        ]
        payload = {
            "Image": spec.image,
            "WorkingDir": "/state",
            "Entrypoint": entrypoint,
            "Env": [f"{key}={value}" for key, value in sorted(spec.environment.items())],
            "Labels": spec.labels,
            "HostConfig": {
                "RestartPolicy": {"Name": "unless-stopped"},
                "Mounts": mounts,
                "ExtraHosts": spec.extra_hosts,
            },
            "NetworkingConfig": {
                "EndpointsConfig": {
                    spec.network_name: {},
                },
            },
        }
        return self.client.request("POST", "/containers/create", payload=payload, query={"name": spec.container_name})

    def ensure_volume(self, volume_name: str) -> None:
        try:
            self.client.request("GET", f"/volumes/{quote(volume_name, safe='')}")
            return
        except DockerApiError as exc:
            if exc.status != 404:
                raise
        self.client.request("POST", "/volumes/create", payload={"Name": volume_name, "Labels": {MANAGER_LABEL: "true"}})

    def list_containers_for_audit(self, expected: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        containers = self.client.request("GET", "/containers/json", query={"all": 1})
        rows: list[dict[str, Any]] = []
        for container in containers if isinstance(containers, list) else []:
            names = [str(name).lstrip("/") for name in container.get("Names") or []]
            labels = container.get("Labels") or {}
            if (
                labels.get(MANAGER_LABEL) == "true"
                or any(name in expected for name in names)
                or any("zeroclaw" in name for name in names)
            ):
                rows.append(container)
        return rows

    def list_volumes_for_audit(self, expected: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            result = self.client.request("GET", "/volumes")
        except DockerApiError as exc:
            if exc.status == 404:
                return []
            raise
        volumes = result.get("Volumes") if isinstance(result, dict) else []
        rows: list[dict[str, Any]] = []
        for volume in volumes if isinstance(volumes, list) else []:
            name = str(volume.get("Name") or "")
            labels = volume.get("Labels") or {}
            if labels.get(MANAGER_LABEL) == "true" or name in expected or "zeroclaw" in name:
                rows.append(volume)
        return rows

    def list_networks_for_audit(self, expected: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        networks = self.client.request("GET", "/networks")
        rows: list[dict[str, Any]] = []
        for network in networks if isinstance(networks, list) else []:
            name = str(network.get("Name") or "")
            labels = network.get("Labels") or {}
            if labels.get(MANAGER_LABEL) == "true" or name in expected or "zeroclaw" in name:
                rows.append(network)
        return rows

    def classify_container_resources(self, containers: list[dict[str, Any]], expected: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        buckets: dict[str, list[dict[str, Any]]] = {"expected": [], "orphans": [], "legacy": [], "conflicts": []}
        seen_expected: set[str] = set()
        for container in containers:
            names = [str(name).lstrip("/") for name in container.get("Names") or []]
            name = names[0] if names else str(container.get("Id") or "")
            labels = container.get("Labels") or {}
            expected_row = next((expected[item] for item in names if item in expected), None)
            row = {
                "id": container.get("Id"),
                "name": name,
                "names": names,
                "image": container.get("Image"),
                "state": container.get("State"),
                "status": container.get("Status"),
                "labels": labels,
                "role": labels.get(ROLE_LABEL) or (expected_row or {}).get("role") or "",
                "agent_id": labels.get(AGENT_ID_LABEL) or (expected_row or {}).get("agent_id") or "",
                "agent_name": labels.get(AGENT_NAME_LABEL) or (expected_row or {}).get("agent_name") or "",
            }
            if expected_row:
                seen_expected.add(expected_row["name"])
                if labels.get(MANAGER_LABEL) == "true":
                    buckets["expected"].append({**row, "classification": "expected"})
                else:
                    buckets["conflicts"].append({**row, "classification": "expected_name_unmanaged"})
            elif labels.get(MANAGER_LABEL) == "true":
                buckets["orphans"].append({**row, "classification": "managed_orphan"})
            else:
                buckets["legacy"].append({**row, "classification": "legacy_candidate"})
        for name, expected_row in expected.items():
            if name not in seen_expected:
                buckets["expected"].append({**expected_row, "state": "absent", "status": "absent", "classification": "expected_absent"})
        return buckets

    def classify_named_resources(self, resources: list[dict[str, Any]], expected: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        buckets: dict[str, list[dict[str, Any]]] = {"expected": [], "orphans": [], "legacy": [], "conflicts": []}
        seen_expected: set[str] = set()
        for resource in resources:
            name = str(resource.get("Name") or "")
            labels = resource.get("Labels") or {}
            expected_row = expected.get(name)
            row = {
                "name": name,
                "driver": resource.get("Driver"),
                "scope": resource.get("Scope"),
                "labels": labels,
                "role": labels.get(ROLE_LABEL) or (expected_row or {}).get("role") or "",
                "agent_id": labels.get(AGENT_ID_LABEL) or (expected_row or {}).get("agent_id") or "",
                "agent_name": labels.get(AGENT_NAME_LABEL) or (expected_row or {}).get("agent_name") or "",
            }
            if expected_row:
                seen_expected.add(name)
                if labels.get(MANAGER_LABEL) == "true":
                    buckets["expected"].append({**row, "classification": "expected"})
                else:
                    buckets["conflicts"].append({**row, "classification": "expected_name_unlabeled"})
            elif labels.get(MANAGER_LABEL) == "true":
                buckets["orphans"].append({**row, "classification": "managed_orphan"})
            else:
                buckets["legacy"].append({**row, "classification": "legacy_candidate"})
        for name, expected_row in expected.items():
            if name not in seen_expected:
                buckets["expected"].append({**expected_row, "state": "absent", "status": "absent", "classification": "expected_absent"})
        return buckets

    def apply_resource_decisions(self, buckets: dict[str, list[dict[str, Any]]], kind: str, decisions: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        ignored = {item.get("name") for item in decisions.get("ignored", []) if item.get("kind") == kind}
        adopted = {item.get("name") for item in decisions.get("adopted", []) if item.get("kind") == kind}
        if not ignored and not adopted:
            return buckets
        result = {key: list(value) for key, value in buckets.items()}
        result.setdefault("ignored", [])
        result.setdefault("adopted", [])
        for source_bucket in ("conflicts", "legacy", "orphans"):
            remaining = []
            for row in result.get(source_bucket, []):
                name = row.get("name")
                if name in ignored:
                    result["ignored"].append({**row, "classification": "ignored", "original_classification": row.get("classification")})
                elif name in adopted:
                    result["adopted"].append({**row, "classification": "adopted", "original_classification": row.get("classification")})
                else:
                    remaining.append(row)
            result[source_bucket] = remaining
        return result

    def ensure_resource_delete_allowed(self, config: dict[str, Any], kind: str, name: str) -> None:
        audit = self.audit_resources(config, {"ignored": [], "adopted": []})
        group_key = {"container": "containers", "volume": "volumes", "network": "networks"}[kind]
        group = audit.get(group_key, {})
        protected = list(group.get("expected", [])) + list(group.get("conflicts", []))
        if any(row.get("name") == name for row in protected):
            raise ConfigError(
                "resource_delete_refused",
                "Refusing to delete a resource expected by the current configuration.",
                {"kind": kind, "name": name},
                409,
            )

    def delete_resource(self, kind: str, name: str) -> dict[str, Any]:
        if kind == "container":
            container = self.inspect_container(name)
            self.remove_container(str(container.get("Id") or name), force=True)
        elif kind == "volume":
            self.client.request("DELETE", f"/volumes/{quote(name, safe='')}")
        elif kind == "network":
            self.client.request("DELETE", f"/networks/{quote(name, safe='')}")
        return {"action": "delete", "kind": kind, "name": name, "deleted": True, "timestamp": self._now()}

    def migrate_volume(self, source_name: str, target_name: str) -> dict[str, Any]:
        if not target_name:
            raise ConfigError("missing_target_name", "Target volume name is required for migration.", status=422)
        self.ensure_volume(target_name)
        helper_name = f"zeroclaw-migrate-volume-{safe_volume_part(source_name)}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        script = """
import os
import shutil
import stat
from pathlib import Path

source = Path('/source')
target = Path('/target')

def copy_tree(src, dst):
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        destination = dst / item.name
        try:
            mode = item.lstat().st_mode
        except OSError:
            continue
        if stat.S_ISSOCK(mode) or stat.S_ISFIFO(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
            continue
        if item.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            copy_tree(item, destination)
        elif item.is_symlink():
            if destination.exists() or destination.is_symlink():
                destination.unlink()
            destination.symlink_to(os.readlink(item))
        else:
            if destination.exists() and destination.is_dir():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)

copy_tree(source, target)
"""
        payload = {
            "Image": SYNC_HELPER_IMAGE,
            "Cmd": ["python", "-c", script],
            "Labels": {MANAGER_LABEL: "true", ROLE_LABEL: "sync"},
            "HostConfig": {
                "AutoRemove": False,
                "Mounts": [
                    {"Type": "volume", "Source": source_name, "Target": "/source", "ReadOnly": True},
                    {"Type": "volume", "Source": target_name, "Target": "/target"},
                ],
            },
        }
        container_id = ""
        try:
            created = self.client.request("POST", "/containers/create", payload=payload, query={"name": helper_name})
            container_id = str(created.get("Id") or "")
            self.client.request("POST", f"/containers/{container_id}/start")
            result = self.client.request("POST", f"/containers/{container_id}/wait")
            status_code = result.get("StatusCode") if isinstance(result, dict) else None
            if status_code != 0:
                logs = ""
                try:
                    logs = decode_docker_log_stream(self.client.request("GET", f"/containers/{container_id}/logs", query={"stdout": 1, "stderr": 1}, raw=True))
                except DockerApiError:
                    pass
                raise ConfigError("volume_migration_failed", "Volume migration failed.", {"status_code": status_code, "logs": logs}, 502)
        finally:
            if container_id:
                try:
                    self.remove_container(container_id, force=True)
                except DockerApiError:
                    pass
        return {"action": "migrate", "kind": "volume", "source_name": source_name, "target_name": target_name, "timestamp": self._now()}

    def sync_local_to_runtime(self, spec: "ContainerSpec") -> None:
        spec.local_instance_dir.mkdir(parents=True, exist_ok=True)
        (spec.local_instance_dir / "workspace").mkdir(parents=True, exist_ok=True)
        self.run_sync_helper(spec, "to-runtime")

    def sync_runtime_to_local(self, spec: "ContainerSpec") -> None:
        spec.local_instance_dir.mkdir(parents=True, exist_ok=True)
        self.run_sync_helper(spec, "from-runtime")

    def run_sync_helper(self, spec: "ContainerSpec", direction: str) -> None:
        helper_name = f"zeroclaw-sync-{spec.safe_name}-{direction}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        script = self.sync_script(direction, spec.safe_name)
        payload = {
            "Image": SYNC_HELPER_IMAGE,
            "Cmd": ["python", "-c", script],
            "Labels": {MANAGER_LABEL: "true", AGENT_ID_LABEL: spec.agent_id, AGENT_NAME_LABEL: spec.agent_name, ROLE_LABEL: "sync"},
            "HostConfig": {
                "AutoRemove": False,
                "VolumesFrom": ["zeroclaw-dockyard:rw"],
                "Mounts": [{"Type": "volume", "Source": spec.volume_name, "Target": "/volume"}],
            },
        }
        container_id = ""
        try:
            created = self.client.request("POST", "/containers/create", payload=payload, query={"name": helper_name})
            container_id = str(created.get("Id") or "")
            self.client.request("POST", f"/containers/{container_id}/start")
            result = self.client.request("POST", f"/containers/{container_id}/wait")
            status_code = result.get("StatusCode") if isinstance(result, dict) else None
            if status_code != 0:
                logs = ""
                try:
                    logs = decode_docker_log_stream(self.client.request("GET", f"/containers/{container_id}/logs", query={"stdout": 1, "stderr": 1}, raw=True))
                except DockerApiError:
                    pass
                raise ConfigError("sync_failed", "Runtime volume sync failed.", {"direction": direction, "status_code": status_code, "logs": logs}, 502)
        finally:
            if container_id:
                try:
                    self.remove_container(container_id, force=True)
                except DockerApiError:
                    pass

    def run_matrix_reset_helper(self, spec: "ContainerSpec") -> None:
        helper_name = f"zeroclaw-reset-matrix-{spec.safe_name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        script = self.matrix_reset_script(spec.safe_name)
        payload = {
            "Image": SYNC_HELPER_IMAGE,
            "Cmd": ["python", "-c", script],
            "Labels": {MANAGER_LABEL: "true", AGENT_ID_LABEL: spec.agent_id, AGENT_NAME_LABEL: spec.agent_name, ROLE_LABEL: "sync"},
            "HostConfig": {
                "AutoRemove": False,
                "VolumesFrom": ["zeroclaw-dockyard:rw"],
                "Mounts": [{"Type": "volume", "Source": spec.volume_name, "Target": "/volume"}],
            },
        }
        container_id = ""
        try:
            created = self.client.request("POST", "/containers/create", payload=payload, query={"name": helper_name})
            container_id = str(created.get("Id") or "")
            self.client.request("POST", f"/containers/{container_id}/start")
            result = self.client.request("POST", f"/containers/{container_id}/wait")
            status_code = result.get("StatusCode") if isinstance(result, dict) else None
            if status_code != 0:
                logs = ""
                try:
                    logs = decode_docker_log_stream(self.client.request("GET", f"/containers/{container_id}/logs", query={"stdout": 1, "stderr": 1}, raw=True))
                except DockerApiError:
                    pass
                raise ConfigError("matrix_reset_failed", "Matrix state reset failed.", {"status_code": status_code, "logs": logs}, 502)
        finally:
            if container_id:
                try:
                    self.remove_container(container_id, force=True)
                except DockerApiError:
                    pass

    def matrix_reset_script(self, safe_name: str) -> str:
        return f"""
import shutil
from pathlib import Path

targets = [
    Path('/app/instances') / {safe_name!r} / '.zeroclaw' / 'state' / 'matrix',
    Path('/volume') / '.zeroclaw' / 'state' / 'matrix',
]

for target in targets:
    if target.exists():
        shutil.rmtree(target)
"""

    def sync_script(self, direction: str, safe_name: str) -> str:
        return f"""
import os
import shutil
import stat
import tempfile
from pathlib import Path

local = Path('/app/instances') / {safe_name!r}
volume = Path('/volume')
bootstrap = Path('/app/bootstrap')
shared = Path('/app/shared')

def copy_tree(src, dst):
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        try:
            mode = item.lstat().st_mode
        except OSError:
            continue
        if stat.S_ISSOCK(mode) or stat.S_ISFIFO(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
            continue
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            copy_tree(item, target)
        elif item.is_symlink():
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(os.readlink(item))
        else:
            if target.exists() and target.is_dir():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)

def move_dir_contents(src, dst):
    dst.mkdir(parents=True, exist_ok=True)
    for child in list(src.iterdir()):
        shutil.move(str(child), str(dst / child.name))

def mirror_tree(src, dst):
    if not src.exists() or not src.is_dir():
        raise RuntimeError(f'Sync source is missing or not a directory: {{src}}')
    dst.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.zeroclaw-sync-stage.', dir=str(dst)))
    backup = Path(tempfile.mkdtemp(prefix='.zeroclaw-sync-backup.', dir=str(dst)))
    try:
        copy_tree(src, stage)
        for child in list(dst.iterdir()):
            if child == stage or child == backup:
                continue
            shutil.move(str(child), str(backup / child.name))
        move_dir_contents(stage, dst)
    except Exception:
        try:
            for child in list(dst.iterdir()):
                if child == stage or child == backup:
                    continue
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            move_dir_contents(backup, dst)
        except Exception:
            pass
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if backup.exists():
            shutil.rmtree(backup)

if {direction!r} == 'to-runtime':
    mirror_tree(local, volume)
    if bootstrap.exists():
        target = volume / 'bootstrap'
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(bootstrap, target, symlinks=True)
    if shared.exists():
        target = volume / 'shared'
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(shared, target, symlinks=True)
else:
    mirror_tree(volume, local)
    shared_copy = local / 'shared'
    if shared_copy.exists():
        shutil.rmtree(shared_copy)
"""

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

    def image_summary(self, reference: str, kind: str = "custom") -> dict[str, Any]:
        row: dict[str, Any] = {
            "reference": reference,
            "kind": kind,
            "present": False,
        }
        try:
            image = self.inspect_image(reference)
        except DockerApiError as exc:
            if exc.status == 404:
                return row
            row["error"] = {"status": exc.status, "message": exc.message}
            return row
        config = image.get("Config") if isinstance(image.get("Config"), dict) else {}
        labels = config.get("Labels") if isinstance(config.get("Labels"), dict) else {}
        repo_tags = image.get("RepoTags") if isinstance(image.get("RepoTags"), list) else []
        row.update(
            {
                "present": True,
                "id": image.get("Id"),
                "short_id": short_image_id(str(image.get("Id") or "")),
                "repo_tags": repo_tags,
                "created": image.get("Created"),
                "size": image.get("Size"),
                "user": config.get("User") or "",
                "labels": labels,
            }
        )
        return row

    def inspect_image(self, reference: str) -> dict[str, Any]:
        return self.client.request("GET", f"/images/{quote(reference, safe='')}/json")

    def build_derived_image(self, kind: str, base_image: str, target_image: str) -> dict[str, Any]:
        if kind not in {"python", "root"}:
            raise ConfigError("invalid_image_kind", "Unsupported image build kind.", {"kind": kind}, 422)
        if not target_image or any(char.isspace() for char in target_image):
            raise ConfigError("invalid_image_tag", "Target image tag must not be empty or contain whitespace.", {"target_image": target_image}, 422)
        self.pull_image(base_image)
        base_user = ""
        try:
            base = self.inspect_image(base_image)
            config = base.get("Config") if isinstance(base.get("Config"), dict) else {}
            base_user = str(config.get("User") or "")
        except DockerApiError:
            base_user = ""
        dockerfile = self.derived_dockerfile(kind, base_image, base_user)
        context = self.build_context_tar(dockerfile)
        query = {
            "t": target_image,
            "labels": json.dumps(
                {
                    MANAGED_IMAGE_LABEL: "true",
                    IMAGE_KIND_LABEL: kind,
                    "zeroclaw.image.base": base_image,
                },
                sort_keys=True,
            ),
        }
        try:
            raw = self.client.request_bytes(
                "POST",
                "/build",
                context,
                headers={"Content-Type": "application/x-tar"},
                query=query,
                raw=True,
            )
        except DockerApiError as exc:
            if exc.status == 403:
                raise ConfigError(
                    "docker_build_permission_disabled",
                    "Docker build permission is not enabled. Copy .env.example to .env, keep DOCKER_SOCKET_PROXY_BUILD=1, restart Docker Compose, then try building again.",
                    {"target_image": target_image, "base_image": base_image, "status": exc.status},
                    403,
                ) from exc
            raise
        events = decode_build_stream(raw)
        errors = [event for event in events if event.get("error") or event.get("errorDetail")]
        if errors:
            message = str(errors[-1].get("error") or (errors[-1].get("errorDetail") or {}).get("message") or "Docker image build failed.")
            raise ConfigError("image_build_failed", message, {"events": events[-20:]}, 502)
        return {
            "action": f"build-{kind}",
            "base_image": base_image,
            "target_image": target_image,
            "base_user": base_user,
            "events": events[-50:],
            "summary": self.image_summary(target_image, kind),
            "timestamp": self._now(),
        }

    def derived_dockerfile(self, kind: str, base_image: str, base_user: str) -> str:
        if kind == "root":
            return "\n".join(
                [
                    f"FROM {base_image}",
                    "USER root",
                    'LABEL zeroclaw.image.managed="true" zeroclaw.image.kind="root"',
                    "",
                ]
            )
        final_user = base_user.strip() or "zeroclaw"
        return "\n".join(
            [
                f"FROM {base_image}",
                "USER root",
                "RUN apt-get update \\",
                "    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \\",
                "    && rm -rf /var/lib/apt/lists/*",
                f"USER {final_user}",
                'LABEL zeroclaw.image.managed="true" zeroclaw.image.kind="python"',
                "",
            ]
        )

    def build_context_tar(self, dockerfile: str) -> bytes:
        buffer = io.BytesIO()
        encoded = dockerfile.encode("utf-8")
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            info = tarfile.TarInfo("Dockerfile")
            info.size = len(encoded)
            info.mtime = int(datetime.now(timezone.utc).timestamp())
            archive.addfile(info, io.BytesIO(encoded))
        return buffer.getvalue()

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
    """Development-only Docker controller used by tests and UI-only local runs."""

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
            "health_status": "",
            "restart_count": 0,
            "details": {
                "message": "Docker status is stubbed.",
            },
        }

    def logs(self, config: dict[str, Any], agent: dict[str, Any], tail: int = 200) -> dict[str, Any]:
        return {
            "agent_id": self._agent_id(agent),
            "controller": "fake",
            "tail": tail,
            "fetched_at": self._now(),
            "lines": [],
            "details": {
                "message": "Docker logs are stubbed.",
            },
        }

    def sync_to_runtime(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("sync-to-runtime", agent, "stubbed")

    def sync_from_runtime(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("sync-from-runtime", agent, "stubbed")

    def reset_matrix_state(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        return self._operation("reset-matrix-state", agent, "stubbed")

    def audit_resources(self, config: dict[str, Any], decisions: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "checked_at": self._now(),
            "expected": {"containers": [], "volumes": [], "networks": [], "errors": []},
            "containers": {"expected": [], "orphans": [], "legacy": [], "conflicts": []},
            "volumes": {"expected": [], "orphans": [], "legacy": [], "conflicts": []},
            "networks": {"expected": [], "orphans": [], "legacy": [], "conflicts": []},
            "controller": "fake",
        }

    def resource_action(self, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        return {"action": payload.get("action"), "kind": payload.get("kind"), "name": payload.get("name"), "controller": "fake", "timestamp": self._now()}

    def image_inventory(self, config: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
        defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
        official = str(defaults.get("zeroclaw_image") or DEFAULT_IMAGE)
        return {
            "checked_at": self._now(),
            "default_image": official,
            "recommended": {"official": official, "python": DEFAULT_PYTHON_IMAGE, "root": DEFAULT_ROOT_IMAGE},
            "state": state or {"acknowledged": {}},
            "images": [
                {"reference": official, "kind": "official", "present": False},
                {"reference": DEFAULT_PYTHON_IMAGE, "kind": "python", "present": False},
                {"reference": DEFAULT_ROOT_IMAGE, "kind": "root", "present": False},
            ],
            "controller": "fake",
        }

    def image_action(self, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        return {"action": payload.get("action"), "controller": "fake", "timestamp": self._now()}

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
        return str(agent.get("id") or "")

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
        shared_dir: Path,
        instance_dir: Path,
        local_instance_dir: Path,
        storage_driver: str,
        volume_name: str,
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
        self.shared_dir = shared_dir
        self.instance_dir = instance_dir
        self.local_instance_dir = local_instance_dir
        self.storage_driver = storage_driver
        self.volume_name = volume_name
        self.environment = environment
        self.labels = labels
        self.extra_hosts = extra_hosts
        self.spec_hash = spec_hash


def build_controller_from_env(project_root: Path) -> DockerController:
    docker_api_url = os.getenv("DOCKER_API_URL", "http://docker-socket-proxy:2375")
    mode = os.getenv("DOCKER_CONTROLLER", "api").lower()
    if mode == "fake":
        return FakeDockerController(docker_api_url)
    timeout_secs = int(os.getenv("DOCKER_API_TIMEOUT_SECS", "30"))
    return DockerApiController(docker_api_url, project_root, timeout_secs=timeout_secs)


def safe_container_part(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-._")
    return safe.lower() or "agent"


def safe_volume_part(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-._")
    return safe.lower() or "zeroclaw"


def first_item(value: Any) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value.split(",", 1)[0].strip()
    return ""


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


def decode_build_stream(body: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in body.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = {"stream": line}
        if isinstance(event, dict):
            events.append(event)
    return events


def short_image_id(image_id: str) -> str:
    value = image_id.removeprefix("sha256:")
    return value[:12] if value else ""
