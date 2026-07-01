# Quickstart

ZeroClaw Dockyard starts only the local manager WebUI and Docker socket
proxy. Agent containers are created later from the WebUI.

## Requirements

- Docker Desktop or Docker Engine with Compose.
- PowerShell for the commands below on Windows.
- Local loopback access to `127.0.0.1:7652`.

## Start The Manager

```powershell
docker compose up -d
```

Open:

```text
http://127.0.0.1:7652
```

By default Compose uses the published `yexca/zeroclaw-dockyard:v0.2.1`
manager image. Developers who want to build from the local source tree can run
`docker compose up -d --build`.

The first screen opens the Dashboard. Configuration, Docker status, and runtime
details load through the WebUI after the Vue app mounts.

Create and edit manager configuration from the WebUI. Saved local config and
secret files are ignored by Git.

## Create Your First Agent

1. Open the **Agents** view.
2. Create or edit an agent ID and host port.
3. Choose LLM, Matrix, and MCP profiles if they are configured.
4. Save and validate the agent.
5. Start the agent from the Dashboard or agent actions.

No agent containers are started by Compose itself.

## Stop

```powershell
docker compose down
```

This stops the manager and socket proxy. Manager-created agent containers are
controlled from the WebUI.
