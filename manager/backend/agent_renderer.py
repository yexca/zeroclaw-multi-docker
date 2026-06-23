"""Resolve manager agent config into runtime env, workspace files, and previews."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

try:
    from config_store import ConfigError, item_id
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from .config_store import ConfigError, item_id


PROMPT_TEMPLATE_FILES = {"AGENTS.md", "IDENTITY.md", "SOUL.md", "MEMORY.md", "TOOLS.md", "USER.md", "HEARTBEAT.md"}
DEFAULT_ZEROCLAW_IMAGE = "ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian"
REQUIRED_ENV_KEYS = [
    "BOT_NAME",
    "MODEL_PROVIDER_FAMILY",
    "MODEL_PROVIDER_ALIAS",
    "MODEL_PROVIDER_MODEL",
    "MODEL_PROVIDER_BASE_URL",
    "MODEL_PROVIDER_API_KEY",
    "MODEL_PROVIDER_WIRE_API",
    "MODEL_PROVIDER_TIMEOUT_SECS",
    "MODEL_PROVIDER_KIND",
    "MATRIX_HOMESERVER",
    "MATRIX_HOST_IP",
    "MATRIX_USER_ID",
    "MATRIX_DEVICE_ID",
    "MATRIX_RECOVERY_KEY",
    "MATRIX_EXTERNAL_PEERS",
    "ZEROCLAW_channels__matrix__home__access_token",
    "ZEROCLAW_channels__matrix__home__password",
    "MCP_ENABLED",
    "MCP_SERVER_NAME",
    "MCP_TRANSPORT",
    "MCP_URL",
    "MCP_DEFERRED_LOADING",
    "MCP_TOOL_TIMEOUT_SECS",
    "MCP_GATEWAY_TOKEN",
]


class AgentRenderer:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def resolve_agent(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        agent_identifier = item_id(agent)
        if not agent_identifier:
            raise ConfigError("invalid_agent", "Agent requires an id or name.")
        resolved = copy.deepcopy(agent)
        resolved.setdefault("id", agent_identifier)
        resolved.setdefault("name", str(agent.get("name") or agent_identifier))

        llm = self._resolve_profile(config, "llm", agent.get("llm_profile"))
        matrix = self._resolve_profile(config, "matrix", agent.get("matrix_profile"))
        mcp = self._resolve_profile(config, "mcp", agent.get("mcp_profile"))

        defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
        matrix_defaults = defaults.get("matrix") if isinstance(defaults.get("matrix"), dict) else {}
        resolved["model"] = deep_merge(llm, agent.get("model") if isinstance(agent.get("model"), dict) else {})
        resolved["matrix"] = deep_merge(deep_merge(matrix_defaults, matrix), agent.get("matrix") if isinstance(agent.get("matrix"), dict) else {})
        resolved["mcp"] = deep_merge(mcp, agent.get("mcp") if isinstance(agent.get("mcp"), dict) else {})
        if "prompt_template" not in resolved and agent.get("template"):
            resolved["prompt_template"] = agent["template"]
        return resolved

    def render_env(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, str]:
        resolved = self.resolve_agent(config, agent)
        docker_config = config.get("docker") if isinstance(config.get("docker"), dict) else {}
        vision = config.get("vision") if isinstance(config.get("vision"), dict) else {}
        runtime = config.get("runtime") if isinstance(config.get("runtime"), dict) else {}
        heartbeat = config.get("heartbeat") if isinstance(config.get("heartbeat"), dict) else {}
        pacing = config.get("pacing") if isinstance(config.get("pacing"), dict) else {}
        model = resolved.get("model") if isinstance(resolved.get("model"), dict) else {}
        matrix = resolved.get("matrix") if isinstance(resolved.get("matrix"), dict) else {}
        mcp = resolved.get("mcp") if isinstance(resolved.get("mcp"), dict) else {}
        agent_name = str(resolved.get("name") or resolved.get("id"))

        env: dict[str, str] = {
            "LANG": "C.UTF-8",
            "BOT_NAME": agent_name,
            "ZEROCLAW_CONFIG_DIR": "/zeroclaw-data/.zeroclaw",
            "ZEROCLAW_DATA_DIR": "",
            "ZEROCLAW_AGENT_WORKSPACE": "/zeroclaw-data/workspace",
            "MODEL_PROVIDER_FAMILY": env_value(model.get("provider_family") or model.get("family") or "deepseek"),
            "MODEL_PROVIDER_ALIAS": env_value(model.get("provider_alias") or model.get("alias") or "text"),
            "MODEL_PROVIDER_MODEL": env_value(model.get("model") or "deepseek-chat"),
            "MODEL_PROVIDER_BASE_URL": env_value(model.get("base_url") or ""),
            "MODEL_PROVIDER_API_KEY": env_value(model.get("api_key") or ""),
            "MODEL_PROVIDER_WIRE_API": env_value(model.get("wire_api") or ""),
            "MODEL_PROVIDER_TIMEOUT_SECS": env_value(model.get("timeout_secs") or 120),
            "MODEL_PROVIDER_KIND": env_value(model.get("kind") or ""),
            "MATRIX_HOMESERVER": env_value(matrix.get("homeserver") or ""),
            "MATRIX_HOST_IP": env_value(matrix.get("host_ip") or docker_config.get("matrix_host_ip") or "127.0.0.1"),
            "MATRIX_USER_ID": env_value(matrix.get("user_id") or resolved.get("matrix_user_id") or ""),
            "MATRIX_DEVICE_ID": env_value(matrix.get("device_id") or resolved.get("matrix_device_id") or ""),
            "MATRIX_RECOVERY_KEY": env_value(matrix.get("recovery_key") or ""),
            "MATRIX_RECOVER_KEY": env_value(matrix.get("recover_key") or matrix.get("recovery_key") or ""),
            "MATRIX_EXTERNAL_PEERS": join_value(matrix.get("external_peers")),
            "MATRIX_PEERS": join_value(matrix.get("peers") or matrix.get("external_peers")),
            "MATRIX_ALLOWED_ROOMS": join_value(matrix.get("allowed_rooms")),
            "MATRIX_MENTION_ONLY": env_value(matrix.get("mention_only", False)),
            "MATRIX_INTERRUPT_ON_NEW_MESSAGE": env_value(matrix.get("interrupt_on_new_message", True)),
            "MATRIX_REPLY_IN_THREAD": env_value(matrix.get("reply_in_thread", True)),
            "MATRIX_ACK_REACTIONS": env_value(matrix.get("ack_reactions", True)),
            "MATRIX_STREAM_MODE": env_value(matrix.get("stream_mode") or "off"),
            "MATRIX_MULTI_MESSAGE": env_value(matrix.get("multi_message", False)),
            "MATRIX_MULTI_MESSAGE_DELAY_MS": env_value(matrix.get("multi_message_delay_ms") or 800),
            "CHANNEL_DEBOUNCE_MS": env_value(matrix.get("channel_debounce_ms") or 3000),
            "ZEROCLAW_channels__matrix__home__access_token": env_value(matrix.get("access_token") or ""),
            "ZEROCLAW_channels__matrix__home__password": env_value(matrix.get("password") or ""),
            "MCP_ENABLED": env_value(mcp.get("enabled", False)),
            "MCP_SERVER_NAME": env_value(mcp.get("server_name") or "home"),
            "MCP_TRANSPORT": env_value(mcp.get("transport") or "sse"),
            "MCP_URL": env_value(mcp.get("url") or ""),
            "MCP_DEFERRED_LOADING": env_value(mcp.get("deferred_loading", True)),
            "MCP_TOOL_TIMEOUT_SECS": env_value(mcp.get("tool_timeout_secs") or 120),
            "MCP_GATEWAY_TOKEN": env_value(mcp.get("gateway_token") or ""),
            "VISION_MODEL": env_value(vision.get("model") or "gpt-4o"),
            "VISION_BASE_URL": env_value(vision.get("base_url") or "https://api.openai.com/v1"),
            "VISION_WIRE_API": env_value(vision.get("wire_api") or "chat_completions"),
            "VISION_ALLOW_REMOTE_FETCH": env_value(vision.get("allow_remote_fetch", False)),
            "VISION_MAX_IMAGES": env_value(vision.get("max_images") or 4),
            "VISION_MAX_IMAGE_SIZE_MB": env_value(vision.get("max_image_size_mb") or 5),
            "VISION_MAX_IMAGE_TURNS": env_value(vision.get("max_image_turns") or 2),
            "ZEROCLAW_providers__models__custom__vision__api_key": env_value(vision.get("api_key") or ""),
            "OPENAI_API_KEY": env_value(vision.get("api_key") or ""),
            "OPENAI_BASE_URL": env_value(vision.get("base_url") or "https://api.openai.com/v1"),
            "HEARTBEAT_ENABLED": env_value(heartbeat.get("enabled", False)),
            "HEARTBEAT_INTERVAL_MINUTES": env_value(heartbeat.get("interval_minutes") or 30),
            "HEARTBEAT_TWO_PHASE": env_value(heartbeat.get("two_phase", True)),
            "HEARTBEAT_MESSAGE": env_value(heartbeat.get("message") or ""),
            "HEARTBEAT_ADAPTIVE": env_value(heartbeat.get("adaptive", False)),
            "HEARTBEAT_MIN_INTERVAL_MINUTES": env_value(heartbeat.get("min_interval_minutes") or 5),
            "HEARTBEAT_MAX_INTERVAL_MINUTES": env_value(heartbeat.get("max_interval_minutes") or 120),
            "HEARTBEAT_DEADMAN_TIMEOUT_MINUTES": env_value(heartbeat.get("deadman_timeout_minutes") or 0),
            "HEARTBEAT_MAX_RUN_HISTORY": env_value(heartbeat.get("max_run_history") or 100),
            "HEARTBEAT_LOAD_SESSION_CONTEXT": env_value(heartbeat.get("load_session_context", False)),
            "HEARTBEAT_TASK_TIMEOUT_SECS": env_value(heartbeat.get("task_timeout_secs") or 600),
            "PACING_LOOP_IGNORE_TOOLS": join_value(pacing.get("loop_ignore_tools") or ["home__job_status"]),
            "PACING_LOOP_DETECTION_ENABLED": env_value(pacing.get("loop_detection_enabled", True)),
            "PACING_LOOP_DETECTION_WINDOW_SIZE": env_value(pacing.get("loop_detection_window_size") or 20),
            "PACING_LOOP_DETECTION_MAX_REPEATS": env_value(pacing.get("loop_detection_max_repeats") or 3),
            "SHELL_TIMEOUT_SECS": env_value(runtime.get("shell_timeout_secs") or 300),
            "SHELL_TOOL_TIMEOUT_SECS": env_value(runtime.get("shell_tool_timeout_secs") or runtime.get("shell_timeout_secs") or 300),
        }

        overrides = resolved.get("environment")
        if isinstance(overrides, dict):
            for key, value in overrides.items():
                if value is not None:
                    env[str(key)] = env_value(value)
        return env

    def initialize_workspace(self, config: dict[str, Any], agent: dict[str, Any], mode: str = "keep") -> dict[str, Any]:
        if mode not in {"keep", "missing", "overwrite", "merge"}:
            raise ConfigError("invalid_mode", "Workspace mode must be keep, missing, overwrite, or merge.", {"mode": mode})
        resolved = self.resolve_agent(config, agent)
        template = self.get_prompt_template(config, resolved.get("prompt_template"))
        files = normalize_template_files(template.get("files") if template else {})
        workspace_dir = self.workspace_dir(config, resolved)
        workspace_dir.mkdir(parents=True, exist_ok=True)

        written: list[str] = []
        skipped: list[str] = []
        merged: list[str] = []
        conflicts: list[str] = []
        for filename, content in files.items():
            if filename not in PROMPT_TEMPLATE_FILES:
                skipped.append(filename)
                continue
            target = workspace_dir / filename
            if target.exists():
                existing = target.read_text(encoding="utf-8")
                if mode in {"keep", "missing"}:
                    skipped.append(filename)
                    continue
                if mode == "merge":
                    if existing == content:
                        skipped.append(filename)
                        continue
                    target.write_text(merge_markdown(existing, content), encoding="utf-8")
                    merged.append(filename)
                    continue
                if mode == "overwrite" and existing != content:
                    conflicts.append(filename)
            target.write_text(content, encoding="utf-8")
            written.append(filename)
        return {
            "agent": resolved.get("id"),
            "template": template.get("id") if template else None,
            "mode": mode,
            "workspace": str(workspace_dir),
            "written": written,
            "merged": merged,
            "skipped": skipped,
            "conflicts": conflicts,
        }

    def export_agent(self, config: dict[str, Any], agent: dict[str, Any], formats: list[str] | None = None, include_secrets: bool = True) -> dict[str, Any]:
        resolved = self.resolve_agent(config, agent)
        raw_env = self.render_env(config, resolved)
        env = raw_env if include_secrets else redact_env(raw_env)
        formats = formats or ["env", "compose", "zeroclaw_config_preview"]
        result: dict[str, Any] = {"agent": resolved if include_secrets else redact_config(resolved), "formats": {}}
        if "env" in formats:
            result["formats"]["env"] = env
            result["formats"]["env_file"] = render_env_file(env)
        if "compose" in formats:
            result["formats"]["compose"] = self.render_compose(config, resolved, env)
        if "zeroclaw_config_preview" in formats or "toml" in formats:
            result["formats"]["zeroclaw_config_preview"] = render_config_toml_preview(env)
        return result

    def render_compose(self, config: dict[str, Any], agent: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
        safe_name = safe_name_part(str(agent.get("name") or agent.get("id")))
        image = agent.get("image") or config.get("defaults", {}).get("zeroclaw_image") or DEFAULT_ZEROCLAW_IMAGE
        docker_config = config.get("docker") if isinstance(config.get("docker"), dict) else {}
        network = docker_config.get("runtime_network") or f"{docker_config.get('project_name', 'zeroclaw-matrix-multi')}_default"
        return {
            "services": {
                safe_name: {
                    "image": image,
                    "container_name": f"zeroclaw-matrix-{safe_name}",
                    "user": "0:0",
                    "restart": "unless-stopped",
                    "working_dir": "/zeroclaw-data/workspace",
                    "entrypoint": ["/bin/sh", "/bootstrap/render-config.sh"],
                    "environment": env,
                    "volumes": ["./bootstrap:/bootstrap:ro", f"./instances/{safe_name}:/zeroclaw-data"],
                    "ports": [f"127.0.0.1:{agent.get('host_port')}:42617"],
                    "extra_hosts": ["host.docker.internal:host-gateway", f"matrix-host:{env.get('MATRIX_HOST_IP', '127.0.0.1')}"],
                    "networks": [network],
                }
            }
        }

    def workspace_dir(self, config: dict[str, Any], agent: dict[str, Any]) -> Path:
        paths = config.get("paths") if isinstance(config.get("paths"), dict) else {}
        instances_dir = Path(str(paths.get("instances_dir") or self.project_root / "instances"))
        return instances_dir / safe_name_part(str(agent.get("name") or agent.get("id"))) / "workspace"

    def get_prompt_template(self, config: dict[str, Any], template_id: Any) -> dict[str, Any] | None:
        templates = config.get("prompt_templates") if isinstance(config.get("prompt_templates"), list) else []
        if not template_id and templates:
            return templates[0]
        for template in templates:
            if isinstance(template, dict) and item_id(template) == str(template_id):
                return copy.deepcopy(template)
        if template_id:
            raise ConfigError("not_found", "Prompt template was not found.", {"id": template_id}, 404)
        return None

    def _resolve_profile(self, config: dict[str, Any], kind: str, profile_id: Any) -> dict[str, Any]:
        if not profile_id:
            return {}
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        collection = profiles.get(kind) if isinstance(profiles.get(kind), list) else []
        for profile in collection:
            if isinstance(profile, dict) and item_id(profile) == str(profile_id):
                return copy.deepcopy(profile)
        raise ConfigError("not_found", f"{kind} profile was not found.", {"id": profile_id}, 404)


def normalize_template_files(files: Any) -> dict[str, str]:
    if isinstance(files, dict):
        return {str(key): str(value) for key, value in files.items()}
    if isinstance(files, list):
        result: dict[str, str] = {}
        for item in files:
            if isinstance(item, dict) and item.get("name"):
                result[str(item["name"])] = str(item.get("content") or "")
        return result
    return {}


def render_env_file(env: dict[str, str]) -> str:
    lines = []
    for key in sorted(env):
        value = env[key]
        if value == "" or any(ch.isspace() for ch in value) or "#" in value or '"' in value:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')
        else:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def redact_env(env: dict[str, str]) -> dict[str, str]:
    return {key: ("[REDACTED]" if is_secret_key(key) and value else value) for key, value in env.items()}


def redact_config(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result[key] = "[REDACTED]" if is_secret_key(str(key)) and item else redact_config(item)
        return result
    if isinstance(value, list):
        return [redact_config(item) for item in value]
    return value


def is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(word in lowered for word in ("api_key", "token", "password", "recovery_key", "recover_key", "secret"))


def render_config_toml_preview(env: dict[str, str]) -> str:
    provider_ref = f"{env.get('MODEL_PROVIDER_FAMILY', 'deepseek')}.{env.get('MODEL_PROVIDER_ALIAS', 'text')}"
    return f"""schema_version = 3
