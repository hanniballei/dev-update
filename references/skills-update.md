# 全局 Skills 更新

## 本 skill 的自更新

Skill 是指引、脚本和参考文件，不是常驻服务。更新 `SKILL.md` 不会自动替换当前会话已加载的指令，但后续按原路径读取参考文件或再次运行脚本，可能混用新旧版本；只把 `SKILL.md` 读入上下文不足以保护整轮维护。

如果本轮管理器可能覆盖正在使用的 `dev-update`，在首次写入前保存本 skill 的执行快照。将下面路径替换为实际 skill 目录；复制时展开符号链接，避免快照仍指向即将被替换的安装：

```bash
skill_dir="$(realpath /path/to/dev-update)"
run_dir="$(mktemp -d "${TMPDIR:-/tmp}/dev-update-run.XXXXXX")"
mkdir "$run_dir/dev-update"
cp -aL -- "$skill_dir/SKILL.md" "$skill_dir/scripts" "$skill_dir/references" "$run_dir/dev-update/"
python3 "$run_dir/dev-update/scripts/npm_update.py"
```

记录快照路径，并把本轮剩余参考读取和脚本调用的基目录统一改为 `$run_dir/dev-update`，包括自更新后的版本核对。快照建立失败时，先解决失败再更新本 skill；快照不代替其他技能的本地修改备份，也不包含认证配置。

