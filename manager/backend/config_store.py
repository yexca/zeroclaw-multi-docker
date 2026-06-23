"""Configuration persistence and collection helpers for the manager API."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml


PROFILE_COLLECTIONS = {
    "llm": ("profiles", "llm"),
    "matrix": ("profiles", "matrix"),
    "mcp": ("profiles", "mcp"),
}

PROMPT_TEMPLATE_KEY = "prompt_templates"


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
        },
        "paths": {
            "secrets_file": "/app/config/secrets.yaml",
            "generated_dir": "/app/config/generated",
            "instances_dir": "/app/instances",
        },
        "profiles": {
            "llm": [],
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
    for key in ("id", "alias", "name", "server_name"):
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
        return self.save(payload)

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
        return self.create_item("agents", payload)

    def update_agent(self, identifier: str, payload: Any) -> dict[str, Any]:
        return self.update_item("agents", identifier, payload)

    def delete_agent(self, identifier: str) -> dict[str, Any]:
        return self.delete_item("agents", identifier)

    def validate_agent(self, identifier: str) -> dict[str, Any]:
        config = self.load()
        agent = self.get_agent(identifier)
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        if not item_id(agent):
            errors.append({"field": "id", "message": "Agent requires an id or name."})
        for field in ("host_port",):
            if field in agent and not isinstance(agent[field], int):
                errors.append({"field": field, "message": "Value must be an integer."})

        references = {
            "llm_profile": ("llm", agent.get("llm_profile")),
            "matrix_profile": ("matrix", agent.get("matrix_profile")),
            "mcp_profile": ("mcp", agent.get("mcp_profile")),
            "prompt_template": ("prompt_templates", agent.get("prompt_template")),
        }
        for field, (kind, value) in references.items():
            if value and self._find_index(self._get_collection(config, kind), str(value)) is None:
                errors.append({"field": field, "message": f"Referenced {kind} item does not exist."})

        if not agent.get("enabled", True):
            warnings.append({"field": "enabled", "message": "Agent is disabled and will not be started by default."})

        return {"valid": not errors, "errors": errors, "warnings": warnings, "agent": agent}

    def export(self, payload: Any | None = None) -> dict[str, Any]:
        config = self.load()
        export_name = "resolved.yaml"
        if isinstance(payload, dict) and isinstance(payload.get("filename"), str) and payload["filename"].strip():
            export_name = Path(payload["filename"]).name
        target = self.generated_dir / export_name
        self._atomic_write_yaml(target, config)
        return {"path": str(target), "config": config}

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        config = deep_merge(default_config(), raw)
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        config["profiles"] = {
            "llm": normalize_collection(profiles.get("llm")),
            "matrix": normalize_collection(profiles.get("matrix")),
            "mcp": normalize_collection(profiles.get("mcp")),
        }
        config[PROMPT_TEMPLATE_KEY] = normalize_collection(config.get(PROMPT_TEMPLATE_KEY))
        config["agents"] = normalize_collection(config.get("agents"))
        return config

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
