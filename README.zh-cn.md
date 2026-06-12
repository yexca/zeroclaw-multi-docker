# ZeroClaw Multi Docker

用于在一台主机上运行多个 ZeroClaw Matrix agent 的 Docker Compose 模板。

本项目面向 ZeroClaw `0.8.0-beta-2`，提供可复现的容器配置：Matrix channel、多 agent 独立 workspace、可选视觉模型路由、可选 MCP gateway，以及可选 proactive 唤醒 sidecar。

英文文档见 [README.md](README.md)。

## 包含内容

- `docker-compose.yml`: 默认包含 `agent1`、`agent2`、`agent3` 三个示例 agent，以及可选 proactive sidecar。
- `.env.example`: 模型、Matrix 账号、MCP、proactive 唤醒相关的公开占位配置。
- `bootstrap/render-config.sh`: 在容器启动时渲染 ZeroClaw schema v3 `config.toml`。
- `proactive/proactive.py`: 可选 sidecar，定时向每个 agent gateway POST 唤醒 prompt。
- `tools/add-agent.ps1`: 用于添加更多 agent service 的 PowerShell 辅助脚本。
- `templates/workspace/`: 每个 agent workspace 的空白指令和记忆模板。
- `patches/zeroclaw-0.8.0-beta2-docker-matrix.patch`: 用于构建下文 Matrix 版 Docker 镜像的补丁。

## 构建镜像

上游版本是 `0.8.0-beta-2`。本仓库补丁基于 ZeroClaw 提交 `af50475a37fa9d2ae78758d2fbe82bda67218c17` 生成，该提交的 Cargo package 版本仍是 `0.8.0-beta-2`。

```powershell
git clone https://github.com/zeroclaw-labs/zeroclaw.git
cd zeroclaw
git checkout af50475a37fa9d2ae78758d2fbe82bda67218c17
git apply ..\zeroclaw_multi_docker\patches\zeroclaw-0.8.0-beta2-docker-matrix.patch
docker build -f Dockerfile.debian -t zeroclaw:0.8.0-beta2-matrix .
```

也可以使用 `Dockerfile` 构建：

```powershell
docker build -f Dockerfile -t zeroclaw:0.8.0-beta2-matrix .
```

## 补丁概要

该补丁会：

- 在 Docker 构建中启用 `channel-matrix` Cargo feature。
- 为 Docker 依赖预取层补齐缺失的 workspace 文件。
- 在解析 channel runtime model provider 前应用环境变量覆盖。
- 让 `interrupt_on_new_message` 检查所有 channel alias，而不是只检查 `default`。
- 让多模态 vision fallback 通过配置里的 dotted alias 创建 provider，例如 `custom.vision`。

## 配置

```powershell
cd zeroclaw_multi_docker
Copy-Item .env.example .env
```

编辑 `.env`，至少填写：

- `DEEPSEEK_API_KEY`，或把文本模型 provider 配置替换成你自己的。
- `VISION_API_KEY`，如果需要 Matrix 图片消息路由到视觉模型。
- `MATRIX_HOMESERVER`
- `AGENT*_MATRIX_USER_ID`
- `AGENT*_MATRIX_PASSWORD` 或 `AGENT*_MATRIX_ACCESS_TOKEN`
- `AGENT*_MATRIX_RECOVERY_KEY`，如果使用 Matrix E2EE。
- `AGENT*_MATRIX_EXTERNAL_PEERS`，包含允许发消息给 agent 的用户 MXID，以及出站房间目标。

初始化 workspace 文件：

```powershell
New-Item -ItemType Directory -Force instances\agent1\workspace,instances\agent2\workspace,instances\agent3\workspace
Copy-Item templates\workspace\* instances\agent1\workspace\
Copy-Item templates\workspace\* instances\agent2\workspace\
Copy-Item templates\workspace\* instances\agent3\workspace\
```

## 运行

```powershell
docker compose up -d agent1 agent2 agent3
```

默认 gateway 端口只绑定 localhost：

- agent1: `http://127.0.0.1:42641`
- agent2: `http://127.0.0.1:42642`
- agent3: `http://127.0.0.1:42643`

## 添加更多 agent

```powershell
.\tools\add-agent.ps1 -Id 4 -HostPort 42644
```

脚本会创建 `instances/agent4/workspace`，向 `.env` 追加空的 `AGENT4_*` 变量，向 `docker-compose.yml` 插入 `agent4` service，并把该 service 加入 proactive sidecar 依赖。

## Proactive sidecar

sidecar 默认关闭。启用时设置：

```dotenv
PROACTIVE_ENABLED=true
PROACTIVE_TARGETS=agent1=#agent1-room:matrix.example.com,agent2=#agent2-room:matrix.example.com,agent3=#agent3-room:matrix.example.com
```

然后启动：

```powershell
docker compose up -d proactive
```

sidecar 会以随机间隔向每个已配置 agent 的 `/webhook` 发送唤醒请求。是否发送 Matrix 出站消息由 agent 自己决定。

## 不要提交敏感信息

不要提交：

- `.env`
- `instances/*/.zeroclaw/`
- `instances/*/data/`
- `instances/*/workspace/sessions/`
- SQLite 数据库、Matrix crypto store、日志、备份、生成媒体文件，以及本地 workspace 文件
- `proactive/state/`

仓库内 `.gitignore` 已覆盖这些路径。发布前建议运行：

```powershell
rg -n "api[_-]?key|token|password|recovery|secret|PRIVATE KEY|Bearer " .
```
