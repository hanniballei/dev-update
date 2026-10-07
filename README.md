# dev-update

一个维护全局开发工具的 Agent Skill：检查和更新全局 npm 包，将发现的 Codex 服务实际安装一并升级，并更新 `skills` CLI 管理的全局技能。兼容 Codex 与支持 Agent Skills 的工具。

## 安装

```bash
npx skills add hanniballei/dev-update -g --skill dev-update -a codex -y
```

需要其他代理时，将 `-a codex` 换成对应名称；安装这个 skill 不会更新服务器的软件包或重启服务。

## 使用

```text
使用 $dev-update，只检查全局 npm 包和 Codex server，不更新。
使用 $dev-update，更新全部全局 npm 包；发现 Codex 服务时也更新其实际安装。
使用 $dev-update，更新全部全局 npm 包，并更新全局 skills。
使用 $dev-update，只更新 @openai/codex，不重启服务。
```

入口 [`SKILL.md`](SKILL.md) 按范围加载指引。npm 更新默认包括主版本升级；脚本不替换 linked / 本地 / Git 安装，不降级高于 `latest` 的版本，并把 npm 自身留到最后。服务重启与磁盘软件升级分开处理，避免中断当前代理会话。

全局 npm 更新默认包含发现的 Codex 服务：skill 会定位服务实际使用的安装并升级，不局限于当前 shell 的 npm prefix。相同安装只更新一次，其他安装分别处理，并核对平台原生组件与运行版本。服务发现和跨安装更新由代理按服务器指引执行，不是 `npm_update.py` 单独扫描所有服务。当前会话所属服务需要重启时，先完成磁盘升级并明确报告待重启；不会把“未重启”误称为运行版本已更新。

**注意 `skills check` 的版本差异：** 已核实 `skills@1.7.1` 的 `check` 是更新别名，不能用于仅检查任务；旧版本则可能还需要 `skills update` 才实际更新。具体流程见 [`references/skills-update.md`](references/skills-update.md)。不属于该 CLI 管理的技能会明确报告为未覆盖，而非声称已经更新。

## npm 脚本

运行环境需要 Python 3.10+、Node.js 及 npm；脚本本身只使用 Python 标准库，无须安装 Python 运行依赖。正常检查会读取 npm registry 并可能写入 npm 缓存，不安装或升级全局包。

从仓库根目录执行：

```bash
python3 scripts/npm_update.py
python3 scripts/npm_update.py --apply
python3 scripts/npm_update.py --apply --package @openai/codex
```

JSON 输出包含计划、跳过项，以及更新模式的逐包结果、安装后版本和剩余更新。检查成功退出 0，包括存在待更新包的情况；命令/数据错误、安装失败、版本核对失败或仍有目标更新时退出 1。有意跳过的来源会列出，不等于已更新。

如使用其他 Node 安装，设置对应 `PATH` 并传入 `--npm /absolute/path/to/npm`。作用域是该 npm 的全局 prefix，不会扫描所有用户和所有 Node 安装。npm 安装可能执行第三方生命周期脚本，应在已有更新授权下使用 `--apply`。

没有必需的新增环境变量。复用本机 npm registry/auth 配置；skills 私有来源复用其支持的 GitHub 认证。不要把 token 放入参数、报告或仓库。`DISABLE_TELEMETRY=1` 是 skills CLI 的可选遥测开关；其他路径和权限使用当前环境配置。

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

## OpenAI 9 月指导的应用

依据 OpenAI 于 **2026-09-11** 发布的 [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) 与 [Build skills](https://learn.chatgpt.com/docs/build-skills)：

- 简短 description 只触发全局工具维护，不吸引普通项目依赖工作。
- 根文件保留范围选择和关键约束，Codex 服务、skills 版本分支按需加载。
- 只有 npm 的数据解析、精确安装和版本核验采用确定性脚本；服务部署方式由实际环境决定。
- 用请求范围内的可观察结果定义完成，不把检查、磁盘更新和运行进程更新混为一谈。

这些是官方指导的实现选择，不表示 OpenAI 审核或认证了本项目。
