"""Validation and safety checks for manager configuration and agents."""

from __future__ import annotations

import re
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from agent_renderer import DEFAULT_ZEROCLAW_IMAGE, AgentRenderer, safe_name_part
    from config_store import ConfigError, item_id
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from .agent_renderer import DEFAULT_ZEROCLAW_IMAGE, AgentRenderer, safe_name_part
    from .config_store import ConfigError, item_id


LOCAL_API_KEY_OPTIONAL = {"ollama", "local"}
AGENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")


class ConfigValidator:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.renderer = AgentRenderer(project_root)

    def validate_config(self, config: dict[str, Any], check_ports: bool = False) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        agents = config.get("agents") if isinstance(config.get("agents"), list) else []

        self._validate_server(config, errors, warnings)
        self._validate_skill_bundles(config, errors, warnings)
        self._validate_vision_profiles(config, errors, warnings)
        self._validate_gitignore(errors, warnings)
        self._validate_agent_ids(agents, errors)

        used_ports: dict[int, str] = {}
        for agent in agents:
            if isinstance(agent, dict):
                result = self.validate_agent(config, agent, check_ports=check_ports)
                errors.extend(result["errors"])
                warnings.extend(result["warnings"])
                port = agent.get("host_port")
                identifier = str(item_id(agent) or "<unknown>")
                if isinstance(port, int):
                    if port in used_ports:
                        errors.append(issue("duplicate_host_port", "host_port", "Host port is used by more than one agent.", {"port": port, "agents": [used_ports[port], identifier]}))
                    used_ports[port] = identifier
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def validate_agent(self, config: dict[str, Any], agent: dict[str, Any], check_ports: bool = False) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        identifier = str(item_id(agent) or "")
        prefix = f"agents.{identifier}" if identifier else "agents.<unknown>"

        if not identifier or not AGENT_ID_PATTERN.match(identifier):
            errors.append(issue("invalid_agent_id", f"{prefix}.id", "Agent id must start with a letter or number and contain only letters, numbers, dot, underscore, or hyphen.", {"id": identifier}))

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
        matrix_login_mode = str((resolved.get("matrix") or {}).get("login_mode") or "").strip().lower()
        if matrix_login_mode == "token":
            if not string_value(env.get("MATRIX_DEVICE_ID")):
                errors.append(issue("missing_matrix_device_id", f"{prefix}.matrix.device_id", "Matrix device id must be non-empty for token login."))
            if not string_value(env.get("ZEROCLAW_channels__matrix__home__access_token")):
                errors.append(issue("missing_matrix_access_token", f"{prefix}.matrix.access_token", "Matrix access token must be configured for token login."))
        elif matrix_login_mode == "advanced":
            has_account = string_value(env.get("MATRIX_USER_ID")) and string_value(env.get("ZEROCLAW_channels__matrix__home__password"))
            has_token = string_value(env.get("MATRIX_DEVICE_ID")) and string_value(env.get("ZEROCLAW_channels__matrix__home__access_token"))
            if not has_account and not has_token:
                errors.append(issue("missing_matrix_credentials", f"{prefix}.matrix", "Matrix advanced login requires either user id + password or device id + access token."))
        else:
            if not string_value(env.get("MATRIX_USER_ID")):
                errors.append(issue("missing_matrix_user_id", f"{prefix}.matrix.user_id", "Matrix user id must be non-empty for account login."))
            if not string_value(env.get("ZEROCLAW_channels__matrix__home__password")):
                errors.append(issue("missing_matrix_password", f"{prefix}.matrix.password", "Matrix password must be configured for account login."))
        if not string_value(env.get("MATRIX_EXTERNAL_PEERS")):
            errors.append(issue("missing_matrix_external_peers", f"{prefix}.matrix.external_peers", "Matrix external peers must be non-empty."))

        if env.get("MCP_ENABLED", "").lower() == "true" and not string_value(env.get("MCP_URL")):
            errors.append(issue("missing_mcp_url", f"{prefix}.mcp.url", "MCP URL must be non-empty when MCP is enabled."))

        bundle_ids = {str(item_id(bundle) or "") for bundle in config.get("skill_bundles", []) if isinstance(bundle, dict)}
        for index, bundle in enumerate(agent.get("skill_bundles") if isinstance(agent.get("skill_bundles"), list) else []):
            if str(bundle) not in bundle_ids:
                errors.append(issue("unknown_skill_bundle", f"{prefix}.skill_bundles[{index}]", "Skill bundle was not found.", {"bundle": bundle}))

        proactive = resolved.get("proactive") if isinstance(resolved.get("proactive"), dict) else {}
        if bool(proactive.get("enabled")):
            self._validate_proactive(prefix, proactive, env, errors)

        template_id = resolved.get("prompt_template")
        try:
            self.renderer.get_prompt_template(config, template_id)
        except ConfigError as exc:
            errors.append(issue(exc.code, f"{prefix}.prompt_template", exc.message, exc.details))

        workspace = self.renderer.workspace_dir(config, resolved)
        if not is_workspace_writable(workspace):
            errors.append(issue("workspace_not_writable", f"{prefix}.workspace", "Workspace directory is not writable.", {"path": str(workspace)}))

        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def _validate_proactive(self, prefix: str, proactive: dict[str, Any], env: dict[str, str], errors: list[dict[str, Any]]) -> None:
        target = proactive.get("target")
        if not string_value(target) and not string_value(env.get("MATRIX_EXTERNAL_PEERS")):
            errors.append(issue("missing_proactive_target", f"{prefix}.proactive.target", "Proactive target must be set or Matrix external peers must contain at least one target."))
        for key, minimum in {
            "poll_seconds": 30,
            "random_min_minutes": 1,
            "random_max_minutes": 1,
        }.items():
            value = proactive.get(key)
            if value is not None and (not isinstance(value, int) or value < minimum):
                errors.append(issue("invalid_proactive_number", f"{prefix}.proactive.{key}", f"Proactive {key} must be an integer greater than or equal to {minimum}.", {"value": value}))
        min_minutes = proactive.get("random_min_minutes")
        max_minutes = proactive.get("random_max_minutes")
        if isinstance(min_minutes, int) and isinstance(max_minutes, int) and max_minutes < min_minutes:
            errors.append(issue("invalid_proactive_range", f"{prefix}.proactive.random_max_minutes", "Proactive random max minutes must be greater than or equal to random min minutes."))
        quiet_hours = proactive.get("quiet_hours")
        if string_value(quiet_hours) and not re.match(r"^(?:[01]?\d|2[0-3])-(?:[01]?\d|2[0-3])$", str(quiet_hours).strip()):
            errors.append(issue("invalid_proactive_quiet_hours", f"{prefix}.proactive.quiet_hours", "Proactive quiet hours must look like 23-8."))
        agent_url = proactive.get("agent_url")
        if string_value(agent_url) and not is_http_url(str(agent_url)):
            errors.append(issue("invalid_proactive_agent_url", f"{prefix}.proactive.agent_url", "Proactive gateway URL override must be a valid http/https URL."))

    def ensure_valid_for_start(self, config: dict[str, Any], agent: dict[str, Any]) -> None:
        result = self.validate_agent(config, agent, check_ports=False)
        blocking = [entry for entry in result["errors"] if entry["code"] != "host_port_conflict"]
        if blocking:
            raise ConfigError("validation_failed", "Agent configuration is not valid for startup.", {"errors": blocking, "warnings": result["warnings"]}, 422)

    def _validate_agent_ids(self, agents: list[Any], errors: list[dict[str, Any]]) -> None:
        seen_ids: dict[str, str] = {}
        seen_container_names: dict[str, str] = {}
        for agent in agents:
            if not isinstance(agent, dict):
                errors.append(issue("invalid_agent", "agents", "Agent entries must be objects."))
                continue
            identifier = str(item_id(agent) or "")
            safe_name = safe_name_part(identifier)
            if identifier in seen_ids:
                errors.append(issue("duplicate_agent_id", "agents", "Agent id must be unique.", {"id": identifier}))
            if safe_name in seen_container_names:
                errors.append(issue("duplicate_agent_container_name", "agents", "Agent ids must map to unique container/workspace names.", {"id": identifier, "normalized": safe_name, "conflict": seen_container_names[safe_name]}))
            seen_ids[identifier] = identifier
            seen_container_names[safe_name] = identifier

    def _validate_server(self, config: dict[str, Any], errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
        server = config.get("server") if isinstance(config.get("server"), dict) else {}
        bind_host = str(server.get("bind_host") or "127.0.0.1")
        if bind_host not in {"127.0.0.1", "localhost", "::1"}:
            warnings.append(issue("non_loopback_bind", "server.bind_host", "WebUI should bind to loopback for local-only use.", {"bind_host": bind_host}))

    def _validate_skill_bundles(self, config: dict[str, Any], errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
        bundles = config.get("skill_bundles") if isinstance(config.get("skill_bundles"), list) else []
        seen: dict[str, str] = {}
        seen_dirs: dict[str, str] = {}
        shared_root = (self.project_root / "shared").resolve()
        for index, bundle in enumerate(bundles):
            if not isinstance(bundle, dict):
                errors.append(issue("invalid_skill_bundle", f"skill_bundles[{index}]", "Skill bundle entries must be objects."))
                continue
            alias = str(item_id(bundle) or "")
            field = f"skill_bundles[{index}]"
            if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$", alias):
                errors.append(issue("invalid_skill_bundle_id", f"{field}.id", "Skill bundle ID must use letters, numbers, underscore, or hyphen.", {"id": alias}))
            if alias in seen:
                errors.append(issue("duplicate_skill_bundle", field, "Skill bundle IDs must be unique.", {"id": alias, "first": seen[alias]}))
            seen[alias] = field
            directory = str(bundle.get("directory") or f"shared/skills/{alias}").strip()
            path = Path(directory)
            resolved = (path if path.is_absolute() else self.project_root / path).resolve()
            if shared_root != resolved and shared_root not in resolved.parents:
                errors.append(issue("unsafe_skill_bundle_directory", f"{field}.directory", "Skill bundle directory must stay inside the project shared directory.", {"path": str(resolved), "shared": str(shared_root)}))
            normalized = str(resolved).lower()
            if normalized in seen_dirs:
                errors.append(issue("duplicate_skill_bundle_directory", f"{field}.directory", "Skill bundle directories must be unique.", {"path": str(resolved), "first": seen_dirs[normalized]}))
            seen_dirs[normalized] = field
            for list_key in ("include", "exclude"):
                values = bundle.get(list_key)
                if values is not None and not isinstance(values, list):
                    errors.append(issue("invalid_skill_bundle_list", f"{field}.{list_key}", "Skill bundle include/exclude must be lists."))

    def _validate_vision_profiles(self, config: dict[str, Any], errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        visions = profiles.get("vision") if isinstance(profiles.get("vision"), list) else []
        for index, vision in enumerate(visions):
            if isinstance(vision, dict):
                self._validate_vision_profile(vision, f"profiles.vision[{index}]", errors, warnings)

    def _validate_vision_profile(self, vision: dict[str, Any], prefix: str, errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
        provider_family = str(vision.get("provider_family") or vision.get("family") or "custom")
        provider_alias = str(vision.get("provider_alias") or vision.get("alias") or "vision")
        if not re.match(r"^[A-Za-z0-9_-]+$", provider_family):
            errors.append(issue("invalid_vision_provider_family", f"{prefix}.provider_family", "Vision provider family must contain only letters, numbers, underscores, or hyphens."))
        if not re.match(r"^[A-Za-z0-9_-]+$", provider_alias):
            errors.append(issue("invalid_vision_provider_alias", f"{prefix}.provider_alias", "Vision provider alias must contain only letters, numbers, underscores, or hyphens."))
        if not string_value(vision.get("model")):
            errors.append(issue("missing_vision_model", f"{prefix}.model", "Vision model must be non-empty."))
        base_url = str(vision.get("base_url") or "")
        if base_url and not is_http_url(base_url):
            errors.append(issue("invalid_vision_base_url", f"{prefix}.base_url", "Vision base URL must be a valid http/https URL."))
        if not string_value(vision.get("wire_api")):
            errors.append(issue("missing_vision_wire_api", f"{prefix}.wire_api", "Vision wire API must be non-empty."))
        for key, minimum, maximum in (
            ("timeout_secs", 1, None),
            ("max_images", 1, 16),
            ("max_image_size_mb", 1, 20),
            ("max_image_turns", 0, None),
        ):
            value = vision.get(key)
            if value is None:
                continue
            if not isinstance(value, int) or value < minimum or (maximum is not None and value > maximum):
                message = f"vision.{key} must be an integer greater than or equal to {minimum}."
                if maximum is not None:
                    message = f"vision.{key} must be an integer from {minimum} to {maximum}."
                errors.append(issue("invalid_vision_number", f"{prefix}.{key}", message, {"value": value}))
        if provider_family.lower() not in LOCAL_API_KEY_OPTIONAL and not string_value(vision.get("api_key")):
            warnings.append(issue("missing_vision_api_key", f"{prefix}.api_key", "Vision provider usually requires an API key; configure one before sending image attachments.", {"provider_family": provider_family}))

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


def is_http_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


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
