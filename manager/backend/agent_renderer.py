"""Resolve manager agent config into runtime env, workspace files, and previews."""

from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

try:
    from config_store import ConfigError, item_id
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from .config_store import ConfigError, item_id


PROMPT_TEMPLATE_FILES = {"AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md", "USER.md", "HEARTBEAT.md", "BOOTSTRAP.md", "MEMORY.md"}
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
    "MODEL_PROVIDER_TEMPERATURE",
    "MODEL_PROVIDER_MAX_TOKENS",
    "MODEL_PROVIDER_REQUIRES_OPENAI_AUTH",
    "MODEL_PROVIDER_FALLBACK",
    "MODEL_PROVIDER_FALLBACK_MODELS",
    "MODEL_PROVIDER_EXTRA_HEADERS",
    "MODEL_PROVIDER_MERGE_SYSTEM_INTO_USER",
    "MODEL_PROVIDER_PROVIDER_EXTRA",
    "MODEL_PROVIDER_PRICING",
    "MODEL_PROVIDER_NATIVE_TOOLS",
    "MODEL_PROVIDER_THINK",
    "MODEL_PROVIDER_CHAT_TEMPLATE_KWARGS",
    "MODEL_PROVIDER_TLS_CA_CERT_PATH",
    "MODEL_PROVIDER_AUTH_MODE",
    "MODEL_PROVIDER_OAUTH_CLIENT_ID",
    "MODEL_PROVIDER_OAUTH_CLIENT_SECRET",
    "MODEL_PROVIDER_OAUTH_PROJECT",
    "MODEL_PROVIDER_NUM_CTX",
    "MODEL_PROVIDER_NUM_PREDICT",
    "MODEL_PROVIDER_TEMPERATURE_OVERRIDE",
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
    "VISION_ENABLED",
    "VISION_PROVIDER_FAMILY",
    "VISION_PROVIDER_ALIAS",
    "VISION_MODEL",
    "VISION_BASE_URL",
    "VISION_WIRE_API",
    "VISION_TIMEOUT_SECS",
    "VISION_ALLOW_REMOTE_FETCH",
    "VISION_MAX_IMAGES",
    "VISION_MAX_IMAGE_SIZE_MB",
    "VISION_MAX_IMAGE_TURNS",
    "ZEROCLAW_providers__models__custom__vision__api_key",
    "SKILLS_ALLOW_SCRIPTS",
    "SKILLS_OPEN_SKILLS_ENABLED",
    "SKILLS_REGISTRY_URL",
    "SKILLS_PROMPT_INJECTION_MODE",
    "SKILLS_EXTRA_REGISTRIES",
    "SKILL_CREATION_ENABLED",
    "SKILL_CREATION_MAX_SKILLS",
    "SKILL_CREATION_SIMILARITY_THRESHOLD",
    "SKILL_INSTALL_SUGGESTIONS_ENABLED",
    "SKILL_IMPROVEMENT_ENABLED",
    "SKILL_IMPROVEMENT_COOLDOWN_SECS",
    "SKILL_IMPROVEMENT_NUDGE_INTERVAL_ITERATIONS",
    "SKILL_IMPROVEMENT_MAX_REVIEW_ITERATIONS",
    "AGENT_SKILL_BUNDLES",
    "SKILL_BUNDLES_JSON",
    "SKILL_BUNDLES_TOML",
]


