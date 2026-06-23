# Docker Socket Proxy Security

The manager never mounts `/var/run/docker.sock` directly. Docker control flows
through `tecnativa/docker-socket-proxy` on the internal `manager-control`
network.

```text
browser -> manager -> docker-socket-proxy -> Docker daemon
```

## Enabled API Areas

- `PING=1`, `VERSION=1`: health and compatibility checks.
- `CONTAINERS=1`: list, inspect, create, delete, and read logs for managed
  containers.
- `ALLOW_START=1`, `ALLOW_STOP=1`, `ALLOW_RESTARTS=1`: lifecycle operations.
- `IMAGES=1`: inspect and pull the ZeroClaw image.
- `NETWORKS=1`: create or inspect the runtime network.
- `POST=1`: required for Docker write operations such as create/start/stop.

## Disabled API Areas

The proxy explicitly disables unrelated sections including `EXEC`, `SYSTEM`,
`VOLUMES`, `SWARM`, `SERVICES`, `SECRETS`, `BUILD`, and `AUTH`.

`ALLOW_RESTARTS=1` also permits Docker's `kill` endpoint in the upstream proxy
configuration. Manager code must not call `kill` unless a later safety review
adds that behavior deliberately.

## Boundary

The proxy is still high privilege. Any container that can reach it can perform
the enabled Docker operations against the host daemon. The internal network and
API section allowlist reduce exposure, but they do not make Docker control
low-risk.

Do not publish proxy port `2375` to the host or a LAN.
