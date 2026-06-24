# ZeroClaw Multi Docker

Local WebUI manager for creating and operating multiple ZeroClaw Matrix agents
from one Docker Compose project.

The manager is the only default entrypoint. A plain `docker compose up -d`
starts the WebUI and Docker socket proxy; agent containers are created,
configured, started, stopped, and deleted by the WebUI through the Docker API.

The manager image builds the frontend inside Docker and serves the generated
static files from the Python backend. The WebUI loads configuration first and
refreshes Docker-backed dashboard status in the background.

Chinese documentation is available in [README.zh-cn.md](README.zh-cn.md).

## What Is Included

- `docker-compose.yml`: WebUI manager and Docker socket proxy.
- `config/manager.example.yaml`: structured manager configuration.
- `config/secrets.example.yaml`: local plaintext secrets template.
- `manager/`: WebUI backend and frontend.
- `bootstrap/render-config.sh`: rendered into manager-created agent containers.
- `manager/backend/prompt_templates/`: starter workspace prompt files.
- `docs/`: operator, reference, architecture, and development docs.

## Start

```powershell
Copy-Item config\manager.example.yaml config\manager.yaml
Copy-Item config\secrets.example.yaml config\secrets.yaml
docker compose up -d
```

Open `http://127.0.0.1:7652`.

The manager binds to `127.0.0.1` and reaches Docker through
`docker-socket-proxy`. The manager container does not mount
`/var/run/docker.sock` directly.

## Configure Agents

Use the WebUI to edit:

- LLM profiles
- Matrix profiles
- MCP profiles
- prompt templates
- per-agent ports, identities, model/profile assignments, and secrets

The dashboard shows runtime status, logs, config hashes, rebuild status, and
operation history.

Detailed docs:

- [Documentation index](docs/README.md)
- [Quickstart](docs/getting-started/quickstart.md)
- [WebUI usage](docs/guides/webui-usage.md)
- [Configuration schema](docs/reference/config-schema.md)
- [API reference](docs/reference/api.md)
- [Architecture](docs/concepts/architecture.md)
- [Docker socket proxy security](docs/concepts/docker-socket-proxy-security.md)

## Image

Manager-created agents use:

```env
ZEROCLAW_IMAGE=ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian
```

Override it with the `ZEROCLAW_IMAGE` environment variable,
`config/manager.yaml`, or per-agent config.

## Keep Secrets Out Of Git

Do not commit:

- `.env`
- `config/manager.yaml`
- `config/secrets.yaml`
- `config/manager.local.yaml`
- `config/secrets.local.yaml`
- `config/generated/*`
- `instances/*`

The included `.gitignore` covers these paths.

## Tests And Release Checks

Run the full local release check:

```powershell
.\tools\release-checks.ps1
```

Individual checks:

```powershell
docker compose config --quiet
python -m unittest discover manager/backend/tests
node manager/frontend/tests/ui-foundation.test.mjs
```

The Docker image build runs the frontend build in a `node:22-alpine` stage:

```powershell
docker build -t zeroclaw-manager:test ./manager
```
