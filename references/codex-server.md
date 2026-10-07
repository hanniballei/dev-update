# Codex 服务器维护

## 确定实际安装

`codex app-server` 是 Codex 的子命令，不应凭名称去安装未知的 `codex-server` npm 包。先确定服务入口、运行进程、实际二进制及所属 Node 安装。全局 npm 的 prefix 只代表当前命令所用的一份安装。

```bash
type -a codex
command -v npm
npm prefix -g
codex --version
```

Linux/systemd 环境检查系统服务，也检查运行该服务的用户级服务：

```bash
systemctl list-unit-files --type=service --no-legend | rg -i codex
systemctl --user list-unit-files --type=service --no-legend | rg -i codex
```

对发现的具体服务读取 `FragmentPath`、`MainPID`、`ActiveState`、`User`。若没有 systemd，则按实际部署方式检查已有 PM2、容器或普通进程；不启动新守护进程来发现服务。未安装的管理器、不支持的用户总线与真实查询失败需分别报告。

检查服务单元和启动包装器时仅提取可执行文件路径和 Node 选择逻辑；不要输出 `Environment`、认证配置或完整进程参数。使用 `ps -eo pid,ppid,comm` 查找服务的 Codex 子进程，再用 `readlink /proc/PID/exe` 查看真实文件。`MainPID` 可能只是 Node 包装器，并非 Codex 原生进程。

对于 shell 函数、别名和包装脚本，追踪至真实入口；对于 nvm、多用户或多 prefix，确认服务的用户、Node 与 npm 路径。不能把“当前 npm 中 Codex 已最新”当成“服务器已最新”。

## 更新与运行版本

如果实际入口属于 `@openai/codex`，用对应的 Node 环境检查。示例中的路径来自发现结果，不硬编码服务器目录：

```bash
PATH="/path/to/node/bin:$PATH" python3 /path/to/dev-update/scripts/npm_update.py \
  --npm /path/to/node/bin/npm --package @openai/codex
```

已有更新授权时添加 `--apply`。其他用户的安装遵循现有权限；权限不足就报告，不自动提权。若是独立二进制、容器镜像或其他部署渠道，依据该渠道的官方更新方式处理，不能覆盖成当前用户的 npm 安装。

npm 更新只替换磁盘文件，已有进程通常继续运行旧版本。分别记录：

- 对应入口的 `codex --version` 和目标版本。
- 服务原先是否 active、是否存在旧 Codex 子进程。
- Linux 中可执行时，用原生 Codex 子进程的 `/proc/PID/exe --version` 检查运行版本；路径标有 `(deleted)` 也是需要进一步核实的证据。权限或平台限制时明确标为未验证。

## 安全重启

只有已获授权、确认目标服务且不会中断当前会话时才重启。明确要求“重启 Codex 服务”可复用授权；单纯请求全局包升级不代表允许中断服务。若当前代理由该 app-server 承载，完成其他维护并给出人工或独立会话执行的具体重启命令，不自行停掉当前服务，也不安排后台定时重启。

允许重启时只操作发现的那一个服务；重启后核对 active 状态、新 PID、运行版本，以及部署已有的健康检查。未运行的服务不因软件升级而自动启动。重启或健康验证失败时报告事实，保留诊断证据；版本回退需要单独授权。

## 已核实的本机情况

2026-10-07 制作时，本机存在 `codex-app-server.service`，入口 `/usr/local/bin/codex` 是一个包装器，最终寻找 PATH 或 nvm 默认环境中的 Codex。此信息仅为部署示例，每次使用仍需重新发现；仓库不存储服务配置、环境值或认证数据。

来源：[OpenAI Codex App Server 文档](https://learn.chatgpt.com/docs/app-server)。