class AgentRenderer:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def resolve_agent(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        agent_identifier = item_id(agent)
        if not agent_identifier:
            raise ConfigError("invalid_agent", "Agent requires an id.")
        resolved = copy.deepcopy(agent)
        resolved.setdefault("id", agent_identifier)
        resolved.setdefault("name", str(agent.get("name") or agent_identifier))

        llm = self._resolve_profile(config, "llm", agent.get("llm_profile"))
        vision = self._resolve_profile(config, "vision", agent.get("vision_profile"), optional=True)
        matrix = self._resolve_profile(config, "matrix", agent.get("matrix_profile"))
        mcp = self._resolve_profile(config, "mcp", agent.get("mcp_profile"))

        defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
        matrix_defaults = defaults.get("matrix") if isinstance(defaults.get("matrix"), dict) else {}
        resolved["model"] = deep_merge(llm, agent.get("model") if isinstance(agent.get("model"), dict) else {})
        resolved["vision"] = deep_merge(vision, agent.get("vision") if isinstance(agent.get("vision"), dict) else {})
        resolved["matrix"] = deep_merge(deep_merge(matrix_defaults, matrix), agent.get("matrix") if isinstance(agent.get("matrix"), dict) else {})
        resolved["mcp"] = deep_merge(mcp, agent.get("mcp") if isinstance(agent.get("mcp"), dict) else {})
        return resolved

    def render_env(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, str]:
        resolved = self.resolve_agent(config, agent)
        docker_config = config.get("docker") if isinstance(config.get("docker"), dict) else {}
        runtime = config.get("runtime") if isinstance(config.get("runtime"), dict) else {}
        skills = config.get("skills") if isinstance(config.get("skills"), dict) else {}
        heartbeat = config.get("heartbeat") if isinstance(config.get("heartbeat"), dict) else {}
        pacing = config.get("pacing") if isinstance(config.get("pacing"), dict) else {}
        model = resolved.get("model") if isinstance(resolved.get("model"), dict) else {}
        vision = resolved.get("vision") if isinstance(resolved.get("vision"), dict) else {}
        matrix = resolved.get("matrix") if isinstance(resolved.get("matrix"), dict) else {}
        mcp = resolved.get("mcp") if isinstance(resolved.get("mcp"), dict) else {}
        agent_name = str(resolved.get("name") or resolved.get("id"))
        vision_family = vision.get("provider_family") or vision.get("family") or "custom"
        vision_alias = vision.get("provider_alias") or vision.get("alias") or "vision"
        vision_api_key = vision.get("api_key") or ""

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
            "MODEL_PROVIDER_TEMPERATURE": env_value(model.get("temperature") if model.get("temperature") is not None else ""),
            "MODEL_PROVIDER_MAX_TOKENS": env_value(model.get("max_tokens") if model.get("max_tokens") is not None else ""),
            "MODEL_PROVIDER_REQUIRES_OPENAI_AUTH": env_value(model.get("requires_openai_auth", False)),
            "MODEL_PROVIDER_FALLBACK": toml_inline_env(model.get("fallback") or []),
            "MODEL_PROVIDER_FALLBACK_MODELS": toml_inline_env(model.get("fallback_models") or []),
            "MODEL_PROVIDER_EXTRA_HEADERS": toml_inline_env(model.get("extra_headers") or {}),
            "MODEL_PROVIDER_MERGE_SYSTEM_INTO_USER": env_value(model.get("merge_system_into_user", False)),
            "MODEL_PROVIDER_PROVIDER_EXTRA": toml_inline_env(model.get("provider_extra")),
            "MODEL_PROVIDER_PRICING": toml_inline_env(model.get("pricing") or {}),
            "MODEL_PROVIDER_NATIVE_TOOLS": env_value(model.get("native_tools") if model.get("native_tools") is not None else ""),
            "MODEL_PROVIDER_THINK": env_value(model.get("think") if model.get("think") is not None else ""),
            "MODEL_PROVIDER_CHAT_TEMPLATE_KWARGS": toml_inline_env(model.get("chat_template_kwargs")),
            "MODEL_PROVIDER_TLS_CA_CERT_PATH": env_value(model.get("tls_ca_cert_path") or ""),
            "MODEL_PROVIDER_AUTH_MODE": env_value(model.get("auth_mode") or ""),
            "MODEL_PROVIDER_OAUTH_CLIENT_ID": env_value(model.get("oauth_client_id") or ""),
            "MODEL_PROVIDER_OAUTH_CLIENT_SECRET": env_value(model.get("oauth_client_secret") or ""),
            "MODEL_PROVIDER_OAUTH_PROJECT": env_value(model.get("oauth_project") or ""),
            "MODEL_PROVIDER_NUM_CTX": env_value(model.get("num_ctx") if model.get("num_ctx") is not None else ""),
            "MODEL_PROVIDER_NUM_PREDICT": env_value(model.get("num_predict") if model.get("num_predict") is not None else ""),
            "MODEL_PROVIDER_TEMPERATURE_OVERRIDE": env_value(model.get("temperature_override") if model.get("temperature_override") is not None else ""),
            "MATRIX_HOMESERVER": env_value(matrix.get("homeserver") or ""),
            "MATRIX_HOST_IP": env_value(matrix.get("host_ip") or docker_config.get("matrix_host_ip") or "127.0.0.1"),
            "MATRIX_USER_ID": env_value(matrix.get("user_id") or resolved.get("matrix_user_id") or ""),
            "MATRIX_DEVICE_ID": env_value(matrix.get("device_id") or resolved.get("matrix_device_id") or ""),
            "MATRIX_RECOVERY_KEY": env_value(matrix.get("recovery_key") or ""),
            "MATRIX_EXTERNAL_PEERS": join_value(matrix.get("external_peers")),
            "MATRIX_ALLOWED_ROOMS": join_value(matrix.get("allowed_rooms")),
            "MATRIX_MENTION_ONLY": env_value(matrix.get("mention_only", False)),
            "MATRIX_INTERRUPT_ON_NEW_MESSAGE": env_value(matrix.get("interrupt_on_new_message", True)),
            "MATRIX_REPLY_IN_THREAD": env_value(matrix.get("reply_in_thread", False)),
            "MATRIX_ACK_REACTIONS": env_value(matrix.get("ack_reactions", True)),
            "MATRIX_STREAM_MODE": env_value(matrix.get("stream_mode") or "multi_message"),
            "MATRIX_MULTI_MESSAGE_DELAY_MS": env_value(matrix.get("multi_message_delay_ms") or 800),
            "MATRIX_DRAFT_UPDATE_INTERVAL_MS": env_value(matrix.get("draft_update_interval_ms") or 1500),
            "MATRIX_APPROVAL_TIMEOUT_SECS": env_value(matrix.get("approval_timeout_secs") or 3600),
            "MATRIX_EXCLUDED_TOOLS": join_value(matrix.get("excluded_tools")),
            "MATRIX_REPLY_MIN_INTERVAL_SECS": env_value(matrix.get("reply_min_interval_secs") or 0),
            "MATRIX_REPLY_QUEUE_DEPTH_MAX": env_value(matrix.get("reply_queue_depth_max") or 0),
            "CHANNEL_DEBOUNCE_MS": env_value(matrix.get("channel_debounce_ms") if matrix.get("channel_debounce_ms") is not None else 0),
            "ZEROCLAW_channels__matrix__home__access_token": env_value(matrix.get("access_token") or ""),
            "ZEROCLAW_channels__matrix__home__password": env_value(matrix.get("password") or ""),
            "MCP_ENABLED": env_value(mcp.get("enabled", False)),
            "MCP_SERVER_NAME": env_value(mcp.get("server_name") or "home"),
            "MCP_TRANSPORT": env_value(mcp.get("transport") or "sse"),
            "MCP_URL": env_value(mcp.get("url") or ""),
            "MCP_DEFERRED_LOADING": env_value(mcp.get("deferred_loading", True)),
            "MCP_TOOL_TIMEOUT_SECS": env_value(mcp.get("tool_timeout_secs") or 120),
            "MCP_GATEWAY_TOKEN": env_value(mcp.get("gateway_token") or ""),
            "VISION_ENABLED": env_value(bool(vision)),
            "VISION_PROVIDER_FAMILY": env_value(vision_family),
            "VISION_PROVIDER_ALIAS": env_value(vision_alias),
            "VISION_MODEL": env_value(vision.get("model") or "gpt-4o"),
            "VISION_BASE_URL": env_value(vision.get("base_url") or "https://api.openai.com/v1"),
            "VISION_WIRE_API": env_value(vision.get("wire_api") or "chat_completions"),
            "VISION_TIMEOUT_SECS": env_value(vision.get("timeout_secs") or 120),
            "VISION_ALLOW_REMOTE_FETCH": env_value(vision.get("allow_remote_fetch", False)),
            "VISION_MAX_IMAGES": env_value(vision.get("max_images") or 4),
            "VISION_MAX_IMAGE_SIZE_MB": env_value(vision.get("max_image_size_mb") or 5),
            "VISION_MAX_IMAGE_TURNS": env_value(vision.get("max_image_turns") or 2),
            "ZEROCLAW_providers__models__custom__vision__api_key": env_value(vision_api_key),
            "OPENAI_API_KEY": env_value(vision_api_key),
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
            "SKILLS_ALLOW_SCRIPTS": env_value(skills.get("allow_scripts", False)),
            "SKILLS_OPEN_SKILLS_ENABLED": env_value(skills.get("open_skills_enabled", False)),
            "SKILLS_REGISTRY_URL": env_value(skills.get("registry_url") or "https://github.com/zeroclaw-labs/zeroclaw-skills"),
            "SKILLS_PROMPT_INJECTION_MODE": env_value(skills.get("prompt_injection_mode") or "full"),
            "SKILLS_EXTRA_REGISTRIES": toml_inline_env(skills.get("extra_registries") or []),
            "SKILL_CREATION_ENABLED": env_value((skills.get("skill_creation") or {}).get("enabled", False)),
            "SKILL_CREATION_MAX_SKILLS": env_value((skills.get("skill_creation") or {}).get("max_skills", 500)),
            "SKILL_CREATION_SIMILARITY_THRESHOLD": env_value((skills.get("skill_creation") or {}).get("similarity_threshold", 0.85)),
            "SKILL_INSTALL_SUGGESTIONS_ENABLED": env_value((skills.get("install_suggestions") or {}).get("enabled", False)),
            "SKILL_IMPROVEMENT_ENABLED": env_value((skills.get("skill_improvement") or {}).get("enabled", False)),
            "SKILL_IMPROVEMENT_COOLDOWN_SECS": env_value((skills.get("skill_improvement") or {}).get("cooldown_secs", 3600)),
            "SKILL_IMPROVEMENT_NUDGE_INTERVAL_ITERATIONS": env_value((skills.get("skill_improvement") or {}).get("nudge_interval_iterations", 10)),
            "SKILL_IMPROVEMENT_MAX_REVIEW_ITERATIONS": env_value((skills.get("skill_improvement") or {}).get("max_review_iterations", 8)),
            "AGENT_SKILL_BUNDLES": join_value(resolved.get("skill_bundles")),
            "SKILL_BUNDLES_JSON": json.dumps(render_skill_bundles_env(config, resolved.get("skill_bundles")), sort_keys=True),
            "SKILL_BUNDLES_TOML": render_skill_bundles_toml(config, resolved.get("skill_bundles")),
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
            if not is_safe_workspace_file(filename):
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
        formats = formats or ["env", "zeroclaw_config_preview"]
        result: dict[str, Any] = {"agent": resolved if include_secrets else redact_config(resolved), "formats": {}}
        if "env" in formats:
            result["formats"]["env"] = env
            result["formats"]["env_file"] = render_env_file(env)
        if "zeroclaw_config_preview" in formats or "toml" in formats:
            result["formats"]["zeroclaw_config_preview"] = render_config_toml_preview(env)
        return result

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

    def _resolve_profile(self, config: dict[str, Any], kind: str, profile_id: Any, optional: bool = False) -> dict[str, Any]:
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        collection = profiles.get(kind) if isinstance(profiles.get(kind), list) else []
        if not profile_id:
            return {}
        for profile in collection:
            if isinstance(profile, dict) and item_id(profile) == str(profile_id):
                return copy.deepcopy(profile)
        raise ConfigError("not_found", f"{kind} profile was not found.", {"id": profile_id}, 404)


def normalize_template_files(files: Any) -> dict[str, str]:
    if isinstance(files, dict):
        return {str(key): str(value) for key, value in files.items()}
    return {}


def is_safe_workspace_file(filename: str) -> bool:
    text = str(filename or "").strip()
    if not text or len(text) > 128 or "\\" in text:
        return False
    path = PurePosixPath(text)
    return (
        len(path.parts) == 1
        and path.name == text
        and path.name not in {"", ".", ".."}
        and ".." not in path.parts
        and all(ch.isalnum() or ch in "._-" for ch in text)
        and text[0].isalnum()
    )


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
    vision_provider_ref = f"{env.get('VISION_PROVIDER_FAMILY', 'custom')}.{env.get('VISION_PROVIDER_ALIAS', 'vision')}"
    provider_block = render_provider_toml_lines(env)
    vision_block = render_vision_preview_block(env, vision_provider_ref)
    return f"""schema_version = 3
workspace_dir = "{toml_escape(env.get('ZEROCLAW_AGENT_WORKSPACE', '/zeroclaw-data/workspace'))}"
config_path = "{toml_escape(env.get('ZEROCLAW_CONFIG_DIR', '/zeroclaw-data/.zeroclaw'))}/config.toml"
default_model_provider = "{toml_escape(provider_ref)}"
default_model = "{toml_escape(env.get('MODEL_PROVIDER_MODEL', 'deepseek-chat'))}"

[providers.models.{env.get('MODEL_PROVIDER_FAMILY', 'deepseek')}.{env.get('MODEL_PROVIDER_ALIAS', 'text')}]
{provider_block}
{vision_block}

[channels.matrix.home]
enabled = true
homeserver = "{toml_escape(env.get('MATRIX_HOMESERVER', ''))}"
user_id = "{toml_escape(env.get('MATRIX_USER_ID', ''))}"
device_id = "{toml_escape(env.get('MATRIX_DEVICE_ID', ''))}"
allowed_rooms = {toml_csv_array(env.get('MATRIX_ALLOWED_ROOMS', ''))}
mention_only = {toml_bool(env.get('MATRIX_MENTION_ONLY', 'false'))}
interrupt_on_new_message = {toml_bool(env.get('MATRIX_INTERRUPT_ON_NEW_MESSAGE', 'true'))}
reply_in_thread = {toml_bool(env.get('MATRIX_REPLY_IN_THREAD', 'false'))}
ack_reactions = {toml_bool(env.get('MATRIX_ACK_REACTIONS', 'true'))}
stream_mode = "{toml_escape(env.get('MATRIX_STREAM_MODE', 'multi_message'))}"
multi_message_delay_ms = {env.get('MATRIX_MULTI_MESSAGE_DELAY_MS', '800')}
draft_update_interval_ms = {env.get('MATRIX_DRAFT_UPDATE_INTERVAL_MS', '1500')}
approval_timeout_secs = {env.get('MATRIX_APPROVAL_TIMEOUT_SECS', '3600')}
excluded_tools = {toml_csv_array(env.get('MATRIX_EXCLUDED_TOOLS', ''))}
reply_min_interval_secs = {env.get('MATRIX_REPLY_MIN_INTERVAL_SECS', '0')}
reply_queue_depth_max = {env.get('MATRIX_REPLY_QUEUE_DEPTH_MAX', '0')}
recovery_key = "{toml_escape(env.get('MATRIX_RECOVERY_KEY', ''))}"

[agents.main]
enabled = true
model_provider = "{toml_escape(provider_ref)}"
runtime_profile = "daemon"
channels = ["matrix.home"]
skill_bundles = {toml_csv_array(env.get('AGENT_SKILL_BUNDLES', ''))}

[runtime_profiles.daemon]
shell_timeout_secs = {env.get('SHELL_TIMEOUT_SECS', '300')}

[shell_tool]
timeout_secs = {env.get('SHELL_TOOL_TIMEOUT_SECS', '300')}
{render_skills_preview_block(env)}
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


def toml_inline_env(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return toml_inline(value)


def render_skill_bundles_env(config: dict[str, Any], selected: Any) -> list[dict[str, Any]]:
    selected_aliases = set(join_list(selected))
    bundles = config.get("skill_bundles") if isinstance(config.get("skill_bundles"), list) else []
    result = []
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue
        alias = str(item_id(bundle) or "").strip()
        if not alias or alias not in selected_aliases:
            continue
        result.append(
            {
                "alias": alias,
                "directory": f"/zeroclaw-data/shared/skills/{alias}",
                "include": join_list(bundle.get("include")),
                "exclude": join_list(bundle.get("exclude")),
            }
        )
    return result


def render_skill_bundles_toml(config: dict[str, Any], selected: Any) -> str:
    lines: list[str] = []
    for bundle in render_skill_bundles_env(config, selected):
        alias = str(bundle.get("alias") or "")
        if not alias:
            continue
        lines.extend(
            [
                "",
                f"[skill_bundles.{alias}]",
                f'directory = "{toml_escape(str(bundle.get("directory") or ""))}"',
                f"include = {toml_array_list(bundle.get('include') or [])}",
                f"exclude = {toml_array_list(bundle.get('exclude') or [])}",
            ]
        )
    return "\n".join(lines)


def join_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]
    return []


def render_skills_preview_block(env: dict[str, str]) -> str:
    lines = [
        "",
        "[skills]",
        f"allow_scripts = {toml_bool(env.get('SKILLS_ALLOW_SCRIPTS', 'false'))}",
        f"open_skills_enabled = {toml_bool(env.get('SKILLS_OPEN_SKILLS_ENABLED', 'false'))}",
        f'prompt_injection_mode = "{toml_escape(env.get("SKILLS_PROMPT_INJECTION_MODE", "full"))}"',
    ]
    if env.get("SKILLS_REGISTRY_URL"):
        lines.append(f'registry_url = "{toml_escape(env["SKILLS_REGISTRY_URL"])}"')
    if env.get("SKILLS_EXTRA_REGISTRIES"):
        lines.append(f"extra_registries = {env['SKILLS_EXTRA_REGISTRIES']}")
    lines.extend(
        [
            "",
            "[skills.skill_creation]",
            f"enabled = {toml_bool(env.get('SKILL_CREATION_ENABLED', 'false'))}",
            f"max_skills = {env.get('SKILL_CREATION_MAX_SKILLS', '500')}",
            f"similarity_threshold = {env.get('SKILL_CREATION_SIMILARITY_THRESHOLD', '0.85')}",
            "",
            "[skills.install_suggestions]",
            f"enabled = {toml_bool(env.get('SKILL_INSTALL_SUGGESTIONS_ENABLED', 'false'))}",
            "",
            "[skills.skill_improvement]",
            f"enabled = {toml_bool(env.get('SKILL_IMPROVEMENT_ENABLED', 'false'))}",
            f"cooldown_secs = {env.get('SKILL_IMPROVEMENT_COOLDOWN_SECS', '3600')}",
            f"nudge_interval_iterations = {env.get('SKILL_IMPROVEMENT_NUDGE_INTERVAL_ITERATIONS', '10')}",
            f"max_review_iterations = {env.get('SKILL_IMPROVEMENT_MAX_REVIEW_ITERATIONS', '8')}",
        ]
    )
    try:
        bundles = json.loads(env.get("SKILL_BUNDLES_JSON") or "[]")
    except json.JSONDecodeError:
        bundles = []
    for bundle in bundles if isinstance(bundles, list) else []:
        alias = str(bundle.get("alias") or "")
        if not alias:
            continue
        lines.extend(
            [
                "",
                f"[skill_bundles.{alias}]",
                f'directory = "{toml_escape(str(bundle.get("directory") or ""))}"',
                f"include = {toml_array_list(bundle.get('include') or [])}",
                f"exclude = {toml_array_list(bundle.get('exclude') or [])}",
            ]
        )
    return "\n".join(lines)


def render_provider_toml_lines(env: dict[str, str]) -> str:
    lines = [
        f'model = "{toml_escape(env.get("MODEL_PROVIDER_MODEL", "deepseek-chat"))}"',
    ]
    if env.get("MODEL_PROVIDER_BASE_URL"):
        lines.append(f'uri = "{toml_escape(env.get("MODEL_PROVIDER_BASE_URL", ""))}"')
    if env.get("MODEL_PROVIDER_API_KEY"):
        lines.append(f'api_key = "{toml_escape(env.get("MODEL_PROVIDER_API_KEY", ""))}"')
    if env.get("MODEL_PROVIDER_WIRE_API"):
        lines.append(f'wire_api = "{toml_escape(env.get("MODEL_PROVIDER_WIRE_API", ""))}"')
    if env.get("MODEL_PROVIDER_KIND"):
        lines.append(f'kind = "{toml_escape(env.get("MODEL_PROVIDER_KIND", ""))}"')
    lines.append(f'timeout_secs = {env.get("MODEL_PROVIDER_TIMEOUT_SECS", "120")}')

    string_fields = {
        "tls_ca_cert_path": "MODEL_PROVIDER_TLS_CA_CERT_PATH",
        "auth_mode": "MODEL_PROVIDER_AUTH_MODE",
        "oauth_client_id": "MODEL_PROVIDER_OAUTH_CLIENT_ID",
        "oauth_client_secret": "MODEL_PROVIDER_OAUTH_CLIENT_SECRET",
        "oauth_project": "MODEL_PROVIDER_OAUTH_PROJECT",
    }
    raw_fields = {
        "temperature": "MODEL_PROVIDER_TEMPERATURE",
        "max_tokens": "MODEL_PROVIDER_MAX_TOKENS",
        "fallback": "MODEL_PROVIDER_FALLBACK",
        "fallback_models": "MODEL_PROVIDER_FALLBACK_MODELS",
        "extra_headers": "MODEL_PROVIDER_EXTRA_HEADERS",
        "provider_extra": "MODEL_PROVIDER_PROVIDER_EXTRA",
        "pricing": "MODEL_PROVIDER_PRICING",
        "chat_template_kwargs": "MODEL_PROVIDER_CHAT_TEMPLATE_KWARGS",
        "num_ctx": "MODEL_PROVIDER_NUM_CTX",
        "num_predict": "MODEL_PROVIDER_NUM_PREDICT",
        "temperature_override": "MODEL_PROVIDER_TEMPERATURE_OVERRIDE",
    }
    bool_fields = {
        "requires_openai_auth": "MODEL_PROVIDER_REQUIRES_OPENAI_AUTH",
        "merge_system_into_user": "MODEL_PROVIDER_MERGE_SYSTEM_INTO_USER",
        "native_tools": "MODEL_PROVIDER_NATIVE_TOOLS",
        "think": "MODEL_PROVIDER_THINK",
    }
    for key, env_key in string_fields.items():
        if env.get(env_key):
            lines.append(f'{key} = "{toml_escape(env.get(env_key, ""))}"')
    for key, env_key in raw_fields.items():
        if env.get(env_key):
            lines.append(f"{key} = {env[env_key]}")
    for key, env_key in bool_fields.items():
        value = env.get(env_key, "")
        if value and (key in {"native_tools", "think"} or toml_bool(value) == "true"):
            lines.append(f"{key} = {toml_bool(value)}")
    return "\n".join(lines)


def render_vision_toml_lines(env: dict[str, str]) -> str:
    lines = [
        f'model = "{toml_escape(env.get("VISION_MODEL", "gpt-4o"))}"',
    ]
    if env.get("VISION_BASE_URL"):
        lines.append(f'uri = "{toml_escape(env.get("VISION_BASE_URL", ""))}"')
    if env.get("ZEROCLAW_providers__models__custom__vision__api_key"):
        lines.append(f'api_key = "{toml_escape(env.get("ZEROCLAW_providers__models__custom__vision__api_key", ""))}"')
    if env.get("VISION_WIRE_API"):
        lines.append(f'wire_api = "{toml_escape(env.get("VISION_WIRE_API", ""))}"')
    lines.append(f'timeout_secs = {env.get("VISION_TIMEOUT_SECS", "120")}')
    return "\n".join(lines)


def render_vision_preview_block(env: dict[str, str], vision_provider_ref: str) -> str:
    multimodal_limits = f"""
[multimodal]
max_images = {env.get('VISION_MAX_IMAGES', '4')}
max_image_size_mb = {env.get('VISION_MAX_IMAGE_SIZE_MB', '5')}
max_image_turns = {env.get('VISION_MAX_IMAGE_TURNS', '2')}
allow_remote_fetch = {toml_bool(env.get('VISION_ALLOW_REMOTE_FETCH', 'false'))}"""
    if toml_bool(env.get("VISION_ENABLED", "true")) != "true":
        return multimodal_limits
    return f"""
[providers.models.{env.get('VISION_PROVIDER_FAMILY', 'custom')}.{env.get('VISION_PROVIDER_ALIAS', 'vision')}]
{render_vision_toml_lines(env)}

[[model_routes]]
hint = "vision"
model_provider = "{toml_escape(vision_provider_ref)}"
model = "{toml_escape(env.get('VISION_MODEL', 'gpt-4o'))}"
{multimodal_limits}
vision_model_provider = "{toml_escape(vision_provider_ref)}"
vision_model = "{toml_escape(env.get('VISION_MODEL', 'gpt-4o'))}"""


def toml_inline(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{toml_escape(value)}"'
    if isinstance(value, (list, tuple, set)):
        return "[" + ", ".join(toml_inline(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f'"{toml_escape(str(key))}" = {toml_inline(child)}' for key, child in value.items()) + " }"
    return f'"{toml_escape(str(value))}"'


def join_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value)
    return str(value)


def toml_csv_array(value: str) -> str:
    items = [item.strip() for item in str(value or "").split(",") if item.strip()]
    return toml_array_list(items)


def toml_array_list(items: Any) -> str:
    if not isinstance(items, list):
        items = []
    return "[" + ", ".join(f'"{toml_escape(str(item))}"' for item in items if str(item).strip()) + "]"


def safe_name_part(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() or ch in "._-" else "-" for ch in value.strip()).strip("-._")
    return safe or "agent"


def toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def toml_bool(value: str) -> str:
    return "true" if str(value).lower() in {"1", "true", "yes", "on"} else "false"


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=False)
