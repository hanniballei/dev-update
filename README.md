# dev-update

一个维护全局开发工具的 Agent Skill：按实际安装渠道检查和更新全局 npm 包、原生 CLI 及其他管理器安装的工具，并维护 Codex 服务、全局 skills 与 Pi agent 插件。兼容 Codex、Pi、Devin 与支持 Agent Skills 的工具；不处理项目依赖或整机系统升级。

## 安装

```bash
npx skills add hanniballei/dev-update -g --skill dev-update -a codex -y
```

需要其他代理时，将 `-a codex` 换成对应名称；安装这个 skill 不会更新服务器的软件包或重启服务。

涉及 Codex 服务升级和重启时，推荐在独立 SSH / tmux 会话中使用 Pi：

```bash
pi --no-approve --skill ~/.agents/skills/dev-update
```

在 Pi 中显式调用 `/skill:dev-update 全局更新`。Pi 也支持自动发现 `~/.agents/skills/`；上述 `--skill` 指定已有安装，`--no-approve` 忽略项目配置。维护流程按执行器与服务的实际关系选择，不限定只能由 Pi 执行。

## 使用

```text
使用 $dev-update，只检查全局 npm 包和 Codex server，不更新。
使用 $dev-update，更新全部全局 npm 包；发现 Codex 服务时也更新其实际安装。
使用 $dev-update，更新全部全局 npm 包，并更新全局 skills。
使用 $dev-update，只更新 @openai/codex，不重启服务。
使用 $dev-update，更新 @openai/codex，并在不影响当前会话时重启 Codex 服务。
使用 $dev-update，只更新 Pi agent 插件。
使用 $dev-update，只检查全部开发工具，包括 npm 和 curl 安装的 CLI，不安装更新。
使用 $dev-update，只更新 Devin，先确认安装渠道，其他工具不要动。
使用 $dev-update，更新全部开发工具，包括 npm、非 npm CLI、Codex 服务、skills 和 Pi 插件。
使用 $dev-update，全量更新开发工具，但不要重启服务或结束当前会话。
```

入口 [`SKILL.md`](SKILL.md) 按范围加载指引，遵循“发现安装 → 核实管理归属与版本 → 展示计划 → 执行更新 → 分别验证磁盘与运行状态”。只读检查不调用可能安装更新的命令；更新请求复用已有授权，跨主版本、换渠道、强制重装及服务 / 会话影响按入口审批规则处理。npm 脚本不替换 linked / 本地 / Git 安装，不降级高于 `latest` 的版本，并把 npm 自身留到最后。

全局 npm 更新默认包含发现的 Codex 服务：skill 会定位服务实际使用的安装并升级，不局限于当前 shell 的 npm prefix。相同安装只更新一次，其他安装分别处理，并核对平台原生组件与运行版本。服务发现和跨安装更新由代理按服务器指引执行，不是 `npm_update.py` 单独扫描所有服务。运行版本落后时，按当前 CLI 能力查询 daemon 或实际进程；已有重启授权且维护会话独立时，直接重启并验证。缺少授权且能安全重启时才询问；当前会话依赖该服务时，给出待重启状态、兼容提示和独立执行命令。版本一致仍有兼容提示时，按实际配置和 TUI 输出继续核对，案例中的特性开关不作为通用默认设置。

