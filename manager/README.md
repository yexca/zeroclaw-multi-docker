# ZeroClaw Dockyard

This directory contains the WebUI manager. The current backend foundation
provides:

- a Python backend with `/healthz`, `/api/health`, `/api/status`, and the
  manager API under `/api`;
- a Vue 3 frontend built with Vite and served as static files by the backend;
- a Dockerfile for the `manager` Compose service.
- frontend foundations for browser preference persistence and light/dark/system
  theme application.
- configuration, profile/template, and agent CRUD over structured YAML files;
- validation, export, Docker control, status, and log API entry points.

The backend deliberately stays on Python's standard-library HTTP server plus
PyYAML instead of introducing a larger framework. The manager frontend now has
a Node/Vite build step, but the runtime container still serves only static files
and does not need Node.js.

Docker lifecycle APIs use the Docker socket proxy URL from `DOCKER_API_URL`.
They create manager-owned agent containers with stable names, labels, volume or
bind storage, loopback gateway port publishing, extra hosts, and the configured
runtime network. Set `DOCKER_CONTROLLER=fake` only for tests or local UI-only
development.

Agent runtime rendering is centralized in `backend/agent_renderer.py`. The
same resolver is used for Docker container environment variables, workspace
template application, env exports, and ZeroClaw `config.toml` previews. The
existing `/bootstrap/render-config.sh` remains the runtime source of truth
inside agent containers.

Validation and safety checks live in `backend/config_validator.py`. Startup is
blocked when required agent settings are missing, while validation endpoints
return all practical issues at once for the WebUI to display.

The manager is intended to be reached only through the host loopback binding in
`docker-compose.yml`.

## Frontend

The current frontend is a Vue 3 application under `frontend/`, using Vite,
Pinia, Vue Router, and a small local component system. The active entry points
are:

- `frontend/src/main.js`
- `frontend/src/App.vue`
- `frontend/src/router/index.js`
- `frontend/src/stores/manager.js`

The backend serves the built `frontend/dist` directory. During local frontend
work, run Vite from `manager/frontend`; its dev server proxies `/api` and
`/healthz` to the Python manager on `127.0.0.1:7652`.

```sh
cd manager/frontend
npm ci
npm run dev -- --port 7653
```

The checked-in dependency set requires Node `^20.19.0 || >=22.12.0` because of
Vite and `@vitejs/plugin-vue`. The Dockerfile and recommended verification path
use `node:22-alpine`:

```sh
docker run --rm -v "${PWD}:/work" -w /work/manager/frontend node:22-alpine sh -lc "npm ci && npm run build"
```

The old framework-free module at `frontend/src/app.mjs` and the old
`frontend/build.mjs` esbuild helper are retained only as migration references.
Do not use either as the current app or build entry point. Remove them only
after the Vue implementation has fully replaced every legacy workflow.

Internationalization is mid-migration. The legacy structured JSON locale files
remain under `frontend/src/locales/`, with English (`en`) as the default locale
and Simplified Chinese (`zh-CN`) available. The current Vue views still contain
hard-coded English labels in many places; future Vue i18n work should connect a
small composable or store to these files before expanding locale coverage.

Theme support is implemented through CSS custom properties and the
`data-theme-mode` / `data-theme` attributes on `<html>`. Supported modes are
`light`, `dark`, and `system`; changing modes applies immediately without a page
reload. Browser-level language and theme preferences are persisted in
`localStorage`.

The backend exposes `/api/webui/defaults`, backed by manager configuration:

```yaml
webui:
  default_language: en
  default_theme: system
```

The endpoint now reads those values from the loaded manager configuration,
falling back to `en` and `system` through backend defaults.

## Backend API

The backend reads `MANAGER_CONFIG_PATH`, falling back to `config/manager.yaml`,
and uses `config/manager.example.yaml` as a read-only bootstrap source when no
local config exists. Writes are atomic and create the local config file.
`GENERATED_CONFIG_DIR` controls `/api/export` output. Docker bind mounts need
host paths, so the manager uses `HOST_PROJECT_DIR` by default and can be
overridden with `paths.host_project_dir`, `paths.host_instances_dir`, or
`paths.host_bootstrap_dir`.

Core endpoints:

- `GET /api/health`
- `GET /api/config`, `PUT /api/config`
- `GET|POST /api/config/validate`
- `GET|POST /api/profiles/{llm|matrix|mcp}`
- `PUT|DELETE /api/profiles/{llm|matrix|mcp}/{id}`
- `GET|POST /api/prompt-templates`
- `PUT|DELETE /api/prompt-templates/{id}`
- `GET|POST /api/agents`
- `GET|PUT|DELETE /api/agents/{id}`
- `POST /api/agents/{id}/validate`
- `POST /api/agents/{id}/apply-template`
- `GET /api/agents/{id}/env`
- `GET /api/agents/{id}/config-preview`
- `POST /api/agents/{id}/export`
- `POST /api/agents/{id}/{start|stop|restart}`
- `POST /api/agents/{id}/delete`
- `GET /api/agents/{id}/{status|logs}`
- `POST /api/export`

Successful API responses use `{ "ok": true, "data": ... }`. Errors use
`{ "ok": false, "error": { "code": "...", "message": "...", "details": {} } }`.
Request-body logging redacts keys, tokens, passwords, recovery keys, and other
secret-like fields.

Workspace template application supports `keep`, `missing`, `overwrite`, and
`merge` modes. Creating an agent attempts to initialize the selected template
without overwriting existing files; explicit WebUI calls can choose a different
mode.

Exports omit secret values by default. Passing `include_secrets: true` to
`POST /api/export` is required for a full local backup. Deleting an agent
configuration keeps its instance directory by default; pass
`delete_instance_dir: true` only when the workspace and runtime data should be
removed too.

Run the frontend foundation checks with:

```sh
node manager/frontend/tests/ui-foundation.test.mjs
```

Run the Vue production build with Node 22:

```sh
docker run --rm -v "${PWD}:/work" -w /work/manager/frontend node:22-alpine sh -lc "npm ci >/tmp/npm.log && npm run build"
```

Run backend tests with:

```sh
python -m unittest discover -s manager/backend/tests
```
