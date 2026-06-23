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
  `http://docker-socket-proxy:2375` on the internal `manager-control` network.

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

Agent rendering resolves profile references, agent overrides, and defaults into
the environment variables expected by `bootstrap/render-config.sh`. The manager
can export the resolved environment, an equivalent compose fragment, and a
readable ZeroClaw `config.toml` preview before a container is started.
Workspace initialization writes selected prompt template files under
`instances/{agent}/workspace` and supports explicit keep, missing-only,
overwrite, and merge modes.

Validation runs before agent startup and is available through the API for WebUI
forms. It checks agent identity, host ports, image/model settings, profile and
template references, Matrix credentials and peers, MCP URL requirements, and
workspace writability. Normal exports and API rendering responses redact
secret-like values; full secret exports require an explicit local
`include_secrets` request.

## Docker API Flow

The manager must not mount the Docker socket directly. Docker control follows
this path:

```text
browser -> manager WebUI/API -> docker-socket-proxy -> Docker daemon
```

The Compose proxy service uses `tecnativa/docker-socket-proxy` because it is a
small HAProxy-based image that gates Docker API URL sections through environment
variables. It is attached only to the internal `manager-control` network and is
not published to the host.

The manager receives the proxy URL through `DOCKER_API_URL`, defaulting to
`http://docker-socket-proxy:2375`.

### Proxy Permissions

Enabled permissions:

- `PING=1` and `VERSION=1`: health checks and Docker API compatibility checks.
- `CONTAINERS=1`: list and inspect containers, create manager-owned agent
  containers, delete manager-owned containers, and read container logs.
- `ALLOW_START=1`: start manager-owned agent containers.
- `ALLOW_STOP=1`: stop manager-owned agent containers.
- `ALLOW_RESTARTS=1`: restart manager-owned agent containers. The proxy image
  also allows the Docker `kill` path under this switch, so manager code must not
  call `kill` unless a later safety review explicitly adds that behavior.
- `IMAGES=1`: inspect local images and pull the configured ZeroClaw image.
- `NETWORKS=1`: inspect or create the dedicated runtime network used by managed
  agents.
- `POST=1`: required by Docker for create, start, stop, restart, delete, pull,
  and network creation operations.

Explicitly disabled permissions:

- `AUTH`, `BUILD`, `COMMIT`, `CONFIGS`, `DISTRIBUTION`, `EXEC`, `GRPC`, `INFO`,
  `NODES`, `PLUGINS`, `SECRETS`, `SERVICES`, `SESSION`, `SWARM`, `SYSTEM`,
  `TASKS`, and `VOLUMES`.
- `ALLOW_PAUSE` and `ALLOW_UNPAUSE`.
- `EVENTS`, until a later observability phase needs Docker event streaming.

The disabled set intentionally excludes unrelated capabilities such as Docker
exec, system operations, swarm/service management, secret access, image build,
and global volume deletion.

Agent containers created by the future manager should be labeled with the
Compose project or an explicit manager label so the backend can distinguish
managed ZeroClaw containers from unrelated Docker workloads.

The current Docker API implementation uses only ping/version-compatible
connectivity, image pull, network inspect/create, container inspect/list,
create, start, stop, restart, delete, and logs. It does not call Docker exec,
kill, volume deletion, system, swarm, service, secret, or build endpoints.

## Security Boundaries

Implemented in this stage:

- The WebUI host port is bound to `127.0.0.1` only.
- The manager container has no direct Docker socket mount.
- Docker socket access is isolated in `docker-socket-proxy`.
- The socket proxy is reachable only from containers attached to the internal
  `manager-control` network.
- Socket proxy permissions are limited to the Docker API sections needed for
  agent container lifecycle, image pull/inspect, logs, and runtime network
  management.
- Local plaintext secrets files are ignored by Git.
- Example config files contain placeholders only.

Implemented in the Docker runtime stage:

- The manager talks to Docker only through `DOCKER_API_URL`, normally the
  socket proxy on the internal `manager-control` network.
- Agent runtime operations create stable `zeroclaw-matrix-{agent}` containers
  with `zeroclaw.manager=true`, `zeroclaw.agent.id`, and
  `zeroclaw.agent.name` labels.
- Start reconciles desired container configuration, recreating only
  manager-owned containers when the stored spec hash changes.
- Stop, restart, delete, status, and logs refuse to operate on a same-named
  container without matching manager labels.
- Agent configuration deletion keeps instance data by default and only deletes
  the instance directory when explicitly requested.
- Host gateway and Matrix host aliases are configured through Docker
  `ExtraHosts`, and the gateway port is published on `127.0.0.1`.

Deferred to later stages:

- Validate all config and secret fields before writing files or touching
  containers.
- Add CSRF and browser-origin protections if non-loopback access is ever
  supported.
- Add explicit safeguards before deleting containers, volumes, generated files,
  or instance data.
- Add logs and audit records for manager-initiated Docker operations.

The proxy remains a high-privilege security boundary. Any service that can reach
it can still perform the enabled Docker write operations against the host daemon.
This is more controllable than mounting `/var/run/docker.sock` into the manager,
but it does not make Docker control low-risk.

## Compatibility

The static Compose services remain available during the migration. This lets
operators keep their current `.env` workflow while the WebUI manager matures
into the primary control plane.