**Codex 托管 daemon：** 它可能使用独立于全局 npm 的包。Skill 会按[托管包更新指引](references/codex-server.md#codex-托管的-daemon-包)识别部署方式；当前 CLI 支持时，用 `codex app-server daemon update --from-cli` 对齐到本轮已更新的 CLI，并分别验证 CLI、托管包与运行版本。该操作可能中断任务，需有相应授权且维护会话独立；未执行时明确报告托管包待更新。`npm_update.py --apply` 本身不更新托管 daemon 或重启服务。

**注意 `skills check` 的版本差异：** 已核实 `skills@1.7.1` 的 `check` 是更新别名，不能用于仅检查任务；旧版本则可能还需要 `skills update` 才实际更新。具体流程见 [`references/skills-update.md`](references/skills-update.md)。不属于该 CLI 管理的技能会明确报告为未覆盖，而非声称已经更新。管理器更新只刷新已登记项，上游新增与移除靠下方的发现脚本例行报告。

## 非 npm 工具与全量维护

“全部开发工具 / 全量更新”包括可发现的非 npm 开发工具；“全部全局 npm 包”仍仅包含 npm 与既有的 Codex 服务关联范围，不顺带更新其他原生工具、skills 或 Pi 插件。指定工具只维护该目标；多份安装无法确定目标时先明确范围，不自动安装缺失的软件。

非 npm 流程由代理按 [`references/native-tools.md`](references/native-tools.md) 执行，`npm_update.py` 仍只处理 npm。它结合管理器记录、已知入口、用户可执行目录和服务发现实际安装，按所属管理器、官方自更新器或宿主渠道更新；同名不同安装分别处理，共用安装去重。只维护原生工具不要求 Node.js / npm。

Devin CLI 是首个具体渠道示例：独立安装可使用已核实的 `devin update`，Homebrew 安装由 Homebrew 更新，宿主捆绑版本沿宿主机制维护。curl 只是下载方式，不代表应重新运行安装脚本；没有安全的只读查询时报告“最新版本未确认”。其他工具按当前官方能力核实，不承诺自动识别或更新任意手工安装的软件。

每份安装都记录渠道、更新前后版本、验证结果及未完成原因。“全量维护已执行”表示清单逐项处理；仍有失败、未知、待审批、待重启或生效未验证时，不称“全部更新完成”。固定版本与用户排除项按约束保留，项目依赖、系统整机升级及覆盖边界之外的软件不自动纳入。

## Skills 发现脚本

`skills update` 不发现上游仓库新增或移除的 skill。`scripts/skills_discover.py` 是只读脚本：按 CLI 同规则定位全局 lock，枚举每个 GitHub 来源上游的全部 `SKILL.md` 并与 lock 对比，不写 lock、不写磁盘。

从仓库根目录执行：

```bash
python3 scripts/skills_discover.py
python3 scripts/skills_discover.py --source mattpocock/skills
```

JSON 输出包含 `untracked`（上游新增未登记，附目录分组）、`missing_upstream`（lock 已登记但上游消失）、`errors`（单源失败与限流）、`truncated_sources` 与 `unsupported_sources`。运行环境需要可访问 GitHub API；未认证限流约 60 次/小时，可用 `GITHUB_TOKEN`/`GH_TOKEN` 或已登录的 `gh auth token` 提额，不要把 token 写入参数或报告。脚本失败（lock 不可读、指定来源不在 lock）退出 1，单源错误记录在输出中不退出非零。

发现的新增 skill 由用户选定后按[补登记流程](references/skills-update.md#补登记新增-skill)精确安装，不用 `skills add --all` 重装。

**Pi 插件更新：** 已用本机 Pi 1.0.4 的帮助及官方文档核实 `pi update --extensions`。Skill 默认追加 `--no-approve`，只更新个人/全局配置中的插件包，保留固定版本和 Git ref；不会把裸 `pi update` 的本体升级当成插件更新。完整开发环境更新包含此项，单独的 npm 或 skills 更新不自动扩展到插件管理器。详见 [`references/pi-extensions.md`](references/pi-extensions.md)。

## 自更新与执行顺序

所有安装渠道遵循同一顺序：先维护普通工具和 skills，再处理服务安装及可安全执行的重启，当前执行器本体与必要后续验证留到最后。npm 目标用已有 `--package` 参数分批，npm 自身放在所有 npm 批次末尾；空批次直接跳过，避免无 `--package` 的 `--apply` 意外扩大范围。分批是代理按 [`SKILL.md`](SKILL.md#更新前与执行顺序)安排的流程，脚本不会自动识别当前代理或服务依赖。

- **更新 `dev-update` 本体：** 首次写入前复制指引、脚本和参考文件，并展开符号链接。本轮从独立快照继续执行，新版流程用于下一轮，避免后续读到不同版本的文件。快照方法见 [`references/skills-update.md`](references/skills-update.md#本-skill-的自更新)。
- **Pi 更新自身：** 旧进程通常仍运行已加载的代码，磁盘升级不能保证动态导入或 reload 安全。在最后一个独立 shell / 脚本阶段完成本体更新、新 CLI 核对、已授权的插件更新及日志记录；旧会话只收尾，完整维护结束后重新启动 Pi。`/reload` 刷新资源，不能代替 Pi 本体重启。详见 [`references/pi-extensions.md`](references/pi-extensions.md#当前执行器是-pi-时)。

执行快照保护本 skill 的文件一致性，不隔离 Pi 运行时或保证插件兼容。报告分别记录磁盘更新、运行版本及实际连接/资源验证；尚需重启、重新开启会话或未能验证的项目明确保留。

## npm 脚本

运行环境需要 Python 3.10+、Node.js 及 npm；脚本本身只使用 Python 标准库，无须安装 Python 运行依赖。正常检查会读取 npm registry 并可能写入 npm 缓存，不安装或升级全局包。

从仓库根目录执行：

```bash
python3 scripts/npm_update.py
python3 scripts/npm_update.py --apply
python3 scripts/npm_update.py --apply --package @openai/codex
```

JSON 输出包含计划、跳过项，以及更新模式的逐包结果、安装后版本和剩余更新。可重复传入 `--package` 选择同一批中的多个包。检查成功退出 0，包括存在待更新包的情况；命令/数据错误、安装失败、版本核对失败或仍有目标更新时退出 1。有意跳过的来源会列出，不等于已更新。

如使用其他 Node 安装，设置对应 `PATH` 并传入 `--npm /absolute/path/to/npm`。作用域是该 npm 的全局 prefix，不会扫描所有用户和所有 Node 安装。npm 安装可能执行第三方生命周期脚本，应在已有更新授权下使用 `--apply`。

没有必需的新增环境变量。复用本机 npm registry/auth 配置；skills 私有来源复用其支持的 GitHub 认证。不要把 token 放入参数、报告或仓库。`DISABLE_TELEMETRY=1` 是 skills CLI 的可选遥测开关；Pi 插件维护需要可用的 `pi` 命令，并遵循已有 `PI_CODING_AGENT_DIR` 路径配置；其他路径和权限使用当前环境配置。

## 开发与验证

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/ruff check scripts tests
.venv/bin/ruff format --check scripts tests
python3 -m unittest discover -s tests -v
```

只格式化修改的文件：`.venv/bin/ruff format scripts/npm_update.py tests/test_npm_update.py`。
测试使用模拟 npm，不连接生产环境，不更新真实全局包或服务。GitHub Actions 执行相同的 lint、格式和单元测试检查。

策略模拟用例见 [`evals/evals.json`](evals/evals.json)，覆盖多安装渠道只读检查、全量更新中的失败与生效缺口、npm 限定范围及 Codex 服务回归。用例使用虚构环境和命令结果，不执行真实更新；它们用于检查代理的计划与报告，不能替代真实安装渠道的集成验证。每轮评估显式指定该轮 skill 目录（旧版快照或待发布版本）及输出目录，再将场景 `prompt` 和 `runner_instructions` 单独交给执行代理，保留 `expected_output` 和验收条件供评审使用，避免答案泄漏。

## OpenAI 9 月指导的应用

依据 OpenAI 于 **2026-09-11** 发布的 [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) 与 [Build skills](https://learn.chatgpt.com/docs/build-skills)：

- 简短 description 只触发全局工具维护，不吸引普通项目依赖工作。
- 根文件保留统一流程、范围选择和关键约束，非 npm 工具、Codex 服务、skills 版本分支和 Pi 插件指引按需加载。
- npm 的数据解析、精确安装和版本核验采用确定性脚本；非 npm 更新和服务部署按实际安装归属及当前官方能力处理。
- 用请求范围内的可观察结果定义完成，不把检查、磁盘更新和运行进程更新混为一谈。

这些是官方指导的实现选择，不表示 OpenAI 审核或认证了本项目。
