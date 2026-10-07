# 全局 Skills 更新

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

## 更新全部全局 Skills

已有更新授权时，先查看 `list -g --json` 和 lock，识别本地修改及无法追踪的来源；有本地修改时备份或按用户明确的覆盖策略处理，避免丢失定制。

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
- 对其他管理器维护的技能，报告未覆盖范围；只有用户要求扩展范围时，才使用相应管理器。不要用 `skills add --all` 重装替代更新。

来源：[官方 CLI 命令分派源码](https://github.com/vercel-labs/skills/blob/main/src/cli.ts)、[更新实现](https://github.com/vercel-labs/skills/blob/main/src/update.ts)。发行版本还应核对本地 npx 缓存中的对应代码，不能仅凭 main 分支推断旧版本。
