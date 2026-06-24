# ZeroClaw Multi Docker

用于在一个 Docker Compose 项目中，通过本地 WebUI 创建和管理多个
ZeroClaw Matrix agent。

管理器是默认入口。直接运行 `docker compose up -d` 只会启动 WebUI
管理器和 Docker socket proxy；agent 容器由 WebUI 通过 Docker API
创建、配置、启动、停止和删除。

管理器镜像会在 Docker 构建阶段编译前端，并由 Python 后端提供静态文件。
WebUI 会先加载配置编辑界面，再在后台刷新依赖 Docker 的 Dashboard 状态。

英文文档见 [README.md](README.md)。

## 包含内容

- `docker-compose.yml`: WebUI 管理器和 Docker socket proxy。
- `config/manager.example.yaml`: 结构化管理器配置示例。
- `config/secrets.example.yaml`: 本地明文密钥模板。
- `manager/`: WebUI 后端和前端。
- `bootstrap/render-config.sh`: 注入到管理器创建的 agent 容器中使用。
- `manager/backend/prompt_templates/`: workspace 初始提示词文件。
- `docs/`: 运维、参考、架构和开发文档。

## 启动

```powershell
Copy-Item config\manager.example.yaml config\manager.yaml
Copy-Item config\secrets.example.yaml config\secrets.yaml
docker compose up -d
```

打开 `http://127.0.0.1:7652`。

管理器只绑定 `127.0.0.1`，并通过 `docker-socket-proxy` 访问 Docker。
manager 容器不会直接挂载 `/var/run/docker.sock`。

## 配置 Agent

在 WebUI 中编辑：

- LLM profiles
- Vision LLM profiles
- Matrix profiles
- MCP profiles
- prompt templates
- 每个 agent 的端口、身份、模型/profile 选择、proactive 设置和环境变量

Dashboard 会显示运行状态、日志、配置哈希、是否需要重建以及操作历史。

详细文档：

- [文档索引](docs/README.md)
- [快速开始](docs/getting-started/quickstart.md)
- [WebUI 使用说明](docs/guides/webui-usage.md)
- [配置 schema](docs/reference/config-schema.md)
- [API 参考](docs/reference/api.md)
- [架构说明](docs/concepts/architecture.md)
- [Docker socket proxy 安全边界](docs/concepts/docker-socket-proxy-security.md)

## 镜像

管理器创建的 agent 默认使用：

```env
ZEROCLAW_IMAGE=ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian
```

可以通过 `ZEROCLAW_IMAGE` 环境变量、`config/manager.yaml` 或单个 agent
配置覆盖。

## 不要提交敏感信息

不要提交：

- `.env`
- `config/manager.yaml`
- `config/secrets.yaml`
- `config/manager.local.yaml`
- `config/secrets.local.yaml`
- `config/generated/*`
- `instances/*`

仓库中的 `.gitignore` 已覆盖这些路径。

## 测试和发布检查

运行完整本地发布检查：

```powershell
.\tools\release-checks.ps1
```

也可以单独运行：

```powershell
docker compose config --quiet
python -m unittest discover manager/backend/tests
node manager/frontend/tests/ui-foundation.test.mjs
```

Docker 镜像构建会在 `node:22-alpine` 阶段执行前端构建：

```powershell
docker build -t zeroclaw-manager:test ./manager
```
