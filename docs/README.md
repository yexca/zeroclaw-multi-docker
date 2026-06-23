# Documentation

This directory contains operator and maintainer notes for the ZeroClaw multi
Docker manager.

## Contents

- [WebUI Usage](webui-usage.md): day-to-day manager workflows, local files, and
  troubleshooting.
- [WebUI Architecture](webui-architecture.md): runtime flow, Docker API flow,
  and the manager security boundary.
- [Configuration Schema](config-schema.md): YAML layout for manager config,
  profiles, agents, secrets, and validation.
- [I18n And Theme](i18n-theme.md): frontend locale and theme conventions.
- [Docker Socket Proxy Security](docker-socket-proxy-security.md): socket proxy
  exposure model and operational notes.

## Conventions

- Keep documentation in English for broad compatibility.
- Keep local-only files out of Git; document committed examples instead.
- When adding WebUI fields, update the matching usage and schema notes in this
  directory.
