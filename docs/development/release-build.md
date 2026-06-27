# Release Build

The manager image builds the frontend inside Docker and serves the generated
static files from the Python backend.

## Docker Build Flow

`manager/Dockerfile` uses two stages:

1. `node:22-alpine` installs frontend dependencies with `npm ci` and runs
   `npm run build`.
2. `python:3.12-alpine` installs backend dependencies, copies backend code, and
   copies `manager/frontend/dist` from the build stage into `/app/frontend`.

The runtime image does not need Node.js.

## Frontend Build

Frontend source lives under `manager/frontend`.

```powershell
docker run --rm -v "${PWD}/manager/frontend:/work" -w /work node:22-alpine npm ci
docker run --rm -v "${PWD}/manager/frontend:/work" -w /work node:22-alpine npm run build
```

The build writes:

- `manager/frontend/dist/index.html`
- `manager/frontend/dist/assets/index-[hash].js`
- `manager/frontend/dist/assets/index-[hash].css`
- additional hashed chunks under `manager/frontend/dist/assets/` when Vite
  splits the bundle

`dist` and `node_modules` are ignored by Git.

## Static Caching

The backend serves:

- `index.html` with `Cache-Control: no-cache`
- hashed assets under `/assets/` with long immutable caching
- other static files with a short cache lifetime

## Release Checks

Run:

```powershell
.\tools\release-checks.ps1
docker build -t yexca/zeroclaw-dockyard:test ./manager
```

The release check validates Compose config, backend tests, frontend syntax,
locale JSON, and frontend foundation tests.

## Published Images

The release workflow publishes Docker images when a tag matching `v*.*.*` is
pushed. For example, tag `v0.1.2` publishes:

- `ghcr.io/yexca/zeroclaw-dockyard:v0.1.2`
- `ghcr.io/yexca/zeroclaw-dockyard:latest`
- `yexca/zeroclaw-dockyard:v0.1.2`
- `yexca/zeroclaw-dockyard:latest`

GitHub Container Registry uses the repository `GITHUB_TOKEN`. Docker Hub uses
the repository secret `DOCKERHUB_TOKEN` with username `yexca`.
