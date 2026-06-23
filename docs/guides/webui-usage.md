# WebUI Usage

The WebUI manager is the only control plane.

## Start

```powershell
Copy-Item config\manager.example.yaml config\manager.yaml
Copy-Item config\secrets.example.yaml config\secrets.yaml
docker compose up -d
```

Open `http://127.0.0.1:7652`.

`docker compose up -d` starts only `manager` and `docker-socket-proxy`. No
agent containers start until the WebUI creates them.

## Main Workflows

- Dashboard: view state, Docker details, logs, config hash, rebuild status, and
  operation history.
- Agents: create, edit, validate, start, stop, restart, delete, export, and
  apply prompt templates.
- Profiles: edit reusable LLM, Matrix, and MCP profiles.
- Prompt templates: edit workspace files that can be applied to agents.
- Export: write redacted generated configuration under `config/generated/`.

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

## Troubleshooting

- If Docker API calls fail, check `docker-socket-proxy` is running.
- If managed containers fail to start, validate the agent in the WebUI first.
- If bind mounts fail, check that `./bootstrap` and `./instances` are mounted
  into the manager service and that the manager can inspect itself through the
  socket proxy.
- Use dashboard logs and operation history for runtime diagnosis.
