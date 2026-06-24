# ZeroClaw Dockyard Documentation

This documentation is organized by user intent:

- **Getting started**: first-run paths for new operators.
- **Guides**: task-oriented operating instructions.
- **Concepts**: system design and security explanations.
- **Reference**: exact configuration and API details.
- **Development**: maintainer notes for changing the manager.

## New Operators

- [Quickstart](getting-started/quickstart.md): start the manager, open the
  WebUI, and create configuration there.
- [WebUI Usage](guides/webui-usage.md): daily workflows for agents, profiles,
  templates, exports, and troubleshooting.

## Operating The Manager

- [WebUI Usage](guides/webui-usage.md)
- [Configuration Schema](reference/config-schema.md)
- [API Reference](reference/api.md)

## Understanding The System

- [Architecture](concepts/architecture.md)
- [Docker Socket Proxy Security](concepts/docker-socket-proxy-security.md)

## Developing The Manager

- [Release Build](development/release-build.md)
- [I18n And Theme](development/i18n-theme.md)

## Documentation Conventions

- Keep documentation in English for broad compatibility.
- Prefer task pages for operator workflows and reference pages for exact field
  definitions.
- Keep local-only files out of Git; document committed examples instead.
- When adding WebUI fields, update both the usage guide and the matching
  reference page.
