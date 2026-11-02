# Pi Agent 插件更新

将 Pi 本体安装与 Pi 管理的插件作为 [维护清单](../SKILL.md#维护流程) 中不同对象跟踪：共享本体安装只升级一次，插件仍由 Pi 管理。Pi 本体的非 npm 安装按 [非 npm 工具指引](native-tools.md) 核实渠道，单独的插件请求不自动授权本体升级。

## 确认实际 Pi

```bash
command -v pi
pi --version
pi update --help
pi list --help
```

本机制作时核实的入口属于 `@earendil-works/pi-coding-agent@1.0.4`，支持 `pi update --extensions`；2026-10-31 复核本机已到 1.4.0，`pi update --help` 的 `--self/--extensions/--models/--all/--no-approve` 仍有效。环境可能还安装旧分发或 fork；以实际入口和该版本帮助为准，不自动切换到另一套 Pi，也不把 `omp` 当成同一个插件管理器。Pi 未安装时报告未覆盖，不为了更新插件而安装 Pi。

## 检查与更新范围

先查看插件声明和已安装版本；只要求检查时不执行更新。对于已核实支持这些参数的版本：

```bash
pi list --no-approve
```

`pi list` 显示配置的包，不证明它们已经最新。个人配置默认在 `~/.pi/agent/settings.json`；遵循 `PI_CODING_AGENT_DIR` 等现有路径配置，仅读取插件相关字段，不输出认证数据。

明确要求更新 Pi 插件，或执行未限定范围的完整开发环境更新时，运行：

```bash
pi update --extensions --no-approve
```

`--extensions` 只处理 Pi 管理的插件包；本机版本的裸 `pi update` 默认升级 Pi 本体，不能拿它代替插件更新。`--no-approve` 忽略项目配置，避免从当前仓库误更新项目插件；不擅自授予项目 trust，项目插件与 trust 按 [审批点](../SKILL.md#审批点必须显式提出) 单独批准；用户明确要求项目插件时，才切换到指定项目并使用该版本对应的项目作用域选项。

旧版本若不支持这些参数，先核实其官方文档中的等效插件更新方式，不盲目删掉参数重试。同一轮还升级 Pi 本体时，按下一节安排本体与插件的更新阶段。

## 当前执行器是 Pi 时

Pi 本体更新（包括全局 npm 和其他渠道）可能同时替换正在执行维护的 Pi 安装。已加载的模块通常仍在内存中，但后续动态导入、读取资源或 reload 可能访问已被替换的文件；磁盘安装成功不保证旧会话能无缝切换到新版本。`/reload` 刷新资源与扩展，不等于重新启动新版 Pi 本体。

1. 按实际 Pi 入口定位其安装渠道和包名。用 [入口的分批规则](../SKILL.md#更新前与执行顺序)先更新其他目标，把当前 Pi 本体留到最后一个维护阶段；未运行的其他 Pi 分发不必作为当前执行器延后。
2. Pi 本体更新前，保存已完成项目、当前版本、精确目标、剩余命令与日志路径。用不依赖旧 Pi 模块的 shell / 脚本执行这一阶段，并将安装、退出码和验证结果写入文件；npm 自身如待升级，也交给这一阶段在其他 npm 包之后处理。不把剩余关键维护留给更新后的旧 Pi 会话。
3. 沿用已确认的安装渠道更新本体；npm 安装复用快照中的 `npm_update.py --apply --package 实际包名`，其他渠道用其已核实的官方方法。随后启动新 CLI 子进程核对 `pi --version`、`pi update --help`、`pi list --help`，确认参数后更新并验证插件；没有插件更新授权时只做本体验证。
4. 当前旧 Pi 会话只收尾和报告，保留已加载的扩展，完整维护结束前不触发 `/reload`。注明“磁盘 Pi 已更新，当前会话仍使用旧进程”，由用户结束旧会话并重新启动 Pi；已核实支持 `--continue` 的版本可用 `pi --continue` 恢复。新进程验证前，不宣称当前会话已切换到新版本。

这一阶段按步骤失败即停，并保留日志和剩余命令。无法建立独立执行阶段时，明确报告 Pi 本体待更新并提供独立终端命令；不能强行结束当前会话或把延期项说成已更新。当前执行器不是 Pi 时，也应在 Pi 本体更新后用新 CLI 重新确认帮助，再更新插件。

## 插件目录的依赖与安装脚本

`pi update --extensions` 维护的是一份独立 npm 项目（本机为 `~/.pi/agent/npm`），有自己的 `package.json`、lock 和 `node_modules`；全局 npm prefix 的审计结论不覆盖它。

- 需要时单独审计：`cd ~/.pi/agent/npm && npm audit`。
- `npm audit fix` 可能因插件声明的 peer 区间滞后而 ERESOLVE 失败（本机：`pi-background-tasks@2.6.10` 声明 `@earendil-works/pi-coding-agent ^0.81–^0.84`，实际 Pi 已 1.4.0）。这属于审批点：不要自动追加 `--legacy-peer-deps` 或 `--force`；获批后才执行，执行前备份 `package.json` 与 `package-lock.json`，回滚用 `npm ci --legacy-peer-deps`。
- `npm install-scripts approve <pkg>` 会把允许项写进该 `package.json` 的 `allowScripts`；`pi update --extensions` 重写这个文件时可能丢失。每轮插件更新后复查 `npm install-scripts ls`，发现警告回归即为此原因。
- 这些依赖只影响插件运行时；验证仍以 `pi list --no-approve` 和重启后的真实加载为准。

## 固定版本与验证

- 保留 npm 固定版本和 Git ref；更新不能自行解除锁定或修改插件声明，其他更新路径也应遵守这些约束。新版本会将 Git checkout 对齐声明的 ref，旧版本可能直接跳过固定来源。
- 本地文件、目录和内置插件不等于可升级的远程包。`--extensions` 更新整个 Pi 包，包内还可能含 skills、主题或提示模板，不应声称只改了其中的扩展文件。
- 更新前记录版本或 Git commit；有本地改动时保留定制并报告冲突，不强制覆盖。来源不可访问、安装失败或跳过项要明确列出。
- 捕获更新日志和退出码，更新后再次运行 `pi list --no-approve`，核对实际安装版本或 commit；不能只凭插件仍出现在清单中就称升级成功。
- 磁盘更新不保证正在运行的 Pi 会话已加载新插件。仅插件或 skill 变化时，在完整维护结束后按该版本支持的 reload 方式或下一次启动加载；Pi 本体变化时重新启动，新会话再验证插件，不自行终止当前会话。

来源：[Pi 官方 CLI 文档](https://pi.dev/docs/latest/cli#update-pi-or-packages)、[Pi 官方包管理文档](https://pi.dev/docs/latest/packages)、[Pi 扩展生命周期](https://pi.dev/docs/latest/extensions#respect-the-runtime-lifecycle)。自更新阶段是本 skill 的维护策略；已核对本机 Pi 1.4.0 的 skill 按路径读取、动态导入及资源 reload 实现，不代表上游保证旧进程可无缝自更新。
