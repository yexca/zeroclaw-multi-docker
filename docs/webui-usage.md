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
