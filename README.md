# ZeroClaw Multi Docker

Docker Compose templates for running multiple ZeroClaw Matrix agents from one host.

This project uses the official ZeroClaw `v0.8.1-debian` image. The Debian image
includes a shell and Matrix support, so this repository no longer builds or
patches a local ZeroClaw image. It provides per-agent workspaces, per-agent
model providers, optional vision routing, optional MCP gateway access, and an
optional proactive wake-up sidecar.

Chinese documentation is available in [README.zh-cn.md](README.zh-cn.md).

## What Is Included

- `docker-compose.yml`: three example agents, `agent1`, `agent2`, and `agent3`, plus an optional proactive sidecar.
- `.env.example`: public placeholder configuration for the official image, model providers, Matrix accounts, MCP, and proactive wake-ups.
- `bootstrap/render-config.sh`: renders a ZeroClaw schema v3 `config.toml` inside each container.
- `proactive/proactive.py`: optional sidecar that periodically POSTs wake prompts to each agent gateway.
- `tools/add-agent.ps1`: PowerShell helper for adding more agent services.
- `tools/reset-agent-state.ps1`: helper for clearing generated state and rotating Matrix device IDs.
- `templates/workspace/`: blank starter files for per-agent workspace instructions and memory.

## Image

The default image is:

```env
ZEROCLAW_IMAGE=ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian
```

This image was tested with `bootstrap/render-config.sh`; `zeroclaw channel list`
reports Matrix as available after rendering a Matrix config.

To pre-pull it:

```powershell
docker pull ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian
```

To upgrade later, change `ZEROCLAW_IMAGE` in `.env` to the new official Debian
tag and restart the services.

## Configure

```powershell
cd zeroclaw_multi_docker
Copy-Item .env.example .env
```

Edit `.env` and fill at least:

- `MATRIX_HOMESERVER`
- `AGENT*_MATRIX_USER_ID`
- `AGENT*_MATRIX_PASSWORD` or `AGENT*_MATRIX_ACCESS_TOKEN`
- `AGENT*_MATRIX_RECOVERY_KEY`, if using Matrix E2EE.
- `AGENT*_MATRIX_EXTERNAL_PEERS`, including allowed sender MXIDs and outbound room targets.
- `AGENT*_MODEL_*`, or keep the example DeepSeek, Ollama, and Gemini defaults.
- `VISION_API_KEY`, if you want Matrix image messages routed to a vision model.

Initialize workspace files:

```powershell
New-Item -ItemType Directory -Force instances\agent1\workspace,instances\agent2\workspace,instances\agent3\workspace
Copy-Item templates\workspace\* instances\agent1\workspace\
Copy-Item templates\workspace\* instances\agent2\workspace\
Copy-Item templates\workspace\* instances\agent3\workspace\
```

## Run

```powershell
docker compose up -d agent1 agent2 agent3
```

Default gateway ports bind to localhost:

- agent1: `http://127.0.0.1:42641`
- agent2: `http://127.0.0.1:42642`
- agent3: `http://127.0.0.1:42643`

## Per-Agent Model Providers

Each agent maps its own `AGENT*_MODEL_*` values to generic container variables
consumed by `bootstrap/render-config.sh`. The renderer writes one primary
provider block per container and points `agents.main.model_provider` at it.

Example `.env` entries:

```env
AGENT1_MODEL_PROVIDER_FAMILY=deepseek
AGENT1_MODEL_PROVIDER_ALIAS=text
AGENT1_MODEL=deepseek-chat
AGENT1_MODEL_BASE_URL=https://api.deepseek.com/v1
AGENT1_MODEL_API_KEY=
AGENT1_MODEL_WIRE_API=chat_completions
AGENT1_MODEL_TIMEOUT_SECS=120

AGENT2_MODEL_PROVIDER_FAMILY=ollama
AGENT2_MODEL_PROVIDER_ALIAS=local
AGENT2_MODEL=qwen2.5:14b
AGENT2_MODEL_BASE_URL=http://host.docker.internal:11434
AGENT2_MODEL_API_KEY=
AGENT2_MODEL_WIRE_API=chat_completions
AGENT2_MODEL_TIMEOUT_SECS=600

AGENT3_MODEL_PROVIDER_FAMILY=gemini
AGENT3_MODEL_PROVIDER_ALIAS=flash
AGENT3_MODEL=gemini-2.5-flash
AGENT3_MODEL_BASE_URL=
AGENT3_MODEL_API_KEY=
AGENT3_MODEL_WIRE_API=
AGENT3_MODEL_TIMEOUT_SECS=120
```

