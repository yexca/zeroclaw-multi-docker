"""Configuration persistence and collection helpers for the manager API."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml


PROFILE_COLLECTIONS = {
    "llm": ("profiles", "llm"),
    "vision": ("profiles", "vision"),
    "matrix": ("profiles", "matrix"),
    "mcp": ("profiles", "mcp"),
}

PROMPT_TEMPLATE_KEY = "prompt_templates"
SKILL_BUNDLE_KEY = "skill_bundles"
DEFAULT_PROMPT_TEMPLATE_FILES = [
    "AGENTS.md",
    "SOUL.md",
    "TOOLS.md",
    "IDENTITY.md",
    "USER.md",
    "MEMORY.md",
    "HEARTBEAT.md",
    "PROACTIVE.md",
]
MODULE_COLLECTIONS = {
    "llm": ("profiles", "llm", "llm_dir"),
    "vision": ("profiles", "vision", "vision_dir"),
    "matrix": ("profiles", "matrix", "matrix_dir"),
    "mcp": ("profiles", "mcp", "mcp_dir"),
    "agents": ("agents", None, "agents_dir"),
    "skill_bundles": ("skill_bundles", None, "skills_dir"),
}
DEFAULT_CONFIG_MODULES = {
    "llm_dir": "config/llm",
    "vision_dir": "config/vision",
    "matrix_dir": "config/matrix",
    "mcp_dir": "config/mcp",
    "agents_dir": "config/agents",
    "prompts_dir": "config/prompts",
    "skills_dir": "config/skills",
    "secrets_file": "config/secrets.yaml",
}
MOJIBAKE_MARKERS = ("\u9287", "\u935d", "\u93c0", "\u20ac", "\ufffd", "\u6d93", "\u7d31", "\u9428")


class ConfigError(Exception):
    """Structured error raised by config store operations."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status = status


