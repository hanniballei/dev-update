# Codex 服务器维护

本分支在 [统一维护流程](../SKILL.md#维护流程) 的清单中跟踪 CLI 安装、托管包和运行服务；非 npm 安装的渠道核实复用 [非 npm 工具指引](native-tools.md)。服务对应安装与普通工具共用时只更新一次，各运行进程仍分别验证。

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

## Codex 托管的 daemon 包

全局 npm 更新也包含发现的 Codex 托管 daemon，但它可能使用独立于 npm prefix 的包；`npm update -g` 或仅重启进程不能保证这份包已更新。在软件升级前识别部署方式，并在升级 CLI 后重新核对：

1. 用实际 CLI 的 `codex app-server --help`、`codex app-server daemon --help` 确认命令能力；支持时运行 `codex app-server daemon version`。记录 `cliVersion`、`managedCodexPath`、`managedCodexVersion`、`appServerVersion` 和连接目标。字段缺失或查询失败时保留未验证状态，用实际入口与进程继续确认。
2. 将托管路径与服务入口、运行进程及服务所属用户核对。路径字段存在不代表托管包已安装，`managedCodexVersion` 为 null 也不能单独证明部署方式。手工 systemd 服务仍按其实际安装渠道更新；服务管理器名称本身不能区分是否使用 Codex 托管包。
3. 已确认使用 Codex 托管包时，单独比较托管包与本轮目标版本。CLI 已更新而托管包仍旧时，先核实 `codex app-server daemon update --help`。本机 Codex 0.161.0 帮助确认 `--from-cli` 会复制并固定当前 CLI 包，可用于将 daemon 对齐到本轮已升级、已验证的 CLI：

```bash
codex app-server daemon update --from-cli
```

在该服务所属用户及相同的 `CODEX_HOME`、连接配置下，从已核实的 CLI 入口执行；不要把维护者的默认 daemon 当成目标服务。保留用户指定的版本或渠道，托管包比当前 CLI 新时不自动用 `--from-cli` 降级。命令不支持时按实际版本及部署渠道处理，并明确报告未完成项。

该命令可能中断正在运行的任务，执行前适用下方“安全重启”的授权与会话独立性条件；已有明确的 daemon 更新及中断授权直接复用。只有 npm 升级授权或当前会话依赖目标 daemon 时，先完成可独立执行的 CLI 更新，报告“托管包待更新”及独立执行命令，不能只写“待重启”。仅检查任务不运行此命令，也不通过 `bootstrap` 或 `start` 创建服务。更新失败时保留错误，不用重装 npm 或反复重启代替修复。

执行后重新查询版本，并核对实际进程和已有健康检查：CLI 与托管包应符合本轮目标，运行中的 app-server 应匹配目标包。包已对齐但进程仍旧时，再按实际管理方式执行已授权的重启；已达到目标则无需额外重启。原先未运行的服务不主动启动，运行版本记为未运行。最终分别报告 CLI、托管包（不适用时注明）、运行版本和连接验证；版本字段相同不能代替用户可见连接验证。

## 更新与运行版本

如果实际入口属于 `@openai/codex`，用对应的 Node 环境检查。示例中的路径来自发现结果，不硬编码服务器目录：

```bash
PATH="/path/to/node/bin:$PATH" python3 /path/to/dev-update/scripts/npm_update.py \
  --npm /path/to/node/bin/npm --package @openai/codex
```

在更新任务中，对发现服务对应的安装添加 `--apply` 并执行；仅检查任务不添加。其他用户的安装遵循现有权限；权限不足就报告，不自动提权。若是独立二进制、容器镜像或其他部署渠道，按 [非 npm 工具指引](native-tools.md#核实能力与选择渠道) 核实并使用原渠道；更新方法未核实时保留待处理项，不能覆盖成当前用户的 npm 安装。

npm 更新只替换磁盘文件，已有进程通常继续运行旧版本。分别记录：

- 对应入口的 `codex --version` 和目标版本；npm 安装还应核对平台原生包及附带 Code Mode host 的版本或分发归属，防止仅 JS 启动包更新而原生组件仍旧。发现不一致时按已确认的安装渠道修复并重新验证，不能把不一致当成成功。
- 服务原先是否 active、是否存在旧 Codex 子进程。
- Linux 中可执行时，用原生 Codex 子进程的 `/proc/PID/exe --version` 检查运行版本；路径标有 `(deleted)` 也是需要进一步核实的证据。权限或平台限制时明确标为未验证。

若主包已是目标版本而磁盘原生组件仍旧，按对应渠道重新安装已确认的目标分发；npm 安装可在服务对应的 Node 环境运行 `npm install --global @openai/codex@精确目标版本`，再核对组件。不能因 `npm outdated` 没有列出主包就跳过这类修复，也不能把仍在运行的旧进程误判为磁盘组件安装失败。

## 安全重启

先根据进程归属和启动方式判断当前维护会话是否依赖目标服务。独立 SSH / tmux 中的 Pi 可继续执行该服务重启后的验证；从目标 Codex 会话启动的 Pi 子进程仍可能随服务停止而中断。关系无法确认时，保留当前会话并给出独立执行命令。

升级后先查看实际 CLI 的 `codex app-server --help`。仅在提供 `daemon` 及其 `version` 子命令时使用下面的查询；子命令不存在时，复用前述服务 PID、实际入口和 `/proc/PID/exe --version`，其他平台使用部署已有的运行版本接口。支持命令但查询失败时保留错误并继续核对进程，不把查询失败当成服务未运行，也不启动新 daemon 来完成检查。

```bash
codex app-server daemon version
```

本机已核实版本中，`cliVersion` 是磁盘 CLI，`appServerVersion` 是查询所连接服务的运行版本。将查询指向的服务或 socket 与发现的部署核对；另有服务安装时，不能用默认 daemon 的结果代替其运行版本。

只有已获授权、确认目标服务且不会中断维护会话时才重启。已有明确的重启授权就直接复用，不再请求一次确认；单纯的全局包升级授权不包括中断服务。运行版本落后且可以安全重启、但缺少授权时，再按 [审批点](../SKILL.md#审批点必须显式提出) 请求这一具体服务的重启决定，并说明受影响会话。用户不同意、会话依赖该服务或关系不明时，完成其他已授权维护，报告待重启状态及独立执行命令；不自行停止当前服务或安排后台定时重启。

允许重启时只操作发现的那一个服务；重启后核对 active 状态、新 PID、运行版本，以及部署已有的健康检查。未运行的服务不因软件升级而自动启动。重启或健康验证失败时报告事实，保留诊断证据；版本回退需要单独授权。

## 重启卡死与僵尸 socket

`systemctl restart` 返回 0 不代表服务已切到新二进制。重启后先等十几秒再读状态，按下面顺序判断：

1. `systemctl is-active` 仍为 `activating`、`MainPID` 为 0、`NRestarts` 持续增大，即启动失败循环。
2. `journalctl -u <unit> -n 40` 出现 `Error: app-server control socket is already in use at …`，说明旧进程没真正停下来，仍占着 control socket。本机实测：`TimeoutStopSec=20` 停止超时后留下一个 PPID=1 的孤儿 app-server，随后 9 次启动全部因此失败。

处置顺序（每步可独立执行）：

```bash
systemctl stop <unit>                                # 先停掉重启循环
ps -eo pid,ppid,cmd | grep 'app-server --listen'     # 找占 socket 的进程，PPID=1 多为孤儿
kill -TERM <pid>; sleep 8; kill -0 <pid> && kill -9 <pid>
ls -l "$CODEX_HOME/app-server-control/app-server-control.sock"   # 随进程退出应消失
systemctl start <unit>
```

不要用 `daemon restart`（非托管部署会直接报不支持），不要删除整个 `app-server-control` 目录，也不要在 socket 仍被占用时反复 start。

加固：备份 unit 后调大停止超时并清理 socket，再 `systemctl daemon-reload` 并重启验证一次（本机已核实可行）：

```ini
TimeoutStopSec=40
KillMode=mixed
ExecStopPost=-/bin/rm -f /root/.codex/app-server-control/app-server-control.sock
```

通过标准：`Result=success`、`NRestarts=0`、`MainPID` 非 0、socket 符号链接重新出现，且 `codex app-server daemon version` 的 `cliVersion` 与 `appServerVersion` 一致。

## 未重启时的用户可见后果

报告实际观察到的兼容异常。以下是本机 Codex 0.161.0 的已核实案例，其他版本按实际帮助、部署方式和 TUI 输出判断；尚未验证时标为可能出现，不能声称已经观察到。

该版本 TUI 会向后台 server 请求 `experimentalFeature/list`（请求标记 `tui-daemon-features`）并比对特性设置；不一致时可能出现：

```text
Background server has incompatible feature settings
  Run without daemon this time / Restart with these settings
```

本机由 systemd 手工托管的服务（`managedCodexVersion` 为 null、`$CODEX_HOME/app-server-daemon/settings.json` 缺失）还提示“This server is not managed by Codex. Restart cannot resolve this compatibility check.”，内置重启选项不可用。旧服务也可能报“The local Codex service cannot check background terminals”。这些字段和提示是部署证据，不是所有版本判断托管方式的固定规则。

这种情况下的报告要包含提示文案、经当前 CLI 帮助核实的临时运行方式，以及实际服务管理器的独立重启命令。本机该版本可临时使用 `codex --no-daemon`；其他版本先确认支持。分别报告“磁盘已更新”“运行版本待重启”“连接验证通过或未验证”。

重启后同一提示仍出现时，先重新核对实际运行版本；版本一致仍报错，再检查客户端与服务的特性设置及实际连接目标。2026-10-07 在 0.161.0 手工托管 daemon 上实测：提示直接列出要求共享的设置，并附“This session requires <feature> to be enabled”；`Restart with these settings` 因服务不由 Codex 托管而置灰。

按该版本支持的特性、实际提示、共享配置及服务命令行覆盖项核对差异；在已授权的设置范围内备份并修复配置，然后按重启条件再次验证真实 TUI。保留用户选择的特性，不把本机案例中的开关和值复制成通用默认配置，也不靠删除特性开关隐藏异常。

## 验证用户可见行为

`codex features list`、`codex doctor` 的配置和版本检查不能证明 TUI 不再弹提示。验证这类提示时，在 tmux 或伪终端里真实启动一次使用同一服务和配置的 TUI，等待连接结果并检查已观察的提示文案。无法执行时明确标为连接未验证。下面是本机验证示例，测试会话使用唯一名称，结束时只关闭本次新建的会话：

```bash
check_session="codexcheck-$(date +%s)-$$"
tmux new-session -d -s "$check_session" -x 110 -y 34
tmux send-keys -t "$check_session" 'cd <信任目录> && TERM=xterm-256color codex' Enter
sleep 25
tmux capture-pane -p -t "$check_session" -S -400
tmux kill-session -t "$check_session"
```

在受信任目录启动可避免文件夹信任提示；不得用这种方式发送对话或启动新任务。

## 已核实的本机情况

2026-10-07 制作时，本机存在 `codex-app-server.service`，入口 `/usr/local/bin/codex` 是一个包装器，最终寻找 PATH 或 nvm 默认环境中的 Codex。此信息仅为部署示例，每次使用仍需重新发现；仓库不存储服务配置、环境值或认证数据。

2026-10-07 复核该本机时，npm 升级 `@openai/codex` 0.160.1 → 0.161.0 后，`codex app-server daemon version` 返回 `cliVersion 0.161.0 / appServerVersion 0.160.1 / managedCodexVersion null`，运行进程的原生二进制指向已被 npm 替换的 `(deleted)` 路径，0.161 的 TUI 因此弹出上一节的 daemon 兼容提示；`systemctl restart codex-app-server.service` 后两者一致（`codex doctor` 的 Background Server 段也变为新版本）。重启后提示仍出现，按 client 列出的共享设置补齐 `/root/.codex/config.toml` 的 `[features]`（配置已备份），再次重启服务后真 TUI 启动不再提示。

来源：[OpenAI Codex App Server 文档](https://learn.chatgpt.com/docs/app-server)。
