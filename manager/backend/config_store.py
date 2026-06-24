"""Configuration persistence and collection helpers for the manager API."""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml


PROFILE_COLLECTIONS = {
    "llm": ("profiles", "llm"),
    "vision": ("profiles", "vision"),
    "matrix": ("profiles", "matrix"),
    "mcp": ("profiles", "mcp"),
}

PROMPT_TEMPLATE_KEY = "prompt_templates"
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
            "project_name": "zeroclaw-matrix-multi",
            "control_network": "zeroclaw-matrix-multi_manager-control",
            "storage_driver": "volume",
            "volume_prefix": "zeroclaw-matrix-multi",
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


class ConfigStore:
    def __init__(self, config_path: Path, example_path: Path, generated_dir: Path):
        self.config_path = config_path
        self.example_path = example_path
        self.generated_dir = generated_dir
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
        return self._normalize(raw)

    def save(self, config: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize(config)
        self._atomic_write_yaml(self.config_path, normalized)
        return normalized

    def update_full_config(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ConfigError("invalid_payload", "Configuration payload must be an object.")
        normalized = self._normalize(payload)
        validation = self.validator.validate_config(normalized, check_ports=False)
        if validation["errors"]:
            raise ConfigError("validation_failed", "Configuration has validation errors.", validation, 422)
        return self.save(normalized)

    def list_collection(self, kind: str) -> list[dict[str, Any]]:
        config = self.load()
        return copy.deepcopy(self._get_collection(config, kind))

    def create_item(self, kind: str, payload: Any) -> dict[str, Any]:
        item = self._validate_item_payload(payload)
        identifier = item_id(item)
        if not identifier:
            raise ConfigError("missing_id", "Item must include one of id, alias, name, or server_name.")
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

    def apply_prompt_template(self, identifier: str, payload: Any | None = None) -> dict[str, Any]:
        mode = "keep"
        if isinstance(payload, dict) and isinstance(payload.get("mode"), str):
            mode = payload["mode"]
        config = self.load()
        agent = self.get_agent(identifier)
        return self.renderer.initialize_workspace(config, agent, mode=mode)

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
        config[PROMPT_TEMPLATE_KEY] = normalize_collection(config.get(PROMPT_TEMPLATE_KEY))
        config[PROMPT_TEMPLATE_KEY] = self._normalize_prompt_templates(config[PROMPT_TEMPLATE_KEY])
        config["agents"] = normalize_collection(config.get("agents"))
        return config

    def _normalize_prompt_templates(self, templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        defaults = self._default_prompt_template_files()
        if not templates:
            return [{"id": "default", "name": "Default workspace", "files": defaults}]
        for template in templates:
            files = template.get("files")
            if not isinstance(files, dict):
                files = {}
            normalized_files = {str(key): str(value) for key, value in files.items()}
            for filename, content in defaults.items():
                if not normalized_files.get(filename):
                    normalized_files[filename] = content
            template["files"] = normalized_files
        return templates

    def _default_prompt_template_files(self) -> dict[str, str]:
        template_dirs = [Path(__file__).resolve().parent / "prompt_templates"]
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
