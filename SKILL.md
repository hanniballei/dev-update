---
name: dev-update
description: 检查或更新全局 npm 工具、服务器上的 Codex 和全局安装的 skills；不处理项目依赖升级。
---

# Dev Update

按用户指定的范围维护开发工具。只要求检查时保持只读；明确要求更新时，完成更新和验证，不重复索要已有授权。制作或安装这个 skill 本身不代表授权升级当前服务器。

## 选择范围

- **npm 包**：运行下方脚本。它仅处理当前 npm prefix 的顶层全局包，不修改项目依赖。
- **Codex / codex server**：全局 npm 维护时，读取 [Codex 服务器指引](references/codex-server.md) 发现 Codex 服务或进程。更新全部全局 npm 工具时，也升级 `codex-app-server.service` 等服务实际使用的 Codex 安装，即使它不属于当前 npm prefix；不能只报告发现服务或当前 CLI 已最新。
- **全局 skills**：读取 [Skills 更新指引](references/skills-update.md)，特别注意 `check` 在不同版本中可能直接更新文件。
- 未限定范围的“更新开发环境 / 全部开发工具”包含以上三项；“更新全部全局 npm 包”包含 npm 包和发现的 Codex 服务安装，但不更新 skills。用户明确限定某个包、排除服务器或只要求检查时，遵循该限制。

## npm 检查与更新

把下面路径替换为当前 skill 的实际目录；命令可从任意工作目录运行。

```bash
python3 /path/to/dev-update/scripts/npm_update.py
```

输出 JSON 包含全局 prefix、待更新包的当前版本和目标版本、跳过原因，以及已安装的 Codex 版本。脚本正确区分 `npm outdated` 的退出码 1 和查询失败。

更新前简要展示目标清单，指出跨主版本变化。用户要求更新全部全局包时，包括主版本升级；有版本约束或指定包时，按该约束调整范围。

```bash
python3 /path/to/dev-update/scripts/npm_update.py --apply
```

指定包可重复传入 `--package`；不同 Node 安装可用 `--npm /absolute/path/to/npm`，并按服务器指引设置对应 Node 的 `PATH`。脚本重新查询当前状态，逐包安装查询到的精确版本、最后更新 npm 自身，并核对安装版本及剩余更新。linked、本地或 Git 来源以及高于 `latest` 的版本不会被自动替换或降级。

更新可能执行包的安装脚本；遵循当前运行环境的权限限制。失败后保留具体失败项，继续与其独立的维护工作，不通过 `sudo`、`--force`、删除目录或修改配置绕过失败。

## 完成条件

报告更新前后版本、失败和跳过项；Codex 服务需区分磁盘版本与运行版本，并注明是否需要重启。Skills 需说明已更新、无法追踪、查询失败或待人工处理的来源。只有请求范围内的验证已完成且没有未披露问题时，才称“全部更新完成”。