workspace_dir = "{toml_escape(env.get('ZEROCLAW_AGENT_WORKSPACE', '/zeroclaw-data/workspace'))}"
config_path = "{toml_escape(env.get('ZEROCLAW_CONFIG_DIR', '/zeroclaw-data/.zeroclaw'))}/config.toml"
default_model_provider = "{toml_escape(provider_ref)}"
default_model = "{toml_escape(env.get('MODEL_PROVIDER_MODEL', 'deepseek-chat'))}"

[providers.models.{env.get('MODEL_PROVIDER_FAMILY', 'deepseek')}.{env.get('MODEL_PROVIDER_ALIAS', 'text')}]
model = "{toml_escape(env.get('MODEL_PROVIDER_MODEL', 'deepseek-chat'))}"
uri = "{toml_escape(env.get('MODEL_PROVIDER_BASE_URL', ''))}"
wire_api = "{toml_escape(env.get('MODEL_PROVIDER_WIRE_API', ''))}"
kind = "{toml_escape(env.get('MODEL_PROVIDER_KIND', ''))}"
timeout_secs = {env.get('MODEL_PROVIDER_TIMEOUT_SECS', '120')}

[channels.matrix.home]
enabled = true
homeserver = "{toml_escape(env.get('MATRIX_HOMESERVER', ''))}"
user_id = "{toml_escape(env.get('MATRIX_USER_ID', ''))}"
device_id = "{toml_escape(env.get('MATRIX_DEVICE_ID', ''))}"
mention_only = {toml_bool(env.get('MATRIX_MENTION_ONLY', 'false'))}
reply_in_thread = {toml_bool(env.get('MATRIX_REPLY_IN_THREAD', 'true'))}
ack_reactions = {toml_bool(env.get('MATRIX_ACK_REACTIONS', 'true'))}
stream_mode = "{toml_escape(env.get('MATRIX_STREAM_MODE', 'off'))}"
recovery_key = "{toml_escape(env.get('MATRIX_RECOVERY_KEY', ''))}"

[agents.main]
enabled = true
model_provider = "{toml_escape(provider_ref)}"
runtime_profile = "daemon"
channels = ["matrix.home"]

[runtime_profiles.daemon]
shell_timeout_secs = {env.get('SHELL_TIMEOUT_SECS', '300')}

[shell_tool]
timeout_secs = {env.get('SHELL_TOOL_TIMEOUT_SECS', '300')}
"""


def merge_markdown(existing: str, incoming: str) -> str:
    if existing.rstrip() == incoming.rstrip():
        return existing
    return f"{existing.rstrip()}\n\n<!-- ZeroClaw template merge -->\n\n{incoming.rstrip()}\n"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value)
    return str(value)


def join_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value)
    return str(value)


def safe_name_part(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() or ch in "._-" else "-" for ch in value.strip()).strip("-._")
    return safe or "agent"


def toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def toml_bool(value: str) -> str:
    return "true" if str(value).lower() in {"1", "true", "yes", "on"} else "false"


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=False)
