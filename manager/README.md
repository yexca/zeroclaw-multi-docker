# ZeroClaw Dockyard

This directory contains the WebUI manager. The current backend foundation
provides:

- a Python backend with `/healthz`, `/api/health`, `/api/status`, and the
  manager API under `/api`;
- a static frontend served by the backend;
- a Dockerfile for the `manager` Compose service.
- frontend foundations for locale loading, browser preference persistence, and
  light/dark/system theme application.
- configuration, profile/template, and agent CRUD over structured YAML files;
- validation, export, Docker control, status, and log API entry points.

The backend deliberately stays on Python's standard-library HTTP server plus
PyYAML instead of introducing a larger framework. The repository already used a
small Python backend with no build step, and this keeps the local-only manager
container lightweight while still providing a complete API shape for later
frontend and Docker integration phases.

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

## Frontend Foundation

The current frontend intentionally remains a static, framework-free browser
module app served by the Python manager. This keeps the phase-01 skeleton free
of a build step while still giving later phases shared utilities for UI text,
preferences, and theme state.

Internationalization uses structured JSON locale files under
`frontend/src/locales/`. English (`en`) is the default locale and Simplified
Chinese (`zh-CN`) is supported. All new user-facing WebUI text must use an i18n
key path, except literal technical values such as file names, protocols, model
IDs, provider IDs, and container names.

Theme support is implemented through CSS custom properties and the
`data-theme-mode` / `data-theme` attributes on `<html>`. Supported modes are
`light`, `dark`, and `system`; changing modes applies immediately without a page
reload. Browser-level language and theme preferences are persisted in
`localStorage`.

The backend exposes `/api/webui/defaults` so later configuration work can wire
manager defaults into the browser. Phase 02 should represent those defaults in
`config/manager.yaml` as:

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

Run backend tests with:

```sh
python -m unittest discover -s manager/backend/tests
```
