# WebUI Architecture

Compose starts only the local manager WebUI and Docker socket proxy. Agent
containers are created and operated by the manager through the Docker API.

## Services

- `manager`: local WebUI and API process, published only on
  `127.0.0.1:${MANAGER_HOST_PORT:-7652}`.
- `docker-socket-proxy`: the only service with direct access to
  `/var/run/docker.sock`. The manager talks to it on the internal
  `manager-control` network.

There are no static agent services in Compose.

## Configuration Flow

The manager reads `config/manager.yaml`, or `config/manager.example.yaml` when
the local file does not exist. Secrets live in `config/secrets.yaml`. Only
example files are committed.

The WebUI edits structured config, validates it, exports redacted generated
artifacts under `config/generated/`, and reconciles agent containers.

## Runtime Flow

1. The user edits agents, profiles, templates, and secrets in the WebUI.
2. The backend validates the config.
3. The backend resolves profiles and defaults into container environment.
4. The backend creates or recreates manager-owned Docker containers.
5. Agent containers run `bootstrap/render-config.sh` to render
   `/zeroclaw-data/.zeroclaw/config.toml`.

The manager labels containers with `zeroclaw.manager=true`,
`zeroclaw.agent.id`, `zeroclaw.agent.name`, and a spec hash. Runtime operations
refuse to modify same-named containers without matching manager labels.

Project-level skill bundles live under `shared/skills/`. In volume storage
mode, the manager copies `shared/` into each agent runtime volume before
start/restart so ZeroClaw can load the configured `[skill_bundles.*]`. In bind
storage mode, `shared/` is mounted into the agent at `/zeroclaw-data/shared`.

## Frontend Startup Flow

The frontend source is a Vue 3 application built by Vite. It uses Pinia for the
manager state store, Vue Router for the main sections, and lightweight local
components for the console-style UI. The Python backend still serves only static
files from the built `frontend/dist` output.

`index.html` includes a lightweight startup skeleton so the first paint is not
blank while the Vue bundle and API calls load. Vite emits hashed assets under
`/assets/`, while the backend serves `index.html` with no-cache headers.

Startup applies the locally stored theme before loading CSS, mounts the Vue app
from `src/main.js`, loads manager data through the Pinia store, and fetches
Docker-backed status in the relevant views. The default first route is the
Dashboard, with Agents, Profiles, Skills, Prompt Templates, Docker Images,
Docker Resources, and Export exposed through Vue Router.

The previous framework-free entry point, `manager/frontend/src/app.mjs`, is no
longer part of startup. It remains in the tree as a migration reference until
the team decides every legacy workflow has been fully replaced.

## Docker API Flow

```text
browser -> manager WebUI/API -> docker-socket-proxy -> Docker daemon
```

The manager does not mount the Docker socket directly. It discovers the host
paths for `instances` and `bootstrap` by inspecting its own container mounts
through the Docker API, then uses those host paths when creating agent bind
mounts.

## Security Boundary

The WebUI binds to loopback. The socket proxy is reachable only on the internal
control network and exposes only the API sections needed for container
lifecycle, image pull/inspect, logs, and network management.

The proxy remains high privilege. Do not publish port `2375` to the host or LAN.
