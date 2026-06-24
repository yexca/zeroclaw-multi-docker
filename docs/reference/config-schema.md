# Manager Configuration Schema

Primary config is YAML. The manager reads `config/manager.yaml` locally, or
`config/manager.example.yaml` if the local file does not exist. Secrets live in
`config/secrets.yaml` and are not committed.

## Top-Level Keys

- `version`: schema version, currently `1`.
- `webui`: default UI language and theme.
- `server`: local WebUI bind host and host port.
- `docker`: Docker API proxy URL, Compose project name, control network,
  runtime network, Matrix host IP, and optional runtime storage settings.
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

- `id`: unique identifier used by the WebUI. `name` is still accepted for
  legacy configs, but new WebUI edits use `id` as the visible identity.
- `enabled`: UI/runtime intent.
- `host_port`: loopback gateway port.
- `image`: Docker image for this agent. The WebUI fills the current default
  ZeroClaw image.
- `llm_profile`, `matrix_profile`, `mcp_profile`: profile references.
- `prompt_template`: workspace template reference.
- `matrix.external_peers`: required per-agent peer group members. Matrix
  identity, credentials, rooms, and channel behavior should live in the
  selected Matrix profile.
- `proactive`: optional per-agent proactive sidecar settings.
- `environment`: explicit environment overrides for advanced use.

`agents[].proactive` fields:

- `enabled`: create a per-agent proactive sidecar container.
- `target`: Matrix peer target used by `send_message_to_peer`. If empty, the
  first `matrix.external_peers` entry is used.
- `channel`: Matrix channel alias passed to `send_message_to_peer`. Default:
  `matrix.home`.
- `agent_url`: advanced full gateway URL override. Empty uses the agent's
  `host_port` automatically as `http://host.docker.internal:<port>/webhook?agent=<id>`.
- `random_min_minutes`, `random_max_minutes`: randomized wake interval range.
- `poll_seconds`: sidecar polling interval. Minimum recommended value: `30`.
- `quiet_hours`: local quiet-hour range such as `23-8`; empty disables quiet
  hours.
- `timezone`: timezone used for quiet hours.
- `prompt`: optional wake prompt override. Empty uses the built-in prompt that
  asks the agent to review `PROACTIVE.md`, memory, and current context.

## Docker Runtime Storage

`docker.storage_driver` controls how managed agent containers receive their
runtime filesystem:

- `volume` (default): use a per-agent Docker named volume for container runtime
  data, while keeping a local copy under `paths.instances_dir`. The manager
  syncs local files to the runtime volume before start/restart and can sync the
  runtime volume back to local files.
- `bind`: mount host paths directly, using `paths.host_instances_dir` and
  `paths.host_bootstrap_dir` or paths discovered from the manager container.

`docker.volume_prefix` optionally customizes runtime volume names. The default
prefix is `docker.project_name`.

## Prompt Template Fields

`prompt_templates` entries define reusable workspace files:

- `id`: manager-local template ID selected by agents through
  `prompt_template`.
- `description`: optional operator note shown in the WebUI.
- `files`: mapping of workspace file names to file content. Official prompt
  files include `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md`,
  `BOOTSTRAP.md`, `MEMORY.md`, and `HEARTBEAT.md`. Safe custom file names such
  as `RHYTHM.md` are also supported and written to the workspace when
  templates are applied.

Normal channel prompts inject `AGENTS.md`, `SOUL.md`, `TOOLS.md`,
`IDENTITY.md`, `USER.md`, optional `BOOTSTRAP.md`, and optional `MEMORY.md`.
`HEARTBEAT.md` is a workspace-root task file for the heartbeat worker and is
not injected into ordinary channel prompts. Custom files are not referenced by
ZeroClaw automatically; add an explicit reference from an official file when
the model should use a custom workspace file.

The WebUI AI fill action is an editing helper for this same `files` mapping. It
does not add configuration fields and generated drafts are not persisted until
the prompt template is saved.

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
