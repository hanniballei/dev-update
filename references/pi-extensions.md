# Pi Agent 插件更新

## 确认实际 Pi

```bash
command -v pi
pi --version
pi update --help
pi list --help
```

本机制作时核实的入口属于 `@earendil-works/pi-coding-agent@1.0.4`，支持 `pi update --extensions`。环境可能还安装旧分发或 fork；以实际入口和该版本帮助为准，不自动切换到另一套 Pi，也不把 `omp` 当成同一个插件管理器。Pi 未安装时报告未覆盖，不为了更新插件而安装 Pi。

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

`--extensions` 只处理 Pi 管理的插件包；本机版本的裸 `pi update` 默认升级 Pi 本体，不能拿它代替插件更新。`--no-approve` 忽略项目配置，避免从当前仓库误更新项目插件；不擅自授予项目 trust。用户明确要求项目插件时，才切换到指定项目并使用该版本对应的项目作用域选项。

旧版本若不支持这些参数，先核实其官方文档中的等效插件更新方式，不盲目删掉参数重试。同一轮还升级 Pi 本体时，升级后重新确认入口和帮助，再运行插件更新。

## 固定版本与验证

- 保留 npm 固定版本和 Git ref；更新不能自行解除锁定或修改插件声明，其他更新路径也应遵守这些约束。新版本会将 Git checkout 对齐声明的 ref，旧版本可能直接跳过固定来源。
- 本地文件、目录和内置插件不等于可升级的远程包。`--extensions` 更新整个 Pi 包，包内还可能含 skills、主题或提示模板，不应声称只改了其中的扩展文件。
- 更新前记录版本或 Git commit；有本地改动时保留定制并报告冲突，不强制覆盖。来源不可访问、安装失败或跳过项要明确列出。
- 捕获更新日志和退出码，更新后再次运行 `pi list --no-approve`，核对实际安装版本或 commit；不能只凭插件仍出现在清单中就称升级成功。
- 磁盘更新不保证正在运行的 Pi 会话已加载新插件；按该版本支持的 reload 方式或在下一次启动加载，不自行终止当前会话。

来源：[Pi 官方 CLI 文档](https://pi.dev/docs/latest/cli#update-pi-or-packages)、[Pi 官方包管理文档](https://pi.dev/docs/latest/packages)。
