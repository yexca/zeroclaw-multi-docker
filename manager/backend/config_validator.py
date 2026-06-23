"""Validation and safety checks for manager configuration and agents."""

from __future__ import annotations

import re
import socket
from pathlib import Path
from typing import Any

try:
    from agent_renderer import DEFAULT_ZEROCLAW_IMAGE, AgentRenderer, safe_name_part
    from config_store import ConfigError, item_id
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from .agent_renderer import DEFAULT_ZEROCLAW_IMAGE, AgentRenderer, safe_name_part
    from .config_store import ConfigError, item_id


LOCAL_API_KEY_OPTIONAL = {"ollama", "local"}
AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")


class ConfigValidator:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.renderer = AgentRenderer(project_root)

    def validate_config(self, config: dict[str, Any], check_ports: bool = False) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        agents = config.get("agents") if isinstance(config.get("agents"), list) else []

        self._validate_server(config, errors, warnings)
        self._validate_gitignore(errors, warnings)
        self._validate_agent_names(agents, errors)

        used_ports: dict[int, str] = {}
        for agent in agents:
            if isinstance(agent, dict):
                result = self.validate_agent(config, agent, check_ports=check_ports)
                errors.extend(result["errors"])
                warnings.extend(result["warnings"])
                port = agent.get("host_port")
                identifier = str(item_id(agent) or agent.get("name") or "<unknown>")
                if isinstance(port, int):
                    if port in used_ports:
                        errors.append(issue("duplicate_host_port", "host_port", "Host port is used by more than one agent.", {"port": port, "agents": [used_ports[port], identifier]}))
                    used_ports[port] = identifier
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def validate_agent(self, config: dict[str, Any], agent: dict[str, Any], check_ports: bool = False) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        identifier = str(item_id(agent) or agent.get("name") or "")
        prefix = f"agents.{identifier}" if identifier else "agents.<unknown>"

        name = str(agent.get("name") or identifier)
        if not name or not AGENT_NAME_PATTERN.match(name):
            errors.append(issue("invalid_agent_name", f"{prefix}.name", "Agent name must start with a letter or number and contain only letters, numbers, dot, underscore, or hyphen.", {"name": name}))

        port = agent.get("host_port")
        if not isinstance(port, int) or port < 1 or port > 65535:
            errors.append(issue("invalid_host_port", f"{prefix}.host_port", "Host port must be an integer from 1 to 65535.", {"port": port}))
        elif check_ports and is_port_in_use(port):
            errors.append(issue("host_port_conflict", f"{prefix}.host_port", "Host port is already in use on this host.", {"port": port}))

        try:
            resolved = self.renderer.resolve_agent(config, agent)
            env = self.renderer.render_env(config, resolved)
        except ConfigError as exc:
            errors.append(issue(exc.code, prefix, exc.message, exc.details))
            return {"valid": False, "errors": errors, "warnings": warnings}

        image = resolved.get("image") or config.get("defaults", {}).get("zeroclaw_image") or DEFAULT_ZEROCLAW_IMAGE
        if not string_value(image):
            errors.append(issue("missing_image", f"{prefix}.image", "Agent image must be non-empty."))

        model_config = resolved.get("model") if isinstance(resolved.get("model"), dict) else {}
        provider_family = env.get("MODEL_PROVIDER_FAMILY", "")
        if not string_value(model_config.get("model")):
            errors.append(issue("missing_model", f"{prefix}.model.model", "Model must be non-empty."))
        if provider_family.lower() not in LOCAL_API_KEY_OPTIONAL and not string_value(env.get("MODEL_PROVIDER_API_KEY")):
            warnings.append(issue("missing_model_api_key", f"{prefix}.model.api_key", "Provider usually requires an API key; configure one before startup if this provider is remote.", {"provider_family": provider_family}))

        if not string_value(env.get("MATRIX_HOMESERVER")):
            errors.append(issue("missing_matrix_homeserver", f"{prefix}.matrix.homeserver", "Matrix homeserver must be non-empty."))
        if not string_value(env.get("MATRIX_USER_ID")):
            errors.append(issue("missing_matrix_user_id", f"{prefix}.matrix.user_id", "Matrix user id must be non-empty."))
        if not string_value(env.get("ZEROCLAW_channels__matrix__home__access_token")) and not string_value(env.get("ZEROCLAW_channels__matrix__home__password")):
            errors.append(issue("missing_matrix_credentials", f"{prefix}.matrix", "Matrix access token or password must be configured."))
        if not string_value(env.get("MATRIX_EXTERNAL_PEERS")) and not bool(agent.get("allow_empty_external_peers")):
            errors.append(issue("missing_matrix_external_peers", f"{prefix}.matrix.external_peers", "Matrix external peers must be non-empty unless allow_empty_external_peers is true."))

        if env.get("MCP_ENABLED", "").lower() == "true" and not string_value(env.get("MCP_URL")):
            errors.append(issue("missing_mcp_url", f"{prefix}.mcp.url", "MCP URL must be non-empty when MCP is enabled."))

        template_id = resolved.get("prompt_template")
        try:
            self.renderer.get_prompt_template(config, template_id)
        except ConfigError as exc:
            errors.append(issue(exc.code, f"{prefix}.prompt_template", exc.message, exc.details))

        workspace = self.renderer.workspace_dir(config, resolved)
        if not is_workspace_writable(workspace):
            errors.append(issue("workspace_not_writable", f"{prefix}.workspace", "Workspace directory is not writable.", {"path": str(workspace)}))

        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def ensure_valid_for_start(self, config: dict[str, Any], agent: dict[str, Any]) -> None:
        result = self.validate_agent(config, agent, check_ports=False)
        blocking = [entry for entry in result["errors"] if entry["code"] != "host_port_conflict"]
        if blocking:
            raise ConfigError("validation_failed", "Agent configuration is not valid for startup.", {"errors": blocking, "warnings": result["warnings"]}, 422)

    def _validate_agent_names(self, agents: list[Any], errors: list[dict[str, Any]]) -> None:
        seen_ids: dict[str, str] = {}
        seen_names: dict[str, str] = {}
        for agent in agents:
            if not isinstance(agent, dict):
                errors.append(issue("invalid_agent", "agents", "Agent entries must be objects."))
                continue
            identifier = str(item_id(agent) or "")
            name = str(agent.get("name") or identifier)
            safe_name = safe_name_part(name)
            if identifier in seen_ids:
                errors.append(issue("duplicate_agent_id", "agents", "Agent id/name must be unique.", {"id": identifier, "agents": [seen_ids[identifier], name]}))
            if safe_name in seen_names:
                errors.append(issue("duplicate_agent_name", "agents", "Agent names must map to unique container/workspace names.", {"name": name, "normalized": safe_name, "conflict": seen_names[safe_name]}))
            seen_ids[identifier] = name
            seen_names[safe_name] = name

    def _validate_server(self, config: dict[str, Any], errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
        server = config.get("server") if isinstance(config.get("server"), dict) else {}
        bind_host = str(server.get("bind_host") or "127.0.0.1")
        if bind_host not in {"127.0.0.1", "localhost", "::1"}:
            warnings.append(issue("non_loopback_bind", "server.bind_host", "WebUI should bind to loopback for local-only use.", {"bind_host": bind_host}))

    def _validate_gitignore(self, errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
        gitignore = self.project_root / ".gitignore"
        if not gitignore.exists():
            warnings.append(issue("missing_gitignore", ".gitignore", "Could not verify local secrets ignore rules."))
            return
        content = gitignore.read_text(encoding="utf-8")
        for pattern in ("config/secrets.yaml", "config/manager.yaml", "config/generated/*"):
            if pattern not in content:
                warnings.append(issue("missing_ignore_rule", ".gitignore", "Local sensitive/runtime files should be ignored.", {"pattern": pattern}))


def issue(code: str, field: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "field": field, "message": message, "details": details or {}}


def string_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def is_workspace_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".zeroclaw-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False
