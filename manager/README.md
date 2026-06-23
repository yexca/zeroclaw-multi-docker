# ZeroClaw Manager

This directory contains the WebUI manager. The current backend foundation
provides:

- a Python backend with `/healthz`, `/api/health`, `/api/status`, and the
  manager API under `/api`;
- a static frontend placeholder served by the backend;
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

Docker lifecycle APIs currently use a `FakeDockerController` with the same
method names and structured response shape that the real Docker API
implementation should keep. Later stages will replace the fake controller with
Docker socket proxy calls, generated ZeroClaw config rendering, and stronger
runtime validation.

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

The backend reads `MANAGER_CONFIG_PATH`, falling back to
`config/manager.yaml`, and uses `config/manager.example.yaml` as a read-only
bootstrap source when no local config exists. Writes are atomic and create the
local config file. `GENERATED_CONFIG_DIR` controls `/api/export` output.

Core endpoints:

- `GET /api/health`
- `GET /api/config`, `PUT /api/config`
- `GET|POST /api/profiles/{llm|matrix|mcp}`
- `PUT|DELETE /api/profiles/{llm|matrix|mcp}/{id}`
- `GET|POST /api/prompt-templates`
- `PUT|DELETE /api/prompt-templates/{id}`
- `GET|POST /api/agents`
- `GET|PUT|DELETE /api/agents/{id}`
- `POST /api/agents/{id}/validate`
- `POST /api/agents/{id}/{start|stop|restart}`
- `GET /api/agents/{id}/{status|logs}`
- `POST /api/export`

Successful API responses use `{ "ok": true, "data": ... }`. Errors use
`{ "ok": false, "error": { "code": "...", "message": "...", "details": {} } }`.
Request-body logging redacts keys, tokens, passwords, recovery keys, and other
secret-like fields.

Run the frontend foundation checks with:

```sh
node manager/frontend/tests/ui-foundation.test.mjs
```

Run backend tests with:

```sh
python -m unittest discover -s manager/backend/tests
```