def default_config() -> dict[str, Any]:
    return {
        "version": 1,
        "webui": {
            "default_language": "en",
            "default_theme": "system",
        },
        "server": {
            "bind_host": "127.0.0.1",
            "host_port": 7652,
        },
        "docker": {
            "proxy_url": "http://docker-socket-proxy:2375",
            "project_name": "zeroclaw-dockyard",
            "control_network": "zeroclaw-dockyard_manager-control",
            "storage_driver": "volume",
            "volume_prefix": "zeroclaw-dockyard",
        },
        "paths": {
            "secrets_file": "/app/config/secrets.yaml",
            "generated_dir": "/app/config/generated",
            "instances_dir": "/app/instances",
        },
        "profiles": {
            "llm": [],
            "vision": [
                {
                    "id": "vision-default",
                    "provider_family": "custom",
                    "provider_alias": "vision",
                    "model": "gpt-4o",
                    "base_url": "https://api.openai.com/v1",
                    "wire_api": "chat_completions",
                    "timeout_secs": 120,
                    "allow_remote_fetch": False,
                    "max_images": 4,
                    "max_image_size_mb": 5,
                    "max_image_turns": 2,
                }
            ],
            "matrix": [],
            "mcp": [],
        },
        "skills": {
            "allow_scripts": False,
            "open_skills_enabled": False,
            "registry_url": "https://github.com/zeroclaw-labs/zeroclaw-skills",
            "prompt_injection_mode": "full",
            "extra_registries": [],
            "skill_creation": {
                "enabled": False,
                "max_skills": 500,
                "similarity_threshold": 0.85,
            },
            "install_suggestions": {
                "enabled": False,
            },
            "skill_improvement": {
                "enabled": False,
                "cooldown_secs": 3600,
                "nudge_interval_iterations": 10,
                "max_review_iterations": 8,
            },
        },
        "skill_bundles": [
            {
                "id": "core",
                "directory": "shared/skills/core",
                "include": [],
                "exclude": [],
            }
        ],
        "prompt_templates": [],
        "agents": [],
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def item_id(item: dict[str, Any]) -> str | None:
    for key in ("id", "alias", "server_name"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    family = item.get("family")
    alias = item.get("alias")
    if isinstance(family, str) and isinstance(alias, str) and family and alias:
        return f"{family}:{alias}"
    return None


def normalize_collection(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [copy.deepcopy(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        collection: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, dict):
                normalized = copy.deepcopy(item)
                normalized.setdefault("id", str(key))
                collection.append(normalized)
        return collection
    return []


def safe_file_stem(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value).strip()).strip("-._")
    return safe or "item"


class ConfigStore:
    def __init__(self, config_path: Path, example_path: Path, generated_dir: Path):
        self.config_path = config_path
        self.example_path = example_path
        self.generated_dir = generated_dir
        self.agent_status_provider: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None
        try:
            from agent_renderer import AgentRenderer
            from config_validator import ConfigValidator
        except ModuleNotFoundError:  # pragma: no cover - package import path for tests
            from .agent_renderer import AgentRenderer
            from .config_validator import ConfigValidator
        project_root = config_path.resolve().parents[1] if len(config_path.resolve().parents) > 1 else Path.cwd()
        self.project_root = project_root
        self.renderer = AgentRenderer(project_root)
        self.validator = ConfigValidator(project_root)

    def load(self) -> dict[str, Any]:
        path = self.config_path if self.config_path.exists() else self.example_path
        raw = self._read_yaml(path)
        if not isinstance(raw, dict):
            raw = {}
        if not self._module_mode(raw):
            raise ConfigError(
                "legacy_config_requires_migration",
                "manager.yaml must use modular config. Run tools/migrate-config.py to split a legacy single-file config.",
                {"path": str(path)},
                409,
            )
        raw = self._load_module_config(raw, path)
        return self._normalize(raw)

    def save(self, config: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize(config)
        if self._module_mode(normalized):
            self._save_module_config(normalized)
        else:
            self._atomic_write_yaml(self.config_path, normalized)
        return normalized

    def update_full_config(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ConfigError("invalid_payload", "Configuration payload must be an object.")
        if not self._module_mode(payload):
            raise ConfigError(
                "legacy_config_requires_migration",
                "Full config writes must use modular config. Run tools/migrate-config.py for legacy single-file configs.",
                status=409,
            )
        normalized = self._normalize(payload)
        validation = self.validator.validate_config(normalized, check_ports=False)
        if validation["errors"]:
            raise ConfigError("validation_failed", "Configuration has validation errors.", validation, 422)
        self.ensure_runtime_config_editable(self.load(), normalized)
        return self.save(normalized)

    def list_collection(self, kind: str) -> list[dict[str, Any]]:
        config = self.load()
        return copy.deepcopy(self._get_collection(config, kind))

    def get_item(self, kind: str, identifier: str) -> dict[str, Any]:
        config = self.load()
        collection = self._get_collection(config, kind)
        index = self._find_index(collection, identifier)
        if index is None:
            raise ConfigError("not_found", f"{kind} item was not found.", {"id": identifier}, 404)
        return copy.deepcopy(collection[index])

    def create_item(self, kind: str, payload: Any) -> dict[str, Any]:
        item = self._validate_item_payload(payload)
        identifier = item_id(item)
        if not identifier:
            raise ConfigError("missing_id", "Item must include one of id, alias, or server_name.")
        config = self.load()
        collection = self._get_collection(config, kind)
        if any(item_id(existing) == identifier for existing in collection):
            raise ConfigError("duplicate_id", f"{kind} item already exists.", {"id": identifier}, 409)
        collection.append(item)
        self.save(config)
        return copy.deepcopy(item)

    def update_item(self, kind: str, identifier: str, payload: Any) -> dict[str, Any]:
        item = self._validate_item_payload(payload)
        item.setdefault("id", identifier)
        config = self.load()
        self.ensure_item_editable(config, kind, identifier, item)
        collection = self._get_collection(config, kind)
        index = self._find_index(collection, identifier)
        if index is None:
            raise ConfigError("not_found", f"{kind} item was not found.", {"id": identifier}, 404)
        new_identifier = item_id(item)
        if new_identifier != identifier and any(item_id(existing) == new_identifier for existing in collection):
            raise ConfigError("duplicate_id", f"{kind} item already exists.", {"id": new_identifier}, 409)
        collection[index] = item
        self.save(config)
        return copy.deepcopy(item)

    def delete_item(self, kind: str, identifier: str) -> dict[str, Any]:
        config = self.load()
        self.ensure_item_editable(config, kind, identifier, None)
        collection = self._get_collection(config, kind)
        index = self._find_index(collection, identifier)
        if index is None:
            raise ConfigError("not_found", f"{kind} item was not found.", {"id": identifier}, 404)
        deleted = collection.pop(index)
        self.save(config)
        return copy.deepcopy(deleted)

    def list_agents(self) -> list[dict[str, Any]]:
        config = self.load()
        return copy.deepcopy(normalize_collection(config.get("agents")))

    def get_agent(self, identifier: str) -> dict[str, Any]:
        agents = self.list_agents()
        index = self._find_index(agents, identifier)
        if index is None:
            raise ConfigError("not_found", "Agent was not found.", {"id": identifier}, 404)
        return agents[index]

    def create_agent(self, payload: Any) -> dict[str, Any]:
        agent = self.create_item("agents", payload)
        config = self.load()
        mode = "keep"
        if isinstance(payload, dict) and isinstance(payload.get("workspace_mode"), str):
            mode = payload["workspace_mode"]
        result = copy.deepcopy(agent)
        try:
            result["workspace"] = self.renderer.initialize_workspace(config, agent, mode=mode)
        except ConfigError as exc:
            result["workspace"] = {
                "initialized": False,
                "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            }
        return result

    def update_agent(self, identifier: str, payload: Any) -> dict[str, Any]:
        return self.update_item("agents", identifier, payload)

    def delete_agent(self, identifier: str, delete_instance_dir: bool = False) -> dict[str, Any]:
        config = self.load()
        agent = self.get_agent(identifier)
        deleted = self.delete_item("agents", identifier)
        result = {"agent": deleted, "instance_dir_deleted": False}
        if delete_instance_dir:
            instance_dir = self.renderer.workspace_dir(config, agent).parent.resolve()
            instances_dir = Path(str(config.get("paths", {}).get("instances_dir") or self.config_path.resolve().parents[1] / "instances")).resolve()
            if instances_dir != instance_dir and instances_dir not in instance_dir.parents:
                raise ConfigError("unsafe_instance_path", "Refusing to delete an instance directory outside instances_dir.", {"path": str(instance_dir)}, 409)
            if instance_dir.exists():
                shutil.rmtree(instance_dir)
                result["instance_dir_deleted"] = True
        return result

    def validate_agent(self, identifier: str) -> dict[str, Any]:
        config = self.load()
        agent = self.get_agent(identifier)
        result = self.validator.validate_agent(config, agent, check_ports=False)
        result["agent"] = agent
        return result

    def validate_config(self) -> dict[str, Any]:
        return self.validator.validate_config(self.load(), check_ports=False)

    def export(self, payload: Any | None = None) -> dict[str, Any]:
        config = self.load()
        export_name = "resolved.yaml"
        export_payload: Any = config
        include_secrets = isinstance(payload, dict) and payload.get("include_secrets") is True
        if isinstance(payload, dict) and isinstance(payload.get("filename"), str) and payload["filename"].strip():
            export_name = Path(payload["filename"]).name
        if isinstance(payload, dict) and payload.get("agent"):
            agent = self.get_agent(str(payload["agent"]))
            formats = payload.get("formats") if isinstance(payload.get("formats"), list) else None
            export_payload = self.renderer.export_agent(config, agent, formats=formats, include_secrets=include_secrets)
        if not include_secrets:
            export_payload = redact(export_payload)
        target = self.generated_dir / export_name
        self._atomic_write_yaml(target, export_payload)
        return {"path": str(target), "config": export_payload, "include_secrets": include_secrets}

    def resource_decisions_path(self) -> Path:
        return self.generated_dir / "docker-resource-decisions.json"

    def load_resource_decisions(self) -> dict[str, Any]:
        path = self.resource_decisions_path()
        if not path.exists():
            return {"ignored": [], "adopted": []}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"ignored": [], "adopted": []}
        return {
            "ignored": [item for item in raw.get("ignored", []) if isinstance(item, dict)] if isinstance(raw, dict) else [],
            "adopted": [item for item in raw.get("adopted", []) if isinstance(item, dict)] if isinstance(raw, dict) else [],
        }

    def update_resource_decision(self, action: str, kind: str, name: str) -> dict[str, Any]:
        if action not in {"ignore", "adopt", "clear"}:
            raise ConfigError("invalid_resource_action", "Unsupported resource decision action.", {"action": action}, 422)
        if kind not in {"container", "volume", "network"}:
            raise ConfigError("invalid_resource_kind", "Unsupported Docker resource kind.", {"kind": kind}, 422)
        if not name:
            raise ConfigError("missing_resource_name", "Docker resource name is required.", status=422)
        decisions = self.load_resource_decisions()
        for bucket in ("ignored", "adopted"):
            decisions[bucket] = [
                item for item in decisions.get(bucket, [])
                if not (item.get("kind") == kind and item.get("name") == name)
            ]
        if action in {"ignore", "adopt"}:
            key = "ignored" if action == "ignore" else "adopted"
            decisions[key].append({
                "kind": kind,
                "name": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        self._atomic_write_json(self.resource_decisions_path(), decisions)
        return decisions

    def image_state_path(self) -> Path:
        return self.generated_dir / "docker-image-state.json"

    def load_image_state(self) -> dict[str, Any]:
        path = self.image_state_path()
        if not path.exists():
            return {"acknowledged": {}}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"acknowledged": {}}
        acknowledged = raw.get("acknowledged") if isinstance(raw, dict) else {}
        return {"acknowledged": acknowledged if isinstance(acknowledged, dict) else {}}

    def acknowledge_image_risk(self, kind: str) -> dict[str, Any]:
        if kind not in {"python", "root"}:
            raise ConfigError("invalid_image_kind", "Unsupported image build kind.", {"kind": kind}, 422)
        state = self.load_image_state()
        acknowledged = state.setdefault("acknowledged", {})
        acknowledged[kind] = {
            "accepted": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._atomic_write_json(self.image_state_path(), state)
        return state

    def apply_prompt_template(self, identifier: str, payload: Any | None = None) -> dict[str, Any]:
        mode = "keep"
        if isinstance(payload, dict) and isinstance(payload.get("mode"), str):
            mode = payload["mode"]
        config = self.load()
        agent = self.get_agent(identifier)
        self.ensure_agents_stopped(config, [agent], "runtime_workspace_in_use")
        return self.renderer.initialize_workspace(config, agent, mode=mode)

    def publish_agent(self, identifier: str, payload: Any | None, sync_runtime: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None) -> dict[str, Any]:
        mode = "keep"
        agent_payload: Any | None = None
        sync = True
        if isinstance(payload, dict):
            if isinstance(payload.get("mode"), str):
                mode = payload["mode"]
            if isinstance(payload.get("agent"), dict):
                agent_payload = payload["agent"]
            if payload.get("sync_runtime") is False:
                sync = False

        saved = None
        target_id = identifier
        if agent_payload is not None:
            existing_ids = {str(item_id(agent) or "") for agent in self.list_agents()}
            if identifier and identifier in existing_ids:
                saved = self.update_agent(identifier, agent_payload)
            else:
                saved = self.create_item("agents", agent_payload)
            target_id = str(item_id(saved) or target_id)

        config = self.load()
        agent = self.get_agent(target_id)
        validation = self.validator.validate_agent(config, agent, check_ports=False)
        if validation["errors"]:
            raise ConfigError("validation_failed", "Agent configuration has validation errors.", validation, 422)

        self.ensure_agents_stopped(config, [agent], "runtime_publish_in_use")
        workspace = self.renderer.initialize_workspace(config, agent, mode=mode)
        runtime = sync_runtime(config, agent) if sync and sync_runtime else None
        return {
            "agent": copy.deepcopy(agent),
            "saved": saved,
            "validation": validation,
            "workspace": workspace,
            "runtime": runtime,
            "published": True,
        }

    def rotate_matrix_device_id(self, identifier: str) -> dict[str, Any]:
        config = self.load()
        self.ensure_item_editable(config, "agents", identifier, None)
        agents = config.get("agents") if isinstance(config.get("agents"), list) else []
        index = self._find_index(agents, identifier)
        if index is None:
            raise ConfigError("not_found", "Agent was not found.", {"id": identifier}, 404)
        agent = copy.deepcopy(agents[index])
        matrix = agent.get("matrix") if isinstance(agent.get("matrix"), dict) else {}
        previous_device_id = matrix.get("device_id") if isinstance(matrix.get("device_id"), str) else ""
        matrix.pop("device_id", None)
        if matrix:
            agent["matrix"] = matrix
        else:
            agent.pop("matrix", None)
        agents[index] = agent
        config["agents"] = agents
        self.save(config)
        return {
            "agent": copy.deepcopy(agent),
            "previous_device_id": previous_device_id,
            "device_id": "",
        }

    def set_agent_status_provider(self, provider: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None) -> None:
        self.agent_status_provider = provider

    def ensure_item_editable(self, config: dict[str, Any], kind: str, identifier: str, replacement: dict[str, Any] | None) -> None:
        affected = self.affected_agents_for_item(config, kind, identifier, replacement)
        self.ensure_agents_stopped(config, affected, "runtime_config_in_use")

    def ensure_runtime_config_editable(self, previous: dict[str, Any], updated: dict[str, Any]) -> None:
        affected: dict[str, dict[str, Any]] = {}
        previous_agents = {str(item_id(agent) or ""): agent for agent in normalize_collection(previous.get("agents"))}
        updated_agents = {str(item_id(agent) or ""): agent for agent in normalize_collection(updated.get("agents"))}
        for identifier in sorted(set(previous_agents) | set(updated_agents)):
            if not identifier:
                continue
            if previous_agents.get(identifier) != updated_agents.get(identifier):
                agent = previous_agents.get(identifier) or updated_agents.get(identifier)
                if agent:
                    affected[identifier] = agent

        for kind in PROFILE_COLLECTIONS:
            previous_items = self.collection_by_id(previous, kind)
            updated_items = self.collection_by_id(updated, kind)
            for identifier in sorted(set(previous_items) | set(updated_items)):
                if previous_items.get(identifier) != updated_items.get(identifier):
                    for agent in self.agents_using_item(previous, kind, identifier) + self.agents_using_item(updated, kind, identifier):
                        affected[str(item_id(agent) or "")] = agent

        previous_prompts = self.collection_by_id(previous, "prompt_templates")
        updated_prompts = self.collection_by_id(updated, "prompt_templates")
        for identifier in sorted(set(previous_prompts) | set(updated_prompts)):
            if previous_prompts.get(identifier) != updated_prompts.get(identifier):
                for agent in self.agents_using_item(previous, "prompt_templates", identifier) + self.agents_using_item(updated, "prompt_templates", identifier):
                    affected[str(item_id(agent) or "")] = agent

        self.ensure_agents_stopped(previous, [agent for key, agent in affected.items() if key], "runtime_config_in_use")

    def affected_agents_for_item(
        self, config: dict[str, Any], kind: str, identifier: str, replacement: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        if kind == "agents":
            agents = normalize_collection(config.get("agents"))
            index = self._find_index(agents, identifier)
            return [agents[index]] if index is not None else []
        if kind in PROFILE_COLLECTIONS or kind == "prompt_templates":
            affected = self.agents_using_item(config, kind, identifier)
            replacement_id = item_id(replacement) if replacement else None
            if replacement_id and replacement_id != identifier:
                affected.extend(self.agents_using_item(config, kind, replacement_id))
            return affected
        return []

    def agents_using_item(self, config: dict[str, Any], kind: str, identifier: str) -> list[dict[str, Any]]:
        agents = normalize_collection(config.get("agents"))
        key_by_kind = {
            "llm": "llm_profile",
            "vision": "vision_profile",
            "matrix": "matrix_profile",
            "mcp": "mcp_profile",
            "prompt_templates": "prompt_template",
        }
        key = key_by_kind.get(kind)
        if not key:
            return []
        return [agent for agent in agents if agent.get(key) == identifier]

    def affected_agent_ids_for_item(self, kind: str, identifier: str) -> list[str]:
        config = self.load()
        return [str(item_id(agent) or "") for agent in self.affected_agents_for_item(config, kind, identifier, None) if item_id(agent)]

    def collection_by_id(self, config: dict[str, Any], kind: str) -> dict[str, dict[str, Any]]:
        return {str(item_id(item) or ""): item for item in self._get_collection(config, kind) if item_id(item)}

    def ensure_agents_stopped(self, config: dict[str, Any], agents: list[dict[str, Any]], code: str) -> None:
        if not self.agent_status_provider:
            return
        seen: set[str] = set()
        running: list[dict[str, Any]] = []
        for agent in agents:
            identifier = str(item_id(agent) or "")
            if not identifier or identifier in seen:
                continue
            seen.add(identifier)
            status = self.agent_status_provider(config, agent)
            if bool(status.get("running")):
                running.append({"id": identifier, "name": agent.get("name") or identifier, "state": status.get("state") or "running"})
        if running:
            raise ConfigError(
                code,
                "This configuration is used by a running agent. Stop the agent container before changing it.",
                {"agents": running},
                409,
            )

    def agent_workspace_initialized(self, config: dict[str, Any], agent: dict[str, Any]) -> bool:
        workspace = self.renderer.workspace_dir(config, agent)
        if not workspace.is_dir():
            return False
        try:
            return any(workspace.iterdir())
        except OSError:
            return False

    def render_agent(self, identifier: str, formats: list[str] | None = None) -> dict[str, Any]:
        config = self.load()
        agent = self.get_agent(identifier)
        return self.renderer.export_agent(config, agent, formats=formats, include_secrets=False)

    def _module_mode(self, config: dict[str, Any]) -> bool:
        return isinstance(config.get("config_modules"), dict)

    def _module_paths(self, config: dict[str, Any]) -> dict[str, Path]:
        modules = deep_merge(DEFAULT_CONFIG_MODULES, config.get("config_modules") if isinstance(config.get("config_modules"), dict) else {})
        paths: dict[str, Path] = {}
        for key, value in modules.items():
            path = Path(str(value or DEFAULT_CONFIG_MODULES.get(key, "")))
            paths[key] = path if path.is_absolute() else self.project_root / path
        return paths

    def _load_module_config(self, raw: dict[str, Any], source_path: Path) -> dict[str, Any]:
        if not self._module_mode(raw):
            return raw
        config = copy.deepcopy(raw)
        paths = self._module_paths(config)
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        profiles = copy.deepcopy(profiles)
        for kind, (top_key, child_key, dir_key) in MODULE_COLLECTIONS.items():
            directory = paths.get(dir_key)
            if not directory:
                continue
            items = self._read_module_collection(directory)
            if not items:
                continue
            if top_key == "profiles" and child_key:
                profiles[child_key] = items
            else:
                config[top_key] = items
        if profiles:
            config["profiles"] = profiles
        prompts_dir = paths.get("prompts_dir")
        if prompts_dir:
            prompts = self._read_prompt_modules(prompts_dir)
            if prompts:
                config[PROMPT_TEMPLATE_KEY] = prompts
        config.setdefault("paths", {})
        if isinstance(config["paths"], dict) and paths.get("secrets_file"):
            config["paths"].setdefault("secrets_file", str(paths["secrets_file"]))
        config["_config_modules_loaded_from"] = str(source_path)
        return config

    def _read_module_collection(self, directory: Path) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not directory.is_dir():
            return items
        for path in sorted(directory.glob("*.yaml")):
            if path.name.endswith(".example.yaml") or path.stem in {"example", "manifest"}:
                continue
            raw = self._read_yaml(path)
            if isinstance(raw, dict):
                item = copy.deepcopy(raw)
                item.setdefault("id", path.stem)
                items.append(item)
        return items

    def _read_prompt_modules(self, directory: Path) -> list[dict[str, Any]]:
        templates: list[dict[str, Any]] = []
        if not directory.is_dir():
            return templates
        for prompt_dir in sorted(child for child in directory.iterdir() if child.is_dir() and child.name != "example"):
            manifest_path = prompt_dir / "manifest.yaml"
            manifest = self._read_yaml(manifest_path) if manifest_path.exists() else {}
            if not isinstance(manifest, dict):
                manifest = {}
            template_id = str(manifest.get("id") or prompt_dir.name)
            files = self._read_prompt_files(prompt_dir, manifest.get("files"))
            template = {
                "id": template_id,
                "name": str(manifest.get("name") or template_id),
                "description": str(manifest.get("description") or ""),
                "files": files,
                "source_dir": str(prompt_dir),
            }
            warnings = self._prompt_warnings(files)
            if warnings:
                template["warnings"] = warnings
            templates.append(template)
        return templates

    def _read_prompt_files(self, prompt_dir: Path, manifest_files: Any) -> dict[str, str]:
        files: dict[str, str] = {}
        if isinstance(manifest_files, dict):
            entries = {str(name): str(path) for name, path in manifest_files.items()}
        else:
            entries = {path.name: path.name for path in sorted(prompt_dir.glob("*.md"))}
        for filename, relative in entries.items():
            if not self._safe_module_filename(filename) or "/" in relative or "\\" in relative:
                continue
            path = prompt_dir / relative
            try:
                files[filename] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise ConfigError("invalid_utf8_prompt", "Prompt file must be UTF-8.", {"path": str(path), "error": str(exc)}, 422) from exc
            except OSError:
                files[filename] = ""
        return files

    def _save_module_config(self, config: dict[str, Any]) -> None:
        paths = self._module_paths(config)
        root_payload = self._module_root_payload(config)
        self._atomic_write_yaml(self.config_path, root_payload)
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        for kind, (_top_key, child_key, dir_key) in MODULE_COLLECTIONS.items():
            directory = paths.get(dir_key)
            if not directory:
                continue
            if child_key:
                items = profiles.get(child_key) if isinstance(profiles.get(child_key), list) else []
            else:
                items = config.get(kind) if isinstance(config.get(kind), list) else []
            self._write_module_collection(directory, items)
        prompts_dir = paths.get("prompts_dir")
        if prompts_dir:
            self._write_prompt_modules(prompts_dir, config.get(PROMPT_TEMPLATE_KEY) if isinstance(config.get(PROMPT_TEMPLATE_KEY), list) else [])

    def _module_root_payload(self, config: dict[str, Any]) -> dict[str, Any]:
        excluded = {"profiles", "agents", PROMPT_TEMPLATE_KEY, SKILL_BUNDLE_KEY, "_config_modules_loaded_from"}
        payload = {key: copy.deepcopy(value) for key, value in config.items() if key not in excluded}
        payload["version"] = max(2, int(payload.get("version") or 2))
        payload.setdefault("config_modules", copy.deepcopy(DEFAULT_CONFIG_MODULES))
        return payload

    def _write_module_collection(self, directory: Path, items: list[Any]) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        expected_files: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            identifier = item_id(item)
            if not identifier:
                continue
            filename = f"{safe_file_stem(identifier)}.yaml"
            expected_files.add(filename)
            path = directory / filename
            self._atomic_write_yaml(path, copy.deepcopy(item))
        for path in directory.glob("*.yaml"):
            if path.name.endswith(".example.yaml") or path.stem in {"example", "manifest"}:
                continue
            if path.name not in expected_files:
                path.unlink()

    def _write_prompt_modules(self, directory: Path, templates: list[Any]) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        expected_dirs: set[str] = set()
        for template in templates:
            if not isinstance(template, dict):
                continue
            template_id = item_id(template)
            if not template_id:
                continue
            dirname = safe_file_stem(template_id)
            expected_dirs.add(dirname)
            prompt_dir = directory / dirname
            prompt_dir.mkdir(parents=True, exist_ok=True)
            files = template.get("files") if isinstance(template.get("files"), dict) else {}
            manifest_files: dict[str, str] = {}
            for filename, content in files.items():
                if not self._safe_module_filename(str(filename)):
                    continue
                target = prompt_dir / str(filename)
                target.write_text(str(content), encoding="utf-8")
                manifest_files[str(filename)] = str(filename)
            manifest = {
                "id": str(template_id),
                "name": str(template.get("name") or template_id),
                "description": str(template.get("description") or ""),
                "encoding": "utf-8",
                "files": manifest_files,
            }
            warnings = self._prompt_warnings({str(k): str(v) for k, v in files.items()})
            if warnings:
                manifest["warnings"] = warnings
            self._atomic_write_yaml(prompt_dir / "manifest.yaml", manifest)
        for prompt_dir in directory.iterdir():
            if not prompt_dir.is_dir() or prompt_dir.name == "example":
                continue
            if prompt_dir.name not in expected_dirs:
                shutil.rmtree(prompt_dir)

    def _prompt_warnings(self, files: dict[str, str]) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        for filename, content in files.items():
            markers = [marker for marker in MOJIBAKE_MARKERS if marker in content]
            if markers:
                warnings.append({"code": "possible_mojibake", "file": filename, "markers": markers[:5]})
        return warnings

    def _safe_module_filename(self, filename: str) -> bool:
        text = str(filename or "").strip()
        return bool(text) and len(text) <= 128 and "/" not in text and "\\" not in text and ".." not in Path(text).parts

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        config = deep_merge(default_config(), raw)
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        vision_profiles = normalize_collection(profiles.get("vision"))
        config["profiles"] = {
            "llm": normalize_collection(profiles.get("llm")),
            "vision": vision_profiles,
            "matrix": normalize_collection(profiles.get("matrix")),
            "mcp": normalize_collection(profiles.get("mcp")),
        }
        for profile in config["profiles"]["matrix"]:
            self._normalize_matrix_login_profile(profile)
        config[PROMPT_TEMPLATE_KEY] = normalize_collection(config.get(PROMPT_TEMPLATE_KEY))
        config[PROMPT_TEMPLATE_KEY] = self._normalize_prompt_templates(config[PROMPT_TEMPLATE_KEY])
        config[SKILL_BUNDLE_KEY] = self._normalize_skill_bundles(config.get(SKILL_BUNDLE_KEY))
        if not isinstance(config.get("skills"), dict):
            config["skills"] = default_config()["skills"]
        config["skills"] = self._normalize_skills_config(config["skills"])
        config["agents"] = normalize_collection(config.get("agents"))
        for agent in config["agents"]:
            agent["skill_bundles"] = self._normalize_string_list(agent.get("skill_bundles"))
            self._strip_agent_matrix_device_id(agent)
        return config

    def _strip_agent_matrix_device_id(self, agent: dict[str, Any]) -> None:
        matrix = agent.get("matrix")
        if not isinstance(matrix, dict):
            return
        matrix.pop("device_id", None)
        if not matrix:
            agent.pop("matrix", None)

    def _normalize_matrix_login_profile(self, profile: dict[str, Any]) -> None:
        mode = str(profile.get("login_mode") or "").strip().lower()
        if mode not in {"account", "token", "advanced"}:
            mode = "token" if str(profile.get("access_token") or "").strip() else "account"
        profile["login_mode"] = mode
        if mode == "advanced":
            return
        if mode == "token":
            profile.pop("password", None)
            profile.pop("recovery_key", None)
        else:
            profile.pop("access_token", None)
            profile.pop("device_id", None)

    def _normalize_prompt_templates(self, templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        defaults = self._default_prompt_template_files()
        if not templates:
            return []
        for template in templates:
            files = template.get("files")
            if not isinstance(files, dict):
                files = {}
            normalized_files = {str(key): str(value) for key, value in files.items()}
            for filename in defaults:
                if filename not in normalized_files:
                    normalized_files[filename] = ""
            template["files"] = {
                **{filename: normalized_files[filename] for filename in defaults if filename in normalized_files},
                **{filename: normalized_files[filename] for filename in sorted(normalized_files) if filename not in defaults},
            }
        return templates

    def prompt_template_examples(self) -> dict[str, str]:
        return self._default_prompt_template_files()

    def _normalize_skill_bundles(self, value: Any) -> list[dict[str, Any]]:
        bundles = normalize_collection(value)
        if not bundles:
            bundles = [{"id": "core", "directory": "shared/skills/core", "include": [], "exclude": []}]
        for bundle in bundles:
            identifier = item_id(bundle)
            if identifier:
                bundle["id"] = str(identifier)
            bundle["include"] = self._normalize_string_list(bundle.get("include"))
            bundle["exclude"] = self._normalize_string_list(bundle.get("exclude"))
            if bundle.get("directory") is not None:
                bundle["directory"] = str(bundle.get("directory") or "")
        return bundles

    def _normalize_skills_config(self, value: dict[str, Any]) -> dict[str, Any]:
        defaults = default_config()["skills"]
        result = deep_merge(defaults, value if isinstance(value, dict) else {})
        mode = str(result.get("prompt_injection_mode") or "full").strip().lower()
        result["prompt_injection_mode"] = mode if mode in {"full", "compact"} else "full"
        result["allow_scripts"] = bool(result.get("allow_scripts"))
        result["open_skills_enabled"] = bool(result.get("open_skills_enabled"))
        result["extra_registries"] = [item for item in result.get("extra_registries", []) if isinstance(item, dict)]
        return result

    def _normalize_string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        return []

    def _default_prompt_template_files(self) -> dict[str, str]:
        module_dirs = self._module_paths({"config_modules": DEFAULT_CONFIG_MODULES})
        template_dirs = [
            module_dirs["prompts_dir"] / "example",
            Path(__file__).resolve().parent / "prompt_templates",
        ]
        result: dict[str, str] = {}
        for filename in DEFAULT_PROMPT_TEMPLATE_FILES:
            result[filename] = ""
            for template_dir in template_dirs:
                path = template_dir / filename
                try:
                    result[filename] = path.read_text(encoding="utf-8")
                    break
                except OSError:
                    continue
        return result

    def _get_collection(self, config: dict[str, Any], kind: str) -> list[dict[str, Any]]:
        if kind in PROFILE_COLLECTIONS:
            parent, child = PROFILE_COLLECTIONS[kind]
            return config[parent][child]
        if kind == "prompt_templates":
            return config[PROMPT_TEMPLATE_KEY]
        if kind == "skill_bundles":
            return config[SKILL_BUNDLE_KEY]
        if kind == "agents":
            return config["agents"]
        raise ConfigError("unknown_collection", "Unknown collection type.", {"kind": kind}, 404)

    def _find_index(self, collection: list[dict[str, Any]], identifier: str) -> int | None:
        for index, item in enumerate(collection):
            if item_id(item) == identifier:
                return index
        return None

    def _validate_item_payload(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ConfigError("invalid_payload", "Payload must be an object.")
        return copy.deepcopy(payload)

    def _read_yaml(self, path: Path) -> Any:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _atomic_write_yaml(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _atomic_write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, sort_keys=True, indent=2, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def redact(value: Any) -> Any:
    secret_words = ("api_key", "token", "password", "recovery_key", "secret", "key")
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if any(word in str(key).lower() for word in secret_words):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def to_json(data: Any) -> str:
    return json.dumps(redact(data), sort_keys=True, ensure_ascii=True)
