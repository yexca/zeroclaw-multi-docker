# ZeroClaw Manager

This directory contains the WebUI manager skeleton. The current stage provides:

- a tiny Python backend with `/healthz` and `/api/status`;
- a static frontend placeholder served by the backend;
- a Dockerfile for the `manager` Compose service.

Later stages will add configuration validation, Docker API integration, agent
container lifecycle operations, and generated ZeroClaw config rendering.

The manager is intended to be reached only through the host loopback binding in
`docker-compose.yml`.
