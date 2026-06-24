# WebUI Usage

The WebUI manager is the only control plane.

## Start

```powershell
docker compose up -d
```

Open `http://127.0.0.1:7652`.

`docker compose up -d` starts only `manager` and `docker-socket-proxy`. No
agent containers start until the WebUI creates them.

Create and edit manager configuration from the WebUI. Saved local config and
secret files are ignored by Git.

## Main Workflows

- Dashboard: view state, Docker details, logs, config hash, rebuild status, and
  operation history.
- Agents: create, edit, validate, start, stop, restart, delete, export, and
  apply prompt templates.
- Profiles: edit reusable LLM, Vision LLM, Matrix, and MCP profiles.
- Skills: edit runtime skill settings, skill bundles, canonical `SKILL.md`
  files, and support files.
- Prompt templates: edit workspace files that can be applied to agents.
- Export: write redacted generated configuration under `config/generated/`.

## Skills

The Skills view manages canonical Agent Skills. A bundle points at a directory
under `shared/skills/`, and each skill is stored as:

```text
shared/skills/<bundle>/<skill>/
  SKILL.md
  scripts/
  references/
  assets/
```

`SKILL.md` uses YAML frontmatter (`name`, `description`, optional `version`,
`author`, `license`, `category`, and `tags`) followed by Markdown instructions.
Support files can be written under `references/`, `scripts/`, or `assets/`.
Script files are blocked unless `skills.allow_scripts` is enabled.

Agents load skills by listing bundle aliases in the Agent Editor's Skill
bundles field. The manager renders those aliases into the agent's ZeroClaw
`config.toml` and syncs `shared/` into runtime volumes before agent
start/restart. In bind storage mode, `./shared` is mounted into the agent at
`/zeroclaw-data/shared`.

## Prompt Templates

Prompt templates edit reusable files that the manager can write into an
agent's workspace root. The editor shows files as horizontal tabs so operators
can switch between official ZeroClaw personality files and custom workspace
files without scrolling through every file at once.

For normal channel turns, ZeroClaw's source-defined system prompt path injects
workspace files in this order:

```text
normal channel system prompt:
  tools/safety/skills/workspace
  + AGENTS.md
  + SOUL.md
  + TOOLS.md
  + IDENTITY.md
  + USER.md
  + BOOTSTRAP.md if it exists
  + MEMORY.md when memory injection is enabled
  + current date/runtime/channel capabilities
```

`HEARTBEAT.md` is also written to the workspace root, but it is intentionally
excluded from normal channel prompts. The heartbeat worker reads it separately
and treats lines beginning with `- ` as periodic tasks. Task metadata supports
priority and status tags such as `[high]`, `[low|paused]`, and `[completed]`.

Custom files such as `RHYTHM.md` can be saved and applied to a workspace, but
ZeroClaw does not automatically read them. To make custom files effective,
reference them from an official file such as `AGENTS.md` or `USER.md`.

The AI fill button can draft every file in the selected prompt template from an
LLM Profile. The dialog lets operators choose the model profile, edit the
generation instruction, describe who the agent is, and optionally send selected
current template files as reference context. Generated content is applied only
to the browser-side template draft; review the file tabs and click Save to
persist it.

## LLM Profiles

The LLM Profiles view edits reusable model provider profiles under
`profiles.llm`.

Creating a new LLM profile starts from the OpenAI preset. The provider selector
can also apply presets for DeepSeek, Ollama, Gemini, and OpenAI-compatible
endpoints. Changing the provider overwrites preset-managed fields such as
provider alias, base URL, model, wire API, and timeout, but it keeps the profile
ID and API key.

Core fields:

- `ID`: manager-local profile ID used by agents through `llm_profile`.
- `Provider`: ZeroClaw provider family, such as `openai`, `deepseek`,
  `ollama`, `gemini`, or `custom`.
- `Provider alias`: the alias half of ZeroClaw's
  `[providers.models.<family>.<alias>]` entry. Use aliases to keep multiple
  profiles for the same family, such as `openai.default` and `openai.review`.
- `Base URL`: endpoint URL. For OpenAI-compatible endpoints, include the API
  prefix when required, for example `https://api.example.com/v1`.
- `Model`: provider-local model ID.
- `Wire API`: request protocol. Use `chat_completions` for ordinary
  `/v1/chat/completions` or compatible endpoints. Use `responses` only for
  OpenAI Responses/Codex style `/v1/responses` endpoints or compatible services
  that explicitly require it.

Advanced settings are folded under the advanced panel. They map to ZeroClaw
provider fields such as temperature, fallback models, extra HTTP headers,
provider-specific request body extras, cost pricing, TLS CA path, Gemini OAuth
settings, and Ollama context/output overrides.

The frontend validates required strings, numeric ranges, URLs, and JSON fields
before saving. Invalid fields are reported in a browser alert with the specific
field name.

## Vision LLM Profiles

