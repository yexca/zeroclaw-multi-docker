# ZeroClaw Dockyard

ZeroClaw Dockyard 是一个本地 WebUI，用于在同一个 Docker Compose 项目
中创建和运行多个 ZeroClaw Matrix agent。

启动 Dockyard，打开 WebUI，就可以创建 agent、复用 profile、提示词模板
和运行时设置，不需要手写 YAML。

English documentation is available in [README.md](README.md).

## 你会得到什么

- 一个运行在 `http://127.0.0.1:7652` 的本地管理器 WebUI。
- 一个 Docker socket proxy，管理器不会直接挂载 `/var/run/docker.sock`。
- 用于编辑 agent、LLM profile、Vision LLM profile、Matrix profile、MCP
  profile、技能和提示词模板的 WebUI。
- Dashboard 中的启动、停止、重启、校验和日志查看等 agent 操作。
- 每个 agent 独立的工作区和生成的运行时配置。

Compose 默认只启动管理器和 socket proxy。Agent 容器稍后从 WebUI 中创建。

## 环境要求

- Docker Desktop 或 Docker Engine，并启用 Docker Compose。
- 本地浏览器可以访问 `127.0.0.1:7652`。
- 如果在 Windows 上使用下方命令，建议使用 PowerShell。

## 启动

```powershell
docker compose up -d
```

打开：

```text
http://127.0.0.1:7652
```

默认情况下，Compose 使用已发布的管理器镜像：

```text
yexca/zeroclaw-dockyard:v0.1.0
```

如果想从当前源码构建管理器：

```powershell
docker compose up -d --build
```

## 创建 Agent

在 WebUI 中：

1. 打开 **Profiles**，创建需要的 LLM、Vision、Matrix 或 MCP profile。
2. 打开 **Agents**，创建 agent，并设置 host port 和 profile 绑定。
3. 选择或编辑提示词模板。
4. 保存并校验 agent。
5. 从 Dashboard 或 agent 操作区启动 agent。

Dashboard 会显示运行状态、日志、配置哈希、是否需要重建，以及最近的管理器
操作记录。

## 本地数据

Dockyard 会把本地运行数据保存在项目目录中：

- `config/manager.yaml`：保存后的管理器配置。
- `config/secrets.yaml`：本地密钥文件，如果使用的话。
- `config/generated/`：生成的预览和导出文件。
- `instances/`：每个 agent 的工作区和运行时文件。
- `shared/`：共享技能包和支持文件。

这些文件属于本地 operator state。仓库自带的 `.gitignore` 已经配置好，
通常会让本地配置、密钥、生成文件和 agent 实例保持在 Git 之外。

## 默认 Agent 镜像

管理器创建的 agent 默认使用：

```env
ZEROCLAW_IMAGE=ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian
```

你可以通过 `ZEROCLAW_IMAGE` 环境变量、管理器配置，或 WebUI 中的单个
agent 设置来覆盖镜像。

## 停止

```powershell
docker compose down
```

这会停止管理器和 socket proxy。由管理器创建的 agent 容器仍然应从 WebUI
中控制。

## 文档

- [文档索引](docs/README.md)
- [快速开始](docs/getting-started/quickstart.md)
- [WebUI 使用说明](docs/guides/webui-usage.md)
- [配置 schema](docs/reference/config-schema.md)
- [API 参考](docs/reference/api.md)
- [架构说明](docs/concepts/architecture.md)
- [Docker socket proxy 安全说明](docs/concepts/docker-socket-proxy-security.md)
- [发布构建说明](docs/development/release-build.md)
