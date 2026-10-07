# Codex 服务器维护

## 发现服务后的更新规则

执行全局 npm 工具或整个开发环境的更新任务时，发现的 Codex 服务也属于本轮更新目标，不需要用户再次单独点名服务器。服务名称可能是 `codex-app-server.service`，也可能通过其他服务名、包装器或普通进程部署；按实际启动入口识别，不依赖固定名称。

- 先定位服务使用的真实安装与更新渠道；存在新版本时完成升级，而不是停在“检测到服务”或只更新当前 shell 的 CLI。
- 服务与当前全局 npm 共用安装时复用已完成的升级；使用其他 prefix、用户或安装渠道时，分别更新对应安装。重复服务共用同一份安装时只升级一次。
- 更新后核对服务实际入口及其原生组件版本，再检查运行进程是否仍需重启；需要重启不能成为跳过软件升级的理由。
- 用户只要求检查、明确排除服务器或限定其他包时保持该范围；未发现服务时不额外安装一个。权限、来源或升级失败需要明确报告，不能称已完成。

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

在更新任务中，对发现服务对应的安装添加 `--apply` 并执行；仅检查任务不添加。其他用户的安装遵循现有权限；权限不足就报告，不自动提权。若是独立二进制、容器镜像或其他部署渠道，依据该渠道的官方更新方式处理，不能覆盖成当前用户的 npm 安装。

npm 更新只替换磁盘文件，已有进程通常继续运行旧版本。分别记录：

- 对应入口的 `codex --version` 和目标版本；npm 安装还应核对平台原生包及附带 Code Mode host 的版本或分发归属，防止仅 JS 启动包更新而原生组件仍旧。发现不一致时按已确认的安装渠道修复并重新验证，不能把不一致当成成功。
- 服务原先是否 active、是否存在旧 Codex 子进程。
- Linux 中可执行时，用原生 Codex 子进程的 `/proc/PID/exe --version` 检查运行版本；路径标有 `(deleted)` 也是需要进一步核实的证据。权限或平台限制时明确标为未验证。

若主包已是目标版本而磁盘原生组件仍旧，按对应渠道重新安装已确认的目标分发；npm 安装可在服务对应的 Node 环境运行 `npm install --global @openai/codex@精确目标版本`，再核对组件。不能因 `npm outdated` 没有列出主包就跳过这类修复，也不能把仍在运行的旧进程误判为磁盘组件安装失败。

## 安全重启

只有已获授权、确认目标服务且不会中断当前会话时才重启。明确要求“重启 Codex 服务”可复用授权；单纯请求全局包升级不代表允许中断服务。若当前代理由该 app-server 承载，完成其他维护并给出人工或独立会话执行的具体重启命令，不自行停掉当前服务，也不安排后台定时重启。

允许重启时只操作发现的那一个服务；重启后核对 active 状态、新 PID、运行版本，以及部署已有的健康检查。未运行的服务不因软件升级而自动启动。重启或健康验证失败时报告事实，保留诊断证据；版本回退需要单独授权。

## 已核实的本机情况

2026-10-07 制作时，本机存在 `codex-app-server.service`，入口 `/usr/local/bin/codex` 是一个包装器，最终寻找 PATH 或 nvm 默认环境中的 Codex。此信息仅为部署示例，每次使用仍需重新发现；仓库不存储服务配置、环境值或认证数据。

来源：[OpenAI Codex App Server 文档](https://learn.chatgpt.com/docs/app-server)。