The Vision LLM Profiles view edits reusable image-attachment routes under
`profiles.vision`. Agents can select one with `vision_profile`; leaving it
empty disables the dedicated vision route for that agent. The manager renders
the selected profile into a dedicated ZeroClaw provider and sets
`multimodal.vision_model_provider`, so text-only default models can still hand
image turns to a vision-capable model.

Use the same provider family, base URL, model, wire API, timeout, and API key
patterns as LLM profiles. The multimodal limits control how many images are
kept in one request, maximum image size, how many recent turns keep image data,
and whether http/https image URLs may be fetched remotely.

## Agents

The Agents view now focuses on container/runtime wiring and per-agent peer
membership. Required fields include the agent ID, host port, LLM profile, and
Matrix profile. The WebUI uses Agent ID as the visible identity. Matrix identity
and credential fields such as `user_id`, `device_id`, `password`,
`access_token`, and `recovery_key` are edited in the Matrix Profiles view.

Agent-level Matrix settings should normally be limited to `external_peers`,
which controls the generated Matrix peer group for that one agent. This field
is required because ZeroClaw uses it to authorize inbound Matrix peers and
`send_message_to_peer` outbound targets. Advanced agent settings include Docker
image, prompt template apply mode, and explicit environment overrides.

Saving an agent stores its manager configuration. Applying its prompt template
initializes the agent workspace by writing the selected prompt files. The
Dashboard only lists agents whose workspace has been initialized, so draft
configurations do not appear as runnable agents until `Apply template` has
created their workspace files.

When Docker runtime storage is `volume`, the manager keeps local agent files
under `instances/` for inspection and uses a Docker named volume for the running
container. Starting or restarting an agent syncs local files into the runtime
volume first. The Agent Editor also exposes manual sync actions for copying
local files to the runtime volume or copying runtime changes back to local
files under its advanced action menu.

The same advanced action menu includes Matrix E2EE state reset. The reset action
is refused while the agent container is running. When confirmed for a stopped
agent, it removes `.zeroclaw/state/matrix/` from the agent state and rotates the
agent's Matrix `device_id` override. Restart the agent afterwards so
`config.toml` is rendered with the new device ID.

The Proactive sidecar section can create one companion container per agent.
The sidecar reads the agent's configured `host_port` and calls that agent's
gateway automatically through `/webhook?agent=<id>`. Operators normally do not
enter a port in the proactive form; the advanced Gateway URL override exists for
custom gateways or experiments. If no explicit target is configured, the
sidecar uses the first External peers entry. The default wake prompt asks the
agent to review `PROACTIVE.md`, memory, and current context before deciding
whether to send one short Matrix message or return `skip`.

## Matrix Profiles

The Matrix Profiles view edits reusable Matrix channel profiles under
`profiles.matrix`. Matrix values are resolved in this order:

```text
defaults.matrix -> profiles.matrix[] -> agents[].matrix
```

The profile form is split into core identity, common behavior, and advanced
settings. Each text input uses placeholder text to explain the field, and field
labels expose the same help text as a browser tooltip.

Core fields:

- `ID`: manager-local profile ID used by agents through `matrix_profile`.
- `Homeserver`: required Matrix homeserver URL.
- `Matrix user`: bot account MXID. Required for the recommended password login
  path.
- `Device ID`: stable Matrix device ID. Keep it stable for token-based E2EE
  sessions; password login can usually leave it empty.
- `Password`: recommended login credential when used with `Matrix user`.
- `Recovery key`: recommended for E2EE rooms so ZeroClaw can restore room keys
  and cross-sign the bot device.
- `Allowed rooms`: canonical Matrix room IDs. Empty means all rooms the bot has
  joined. Use `!room:server` IDs, not `#alias:server` aliases.

Common behavior defaults:

- `Reply in thread`: off.
- `Stream mode`: `multi_message`.
- `Multi-message delay ms`: `800`.
- `Channel debounce ms`: `0`.

`Access token` is available in the common behavior section for operators who
must reuse an existing token. Prefer `Matrix user` + `Password` unless token
reuse is required.

Advanced settings include partial-stream draft interval, approval timeout,
excluded tools, outbound pacing fields, and `host_ip` override. These settings
are rendered into the generated ZeroClaw Matrix channel config for agent
containers.

## Files

Commit examples only:

- `config/manager.example.yaml`
- `config/secrets.example.yaml`

Do not commit local/runtime files:

- `config/manager.yaml`
- `config/secrets.yaml`
- `config/manager.local.yaml`
- `config/secrets.local.yaml`
- `config/generated/*`
- `instances/*`
- `shared/*` unless you intentionally want to version local skill bundles

## Troubleshooting

- If Docker API calls fail, check `docker-socket-proxy` is running.
- If managed containers fail to start, validate the agent in the WebUI first.
- If bind mounts fail, check that `./bootstrap` and `./instances` are mounted
  into the manager service and that the manager can inspect itself through the
  socket proxy.
- Use dashboard logs and operation history for runtime diagnosis.
