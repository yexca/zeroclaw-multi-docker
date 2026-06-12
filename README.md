# ZeroClaw Multi Docker

Docker Compose templates for running multiple ZeroClaw Matrix agents from one host.

This project provides a repeatable container setup for ZeroClaw `0.8.0-beta-2` with Matrix channel support, per-agent workspaces, optional vision routing, optional MCP gateway access, and an optional proactive wake-up sidecar.

Chinese documentation is available in [README.zh-cn.md](README.zh-cn.md).

## What Is Included

- `docker-compose.yml`: three example agents, `agent1`, `agent2`, and `agent3`, plus an optional proactive sidecar.
- `.env.example`: public placeholder configuration for model providers, Matrix accounts, MCP, and proactive wake-ups.
- `bootstrap/render-config.sh`: renders a ZeroClaw schema v3 `config.toml` inside each container.
- `proactive/proactive.py`: optional sidecar that periodically POSTs wake prompts to each agent gateway.
- `tools/add-agent.ps1`: PowerShell helper for adding more agent services.
- `templates/workspace/`: blank starter files for per-agent workspace instructions and memory.
- `patches/zeroclaw-0.8.0-beta2-docker-matrix.patch`: patch used to build the Matrix-enabled Docker image described below.

## Build The Image

The upstream version is `0.8.0-beta-2`. The patch in this repository is generated against ZeroClaw commit `af50475a37fa9d2ae78758d2fbe82bda67218c17`, whose Cargo package version is still `0.8.0-beta-2`.

```powershell
git clone https://github.com/zeroclaw-labs/zeroclaw.git
cd zeroclaw
git checkout af50475a37fa9d2ae78758d2fbe82bda67218c17
git apply ..\zeroclaw_multi_docker\patches\zeroclaw-0.8.0-beta2-docker-matrix.patch
docker build -f Dockerfile.debian -t zeroclaw:0.8.0-beta2-matrix .
```

You can also build with `Dockerfile`:

```powershell
docker build -f Dockerfile -t zeroclaw:0.8.0-beta2-matrix .
```

## Patch Summary

The patch:

- Enables the `channel-matrix` Cargo feature in Docker builds.
- Adds missing workspace files to Docker dependency prefetch layers.
- Applies environment variable overrides before resolving channel runtime model providers.
- Checks `interrupt_on_new_message` across all channel aliases, not only `default`.
- Resolves multimodal vision fallback providers through configured dotted aliases such as `custom.vision`.

## Configure

```powershell
cd zeroclaw_multi_docker
Copy-Item .env.example .env
```

Edit `.env` and fill at least:

- `DEEPSEEK_API_KEY`, or replace the text provider settings with your own provider.
- `VISION_API_KEY`, if you want Matrix image messages routed to a vision model.
- `MATRIX_HOMESERVER`
- `AGENT*_MATRIX_USER_ID`
- `AGENT*_MATRIX_PASSWORD` or `AGENT*_MATRIX_ACCESS_TOKEN`
- `AGENT*_MATRIX_RECOVERY_KEY`, if using Matrix E2EE.
- `AGENT*_MATRIX_EXTERNAL_PEERS`, including allowed sender MXIDs and outbound room targets.

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

## Add Another Agent

```powershell
.\tools\add-agent.ps1 -Id 4 -HostPort 42644
```

The script creates `instances/agent4/workspace`, appends empty `AGENT4_*` values to `.env`, inserts an `agent4` service into `docker-compose.yml`, and adds the service to the proactive sidecar dependencies.

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

The sidecar wakes each configured agent at randomized intervals by posting to `/webhook`. The agent decides whether to send an outbound Matrix message.

## Keep Secrets Out Of Git

Do not commit:

- `.env`
- `instances/*/.zeroclaw/`
- `instances/*/data/`
- `instances/*/workspace/sessions/`
- SQLite databases, Matrix crypto stores, logs, backups, generated media, and local workspace files
- `proactive/state/`

The included `.gitignore` covers these paths. Before publishing, run:

```powershell
rg -n "api[_-]?key|token|password|recovery|secret|PRIVATE KEY|Bearer " .
```
