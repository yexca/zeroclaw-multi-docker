# ZeroClaw Multi Docker

用于在一个 Docker Compose 项目中创建和管理多个 ZeroClaw Matrix agent 的本地 WebUI 管理器。

现在默认入口只有管理器。直接运行 `docker compose up -d` 只会启动 WebUI 和 Docker socket proxy；agent 容器完全由 WebUI 通过 Docker API 创建、配置、启动、停止和删除。

英文文档见 [README.md](README.md)。

## 包含内容

- `docker-compose.yml`: WebUI 管理器和 Docker socket proxy。
- `.env.example`: WebUI/proxy 启动参数的可选覆盖示例。
- `config/manager.example.yaml`: 管理器结构化配置示例。
- `config/secrets.example.yaml`: 本地明文密钥模板。
- `manager/`: WebUI 后端和前端。
- `bootstrap/render-config.sh`: 注入到 WebUI 创建的 agent 容器中使用。
- `templates/workspace/`: workspace 提示词文件模板。

## 启动

```powershell
Copy-Item config\manager.example.yaml config\manager.yaml
Copy-Item config\secrets.example.yaml config\secrets.yaml
docker compose up -d
```

打开 `http://127.0.0.1:7652`。

管理器只绑定 `127.0.0.1`，并通过 `docker-socket-proxy` 访问 Docker。manager 容器不会直接挂载 `/var/run/docker.sock`。

## 配置 Agent

在 WebUI 中编辑：

- LLM 配置
- Matrix 配置
- MCP 配置
- 提示词模板
- 每个 agent 的端口、身份、模型/配置引用和密钥

仪表盘会显示运行状态、日志、配置哈希、是否需要重建，以及操作历史。

详细文档：

- [WebUI 使用说明](docs/guides/webui-usage.md)
- [配置 schema](docs/reference/config-schema.md)
- [Docker socket proxy 安全边界](docs/concepts/docker-socket-proxy-security.md)
- [i18n 和主题](docs/development/i18n-theme.md)
- [架构说明](docs/concepts/architecture.md)

## 镜像

WebUI 创建的 agent 默认使用：

```env
ZEROCLAW_IMAGE=ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian
```

可以在 `.env`、`config/manager.yaml` 或单个 agent 配置中覆盖。

## 不要提交敏感信息

不要提交：

- `.env`
- `config/manager.yaml`
- `config/secrets.yaml`
- `config/manager.local.yaml`
- `config/secrets.local.yaml`
- `config/generated/*`
- `instances/*`

仓库内 `.gitignore` 已覆盖这些路径。

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
