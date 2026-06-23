# Quickstart

ZeroClaw Multi Docker starts only the local manager WebUI and Docker socket
proxy. Agent containers are created later from the WebUI.

## Requirements

- Docker Desktop or Docker Engine with Compose.
- PowerShell for the commands below on Windows.
- Local loopback access to `127.0.0.1:7652`.

## Prepare Local Config

```powershell
Copy-Item config\manager.example.yaml config\manager.yaml
Copy-Item config\secrets.example.yaml config\secrets.yaml
```

Local config and secrets files are ignored by Git.

## Start The Manager

```powershell
docker compose up -d
```

Open:

```text
http://127.0.0.1:7652
```

The first screen opens the configuration editor before Docker status is loaded,
so the WebUI stays usable even when Docker status calls are slow.

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
