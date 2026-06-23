# Manager Configuration Schema

Primary config is YAML. The manager reads `config/manager.yaml` locally, or
`config/manager.example.yaml` if the local file does not exist. Secrets live in
`config/secrets.yaml` and are not committed.

## Top-Level Keys

- `version`: schema version, currently `1`.
- `webui`: default UI language and theme.
- `server`: local WebUI bind host and host port.
- `docker`: Docker API proxy URL, Compose project name, control network,
  runtime network, and Matrix host IP.
- `paths`: container paths plus optional host paths for Docker bind mounts.
- `defaults`: shared image and Matrix defaults.
- `vision`: shared vision model route.
- `heartbeat`: built-in ZeroClaw heartbeat settings.
- `pacing`: loop detection settings.
- `runtime`: shell/tool timeout settings.
- `profiles.llm`: reusable LLM provider profiles.
- `profiles.matrix`: reusable Matrix profiles.
- `profiles.mcp`: reusable MCP profiles.
- `prompt_templates`: reusable workspace prompt files.
- `agents`: per-agent definitions.

## Agent Fields

Common agent fields:

- `id` or `name`: unique identifier.
- `enabled`: UI/runtime intent.
- `host_port`: loopback gateway port.
- `image`: optional image override.
- `llm_profile`, `matrix_profile`, `mcp_profile`: profile references.
- `prompt_template`: workspace template reference.
- `matrix`: per-agent Matrix identity and peer overrides.
- `environment`: explicit environment overrides for advanced use.
- `allow_empty_external_peers`: bypasses peer validation for local testing.

## LLM Profile Fields

`profiles.llm` entries describe reusable ZeroClaw model provider profiles. A
minimal remote profile usually includes:

- `id`: manager-local profile ID.
- `provider_family`: ZeroClaw provider family, for example `openai`,
  `deepseek`, `ollama`, `gemini`, or `custom`.
- `provider_alias`: alias used in the generated
  `[providers.models.<provider_family>.<provider_alias>]` TOML section.
- `model`: provider-local model ID.
- `base_url`: endpoint URL. The manager writes this to ZeroClaw's `uri` field.
- `wire_api`: `chat_completions` or `responses`.
- `timeout_secs`: request timeout in seconds.
- `api_key`: optional provider credential. Local providers and external auth
  flows may not need it.

Advanced fields supported by the manager include:

- Shared ZeroClaw provider fields: `kind`, `temperature`, `max_tokens`,
  `requires_openai_auth`, `fallback`, `fallback_models`, `extra_headers`,
  `merge_system_into_user`, `provider_extra`, `pricing`, `native_tools`,
  `think`, `chat_template_kwargs`, and `tls_ca_cert_path`.
- Gemini-specific fields: `auth_mode`, `oauth_client_id`,
  `oauth_client_secret`, and `oauth_project`.
- Ollama-specific fields: `num_ctx`, `num_predict`, and
  `temperature_override`.

The WebUI validates required strings, HTTP/HTTPS URLs, numeric fields, numeric
ranges, and JSON text fields before saving. JSON fields are stored as structured
YAML and rendered as TOML inline values for agent containers.

## Matrix Profile Fields

`profiles.matrix` entries describe reusable ZeroClaw Matrix channel settings.
They are merged with `defaults.matrix` and each agent's `matrix` override.

Common fields:

- `id`: manager-local profile ID.
- `homeserver`: Matrix homeserver URL. Required before a managed agent can run.
- `user_id`: bot account MXID. Required for password login.
- `device_id`: stable Matrix device ID. Useful for token-based E2EE sessions;
  password login can usually leave it unset.
- `password`: Matrix login password. Recommended together with `user_id`.
- `recovery_key`: E2EE secure backup recovery key.
- `access_token`: alternative token-based credential.
- `allowed_rooms`: canonical Matrix room IDs accepted for inbound messages.
- `mention_only`: in group rooms, respond only when the bot is mentioned.
- `interrupt_on_new_message`: cancel in-flight work when a newer message arrives.
- `reply_in_thread`: reply inside Matrix threads. Manager default: `false`.
- `ack_reactions`: send processing/done reactions. Manager default: `true`.
- `stream_mode`: `off`, `partial`, or `multi_message`. Manager default:
  `multi_message`.
- `multi_message_delay_ms`: delay between split paragraph messages. Default:
  `800`.
- `channel_debounce_ms`: rendered as `[channels].debounce_ms`. Default: `0`.

Advanced fields supported by the manager include:

- `draft_update_interval_ms`: edit interval for `partial` streaming. Default:
  `1500`.
- `approval_timeout_secs`: Matrix approval timeout. Manager default: `3600`.
- `excluded_tools`: tool names hidden from the model for Matrix turns.
- `reply_min_interval_secs`: outbound pacing floor. `0` disables pacing.
- `reply_queue_depth_max`: outbound pacing queue depth.
- `host_ip`: per-profile override for the `matrix-host` extra host IP.

## Secrets

`config/secrets.yaml` may contain plaintext local secrets:

- `vision.api_key`
- `agents.<agent>.model_api_key`
- `agents.<agent>.matrix_access_token`
- `agents.<agent>.matrix_password`
- `agents.<agent>.matrix_recovery_key`
- `agents.<agent>.mcp_gateway_token`

The current manager UI may store secrets inline in the primary config when
edited there. Exports and logs redact secret-like keys by default. Keep local
config files out of Git either way.

## Validation

Validation checks agent names, duplicate ports, profile references, Matrix
credentials, Matrix peers, workspace writability, server bind address, and
local ignore rules.
