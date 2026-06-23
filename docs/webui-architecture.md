# WebUI Architecture

This document describes the target architecture introduced by the manager
skeleton. The current repository still supports the existing static
`agent1`/`agent2`/`agent3` Compose services while adding the structure needed
for a local WebUI-driven runtime.

## Directory Layout

```text
manager/
  backend/        Minimal manager API service.
  frontend/       Static WebUI shell served by the backend.
  Dockerfile      Container image for the manager service.
  README.md       Manager-specific development notes.
config/
  manager.example.yaml
  secrets.example.yaml
  generated/
docs/
  webui-architecture.md
```

The layout follows the prompt recommendation so future backend, frontend,
configuration, and generated output work can evolve independently.

## Services

`docker-compose.yml` now defines these management services:

- `manager`: local WebUI and API process. It is published only on
  `127.0.0.1:${MANAGER_HOST_PORT:-7652}`.
- `docker-socket-proxy`: the only service with direct access to
  `/var/run/docker.sock`. The manager talks to Docker through
  `http://docker-socket-proxy:2375`.

The existing `agent1`, `agent2`, and `agent3` services are unchanged in purpose
and can still be started directly with:

```sh
docker compose up -d agent1 agent2 agent3
```

## Configuration Flow

The target configuration source is `config/manager.yaml`, copied locally from
`config/manager.example.yaml`. This file describes non-secret runtime settings:

- manager bind and port settings;
- Docker proxy URL and project naming;
- paths for generated output and agent instance data;
- shared ZeroClaw defaults;
- agent definitions such as model provider, Matrix identity, ports, and enabled
  state.

Secrets are stored separately in `config/secrets.yaml`, copied locally from
`config/secrets.example.yaml`. It may contain plaintext API keys, Matrix access
tokens, passwords, recovery keys, and gateway tokens.

Only `*.example.yaml` files are intended for Git. Local config and secrets files
are ignored by `.gitignore`.

Future manager stages should load both files, validate them as one logical
configuration, and render audit-friendly outputs under `config/generated/`.
Generated files are ignored except for `config/generated/.gitkeep`.

## Runtime Flow

The current manager container is a skeleton service with:

- `GET /healthz` for container health and smoke checks;
- `GET /api/status` for basic environment and wiring visibility;
- static frontend files served from `manager/frontend`.

The target runtime flow is:

1. The user edits configuration through the WebUI.
2. The backend validates and saves `config/manager.yaml` and
   `config/secrets.yaml`.
3. The backend renders deterministic generated configuration files for review,
   backup, and migration.
4. The backend reconciles desired agent state against Docker containers.
5. Agent containers continue using `bootstrap/render-config.sh` to produce the
   final `/zeroclaw-data/.zeroclaw/config.toml` inside each instance.

This stage intentionally does not implement the full reconciliation engine or
agent lifecycle API.

## Docker API Flow

The manager must not mount the Docker socket directly. Docker control follows
this path:

```text
browser -> manager WebUI/API -> docker-socket-proxy -> Docker daemon
```

The Compose proxy service currently enables the broad capabilities needed for
later development of container, image, network, volume, and write operations.
Permission tightening and exact endpoint selection are deferred to the Docker
socket proxy implementation stage.

Agent containers created by the future manager should be labeled with the
Compose project or an explicit manager label so the backend can distinguish
managed ZeroClaw containers from unrelated Docker workloads.

## Security Boundaries

Implemented in this stage:

- The WebUI host port is bound to `127.0.0.1` only.
- The manager container has no direct Docker socket mount.
- Docker socket access is isolated in `docker-socket-proxy`.
- Local plaintext secrets files are ignored by Git.
- Example config files contain placeholders only.

Deferred to later stages:

- Narrow Docker socket proxy permissions to the exact API surface required.
- Validate all config and secret fields before writing files or touching
  containers.
- Add CSRF and browser-origin protections if non-loopback access is ever
  supported.
- Add explicit safeguards before deleting containers, volumes, generated files,
  or instance data.
- Add logs and audit records for manager-initiated Docker operations.

## Compatibility

The static Compose services remain available during the migration. This lets
operators keep their current `.env` workflow while the WebUI manager matures
into the primary control plane.