`MODEL_PROVIDER_FAMILY` and `MODEL_PROVIDER_ALIAS` become the dotted provider
reference, such as `ollama.local`, `deepseek.text`, `openai.main`, or
`gemini.flash`.

A v3 `model_routes` entry named `vision` points to `custom.vision`, and query
classification routes messages containing Matrix image markers (`[IMAGE:` /
`[Image:`) to that vision model.

## MCP Gateway

Each agent can send a distinct bearer token to the host MCP gateway:

```env
AGENT1_MCP_GATEWAY_TOKEN=agent1-token
AGENT2_MCP_GATEWAY_TOKEN=agent2-token
AGENT3_MCP_GATEWAY_TOKEN=agent3-token
```

Compose maps each value into that container as `MCP_GATEWAY_TOKEN`. The shared
`MCP_GATEWAY_TOKEN` remains a fallback when an agent-specific value is empty.

## Inbound Debounce And Timeouts

By default, `CHANNEL_DEBOUNCE_MS=3000` renders `[channels].debounce_ms = 3000`.
Rapid messages from the same sender/session are merged and dispatched after a
3-second quiet window. Set it to `0` to disable inbound debouncing.

Shell execution limits are configured with:

```env
SHELL_TIMEOUT_SECS=300
SHELL_TOOL_TIMEOUT_SECS=300
```

## Add Another Agent

```powershell
.\tools\add-agent.ps1 -Id 4 -ProviderFamily ollama -ProviderAlias local -Model "qwen2.5:14b"
```

The script creates `instances/agent4/workspace`, appends `AGENT4_MODEL_*`,
Matrix, and `AGENT4_MCP_GATEWAY_TOKEN` entries to `.env`, inserts an `agent4`
service into `docker-compose.yml`, and adds the service to proactive sidecar
dependencies.

Useful options:

- `-HostPort 42644` chooses the localhost gateway port.
- `-MatrixUserId "@agent4:matrix.example.com"` pre-fills the Matrix user ID.
- `-ExternalPeers "@you:matrix.example.com,#agent4-room:matrix.example.com"` pre-fills the peer gate.
- `-ProactiveTarget "#agent4-room:matrix.example.com"` adds the proactive target mapping.
- `-ProviderFamily ollama|deepseek|openai|gemini` chooses the provider family.
- `-ProviderAlias local` chooses the alias segment in `ollama.local`.
- `-Model "qwen2.5:14b"` sets the model identifier sent to the provider.
- `-BaseUrl "http://host.docker.internal:11434"` overrides the provider endpoint.
- `-ApiKey "sk-..."` sets the provider key when needed.
- `-WireApi chat_completions` sets OpenAI-compatible chat completions.
- `-DryRun` previews filesystem and config changes.

## Reset Agent State

Use `tools/reset-agent-state.ps1` when you need to clear generated ZeroClaw
state while keeping workspace files:

```powershell
.\tools\reset-agent-state.ps1 -Agent agent1 -DryRun
.\tools\reset-agent-state.ps1 -Agent agent1
```

The script removes generated config/state directories and rotates the selected
agent's `AGENT*_MATRIX_DEVICE_ID` in `.env`.

## Proactive Sidecar

The sidecar is disabled by default. To enable it, set:

```dotenv
PROACTIVE_ENABLED=true
PROACTIVE_TARGETS=agent1=#agent1-room:matrix.example.com,agent2=#agent2-room:matrix.example.com,agent3=#agent3-room:matrix.example.com
```

Then start it:

```powershell
docker compose up -d proactive
```

The sidecar wakes each configured agent at randomized intervals by posting to
`/webhook`. The agent decides whether to send an outbound Matrix message.

## Keep Secrets Out Of Git

Do not commit:

- `.env`
- `instances/*/.zeroclaw/`
- `instances/*/data/`
- `instances/*/workspace/sessions/`
- SQLite databases, Matrix crypto stores, sockets, logs, backups, generated media, and local workspace files
- `proactive/state/`

The included `.gitignore` covers these paths. Before publishing, run:

```powershell
rg -n "api[_-]?key|token|password|recovery|secret|PRIVATE KEY|Bearer " .
```