本轮继续遵循已加载的流程，更新后的指引用于下一轮。执行过程中不重新调用新版 `dev-update` 或触发资源 reload 来替换当前流程；结束时报告本 skill 是否变化并保留快照供检查。仅更新 skill 时，Pi 可在任务结束后按其版本支持的方式刷新资源；Pi 本体也被更新时按 [Pi 自更新指引](pi-extensions.md#当前执行器是-pi-时)重新启动。

## 版本语义先行

用户指定的 `npx skills check -g` 应保留，但不能假定它永远只读。2026-10-07 核实的 `skills@1.7.1` 将 `check`、`update` 和 `upgrade` 全部路由到 `runUpdate`；旧版本可能把 `check` 作为纯检查。

先解析当前 CLI 版本：

```bash
npx --yes skills@latest --version
```

后续用该输出的具体版本替换下面的 `VERSION`，在同一轮维护中固定版本。`npx` 的下载缓存写入不同于升级全局 skills；可关闭遥测时使用官方支持的 `DISABLE_TELEMETRY=1`。

## 仅检查

```bash
npx --yes skills@VERSION list -g --json
```

结合 CLI 实际使用的全局 lock，说明已安装和可追踪的技能。默认 lock 常见于 `~/.agents/.skill-lock.json`；遵循当前版本和 XDG 配置，不创建、迁移或手工改写 lock。

只有确认该版本提供无写入的检查方式时，才用于报告可用更新。`1.7.1` 的 `check` 会更新，因此在用户只授权检查时不运行；此时报告清单及“该版本没有独立只读更新检查，尚未确认哪些 skill 有更新”。如需更深检查，可按 lock 的来源和 hash 只读比较上游；源不可访问不等于最新。

## 发现上游新增与移除

`skills update` 只刷新 lock 已登记的条目：上游仓库新增的 skill 不会进入更新清单，上游删除或移动的 skill 也会让 lock 条目静默悬空。每轮 skills 维护（含仅检查）都用只读脚本把这两类差异纳入例行报告：

```bash
python3 /path/to/dev-update/scripts/skills_discover.py
```

脚本按 CLI 同规则定位全局 lock（`$XDG_STATE_HOME/skills/.skill-lock.json`，否则 `~/.agents/.skill-lock.json`），对每个 GitHub 来源枚举上游全部 `SKILL.md` 并与 lock 的 `skillPath` 对比；不写 lock、不写磁盘。输出 JSON：

- `untracked`：上游存在但未登记的 skill，附 `group`（所在目录）便于按组判断；正式区与 in-progress、misc 等试验区一并列出，不默认过滤，由用户按组决定。
- `missing_upstream`：lock 已登记但上游消失的条目，附本地安装名；本地副本仍可运行但已冻结，不自动删除。
- `errors`：单源失败（`repository_not_found`、网络错误、`rate_limited`）；触发限流后剩余源标记 `skipped_after_rate_limit`。未认证限流约 60 次/小时，每源 2 次请求；可用 `GITHUB_TOKEN`/`GH_TOKEN` 环境变量或已登录的 `gh auth token` 提额。
- `truncated_sources`：上游 tree 被 GitHub 截断，该源结论不完整，不能据此断言无新增。
- `unsupported_sources`：非 GitHub 来源，只列出、不检查。

仅检查模式下该脚本可自由运行；它只读 GitHub API，源不可访问不等于最新。

### 补登记新增 skill

用户选定要引入的新 skill 后，用官方 CLI 精确安装，而不是全量重装：

```bash
DISABLE_TELEMETRY=1 npx --yes skills@VERSION add SOURCE -g -y --skill NAME...
```

`VERSION` 沿用本轮已解析的 CLI 版本，`SOURCE` 为 lock 中的来源（如 `mattpocock/skills`），`--skill` 接受多个名称（脚本输出 `untracked[].name`）。补登记属于新增安装而非更新，会写入 lock 和技能目录，执行前向用户确认清单。安装后重新运行 `skills_discover.py` 并用 `list -g --json` 验证登记。

### 处理上游消失

`missing_upstream` 只报告不处理：与用户确认后再用 `skills remove -g NAME` 移除或保留冻结副本。批量移动通常是上游路径重构，新路径会同时出现在 `untracked` 中；此时按重构处理，先补登记新条目，再按用户确认移除旧条目。

## 更新全部全局 Skills

已有更新授权时，先查看 `list -g --json` 和 lock，识别本地修改及无法追踪的来源；有本地修改时备份或按用户明确的覆盖策略处理，避免丢失定制。同时运行上方发现脚本，把 `untracked` 与 `missing_upstream` 纳入本轮报告；补登记需用户选定后单独执行，不与批量更新混为一步。

对于已核实的 `1.7.1`，执行用户要求的检查/更新命令：

```bash
DISABLE_TELEMETRY=1 npx --yes skills@VERSION check -g -y
```

`npx --yes` 接受 CLI 缓存下载，末尾的 `-y` 是 skills 自身的非交互参数；`-g` 明确限定全局范围。对已确认 `check` 只检查的旧版本，在检查后补充实际更新：

```bash
DISABLE_TELEMETRY=1 npx --yes skills@VERSION update -g -y
```

未来版本以官方源码和实际帮助为准；不能为了满足字面命令而把未知的 `check` 当成安全检查，也不要无理由退回旧版本。一个命令失败后保留诊断，不重复自动覆盖或修改 lock。

## 验证与覆盖范围

- 捕获更新日志和退出码，再运行 `list -g --json`；结合更新前后的 lock hash 和文件确认发生的更新。不再次运行可能写入的 `check` 充当验证。
- 退出码 0 仍需检查来源不可访问、跳过、失败及删除/迁移提示；不能只据退出码断言全部最新。
- `skills` 只维护自身可追踪的安装。手工复制、缺少 lock 元数据、本地来源，以及 Codex 插件缓存或内置 system skills 不能据此宣称已更新。
- 更新完成不等于覆盖完整：`update` 不发现上游新增/移除，须附上发现脚本结果或明确说明未运行；“全部最新”只针对 lock 已登记项。
- 对其他管理器维护的技能，报告未覆盖范围；只有用户要求扩展范围时，才使用相应管理器。不要用 `skills add --all` 重装替代更新；引入上游新增 skill 用上方“补登记”流程按名精确安装。

来源：[官方 CLI 命令分派源码](https://github.com/vercel-labs/skills/blob/main/src/cli.ts)、[更新实现](https://github.com/vercel-labs/skills/blob/main/src/update.ts)。发行版本还应核对本地 npx 缓存中的对应代码，不能仅凭 main 分支推断旧版本。
