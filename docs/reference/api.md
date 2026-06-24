# Manager API Reference

The manager backend serves the WebUI and exposes JSON APIs under `/api`.
Successful API responses use:

```json
{ "ok": true, "data": {} }
```

Errors use:

```json
{ "ok": false, "error": { "code": "error_code", "message": "Message", "details": {} } }
```

## Health

- `GET /healthz`
- `GET /api/health`
- `GET /api/status`

## Configuration

- `GET /api/config`
- `PUT /api/config`
- `GET /api/config/validate`
- `POST /api/config/validate`
- `GET /api/webui/defaults`

## Profiles

- `GET /api/profiles/{llm|matrix|mcp}`
- `POST /api/profiles/{llm|matrix|mcp}`
- `PUT /api/profiles/{llm|matrix|mcp}/{id}`
- `DELETE /api/profiles/{llm|matrix|mcp}/{id}`

## Prompt Templates

- `GET /api/prompt-templates`
- `POST /api/prompt-templates`
- `POST /api/prompt-templates/ai-fill`
- `PUT /api/prompt-templates/{id}`
- `DELETE /api/prompt-templates/{id}`

`POST /api/prompt-templates/ai-fill` uses a configured LLM profile to generate
Markdown content for prompt template files. The request body includes
`llm_profile`, `instruction`, `description`, `files`, optional
`reference_files`, and optional `current_files`. The response returns
`files`, a mapping of generated file names to Markdown strings. The endpoint
does not save the prompt template; the WebUI applies the result to the draft and
operators save it explicitly.

## Skills

- `GET /api/skills/bundles`
- `POST /api/skills/bundles`
- `PUT /api/skills/bundles/{id}`
- `DELETE /api/skills/bundles/{id}`
- `GET /api/skills/bundles/{id}/skills`
- `POST /api/skills/bundles/{id}/skills`
- `GET /api/skills/bundles/{id}/skills/{name}`
- `PUT /api/skills/bundles/{id}/skills/{name}`
- `DELETE /api/skills/bundles/{id}/skills/{name}`
- `POST /api/skills/bundles/{id}/skills/{name}/files`
- `GET /api/skills/bundles/{id}/skills/{name}/files/{path}`
- `DELETE /api/skills/bundles/{id}/skills/{name}/files/{path}`

Skills use the canonical Agent Skills layout: one directory per skill, a
`SKILL.md` file with YAML frontmatter, and optional `scripts/`,
`references/`, and `assets/` subdirectories. Bundle directories must resolve
inside the project `shared/` directory. Deleting a skill archives it under
`shared/skills/_deleted/` unless `purge=true` is passed.

## Agents

- `GET /api/agents`
- `POST /api/agents`
- `GET /api/agents/{id}`
- `PUT /api/agents/{id}`
- `DELETE /api/agents/{id}`
- `GET /api/agents/{id}/skills`
- `POST /api/agents/{id}/validate`
- `POST /api/agents/{id}/apply-template`
- `POST /api/agents/{id}/sync-to-runtime`
- `POST /api/agents/{id}/sync-from-runtime`
- `POST /api/agents/{id}/reset-matrix-state`
- `POST /api/agents/{id}/export`
- `POST /api/agents/{id}/{start|stop|restart|delete}`
- `GET /api/agents/{id}/status`
- `GET /api/agents/{id}/logs`
- `GET /api/agents/{id}/logs/download`
- `GET /api/agents/{id}/env`
- `GET /api/agents/{id}/config-preview`

## Dashboard And History

- `GET /api/dashboard`
- `GET /api/history`

Dashboard status may call Docker through the socket proxy. The frontend loads
configuration first and refreshes dashboard status in the background or when
the Dashboard view is opened.

## Export

- `POST /api/export`

Exports omit secret values unless `include_secrets: true` is passed.
