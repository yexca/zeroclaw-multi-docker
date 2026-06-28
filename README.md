# ZeroClaw Dockyard

ZeroClaw Dockyard is a local WebUI for creating and operating multiple
ZeroClaw Matrix agents from one Docker Compose project.

Start Dockyard, open the WebUI, then create agents, reusable profiles, prompt
templates, and runtime settings without editing YAML by hand.

Chinese documentation is available in [README.zh-cn.md](README.zh-cn.md).

## What You Get

- A local manager WebUI at `http://127.0.0.1:7652`.
- A Docker socket proxy so the manager does not mount
  `/var/run/docker.sock` directly.
- WebUI editors for agents, LLM profiles, Vision LLM profiles, Matrix
  profiles, MCP profiles, skills, and prompt templates.
- Dashboard controls for starting, stopping, restarting, validating, and
  inspecting agents.
- Per-agent workspaces and generated runtime configuration.

Compose starts only the manager and socket proxy. Agent containers are created
later from the WebUI.

## Requirements

- Docker Desktop or Docker Engine with Docker Compose.
- Local browser access to `127.0.0.1:7652`.
- PowerShell, if you are running the commands below on Windows.

## Start

```powershell
docker compose up -d
```

Open:

```text
http://127.0.0.1:7652
```

By default Compose uses the published manager image:

```text
yexca/zeroclaw-dockyard:v0.2.0
```

To build the manager from this source tree instead:

```powershell
docker compose up -d --build
```

## Create Agents

In the WebUI:

1. Open **Profiles** and create the LLM, Vision, Matrix, or MCP profiles you
   need.
2. Open **Agents** and create an agent with a host port and profile
   assignments.
3. Choose or edit a prompt template.
4. Save and validate the agent.
5. Start the agent from the Dashboard or agent actions.

The Dashboard shows runtime status, logs, config hashes, rebuild status, and
recent manager operations.

## Local Data

Dockyard keeps local runtime data in the project directory:

- `config/manager.yaml`: saved manager configuration.
- `config/secrets.yaml`: local secrets, when used.
- `config/generated/`: generated previews and exports.
- `instances/`: per-agent workspace and runtime files.
- `shared/`: shared skill bundles and support files.

These files are local operator state. The included `.gitignore` is configured
so normal local configuration, secrets, generated files, and agent instances
stay out of Git.

## Default Agent Image

Manager-created agents use:

```env
ZEROCLAW_IMAGE=ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian
```

You can override the image with the `ZEROCLAW_IMAGE` environment variable,
manager configuration, or per-agent settings in the WebUI.

## Stop

```powershell
docker compose down
```

This stops the manager and socket proxy. Manager-created agent containers are
controlled from the WebUI.

## Documentation

- [Documentation index](docs/README.md)
- [Quickstart](docs/getting-started/quickstart.md)
- [WebUI usage](docs/guides/webui-usage.md)
- [Configuration schema](docs/reference/config-schema.md)
- [API reference](docs/reference/api.md)
- [Architecture](docs/concepts/architecture.md)
- [Docker socket proxy security](docs/concepts/docker-socket-proxy-security.md)
- [Release build notes](docs/development/release-build.md)
