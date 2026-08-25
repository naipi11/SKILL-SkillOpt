# 兼容性与本机证据

0.2.0 以 [Agent Plugins v1](https://agent-plugins.org/specification) 为一个便携核心，并提供
Codex、Claude Code、Hermes Agent、OpenClaw 四个适配面。结构校验不等于安装、启用或运行成功。

| 范围 | 实际命令/契约 | 本机证据（Windows，2026-08-25） | 状态 |
| --- | --- | --- | --- |
| 根结构 | `C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe scripts/validate_bundle.py .` | 退出 0，输出 `VALID`；仅检查清单和共享 Skill 结构。 | 已验证；未本机安装验证 |
| Claude Code 远程 marketplace | `/plugin marketplace add naipi11/Agent-SkillOpt` → `/plugin install agent-skillopt@agent-skillopt` → `/reload-plugins` | 离线检查了 `.claude-plugin/marketplace.json` 的 `agent-skillopt` 身份和 `./` 根 source；没有执行远程获取、安装或 reload。 | 清单/CLI 契约已验证；未实际远程安装 |
| Codex 远程 marketplace | `codex plugin marketplace add naipi11/Agent-SkillOpt --ref main` → `codex plugin add agent-skillopt@agent-skillopt` | 离线检查了 `.codex-plugin/plugin.json` 的 `agent-skillopt` 身份和 `./skills/` skills 根；没有执行远程获取或安装。 | 清单/CLI 契约已验证；未实际远程安装 |
| Codex CLI | `codex plugin list --available --json` | 退出 0，返回已安装/可用插件的 JSON（含每个条目的 `version`）；未从该目录推断本包已安装或启用。 | CLI 读取面已验证；未本机安装验证 |
| Claude Code | `claude plugin validate . --strict` | 退出 0，`Validation passed`；只校验 marketplace 清单。 | 清单已验证；未本机安装验证 |
| Hermes Agent | `hermes plugins --help`、`hermes skills --help` | 均退出 0；plugins 帮助列出 portable Agent Plugins v1 packages、`install`、`enable`。 | CLI 可用；未本机安装验证 |
| OpenClaw | [bundle contract](https://docs.openclaw.ai/plugins/bundles) | 本机没有 `openclaw` CLI；未执行 install、inspect 或 gateway restart。 | 合约目标；未本机安装验证 |

同一稳定目录中，通过项目随 Skill 分发的包装器，以
`C:\\Users\\33384\\AppData\\Local\\Programs\\Python\\Python312\\python.exe`
执行 `skills/agent-skillopt/scripts/scaffold_bundle.py install --host codex --path .`，退出 0 并只读渲染
JSON token 和两个计划步骤；调用未传 `--execute`，其中的 `marketplace add` 与 `plugin add` 都没有
运行。该命令从仓库根目录运行，包装器优先使用其自身的 `src`，不会使用旧的全局或 venv console
entry point。编辑包时，安装计划的稳定快照会故意拒绝变化并要求重新渲染；这不是安装成功证据。
没有运行 marketplace add、install、enable、inspect、restart 或远程获取。

远程 marketplace 安装与本地生成包安装是两条不同路径。README 中的 Claude slash commands 和
Codex CLI 命令只具有清单/CLI 契约证据，不是实际远程安装成功的证据；它们会访问网络并改变用户
状态。刷新或升级必须由操作者另行明确执行。`main` 是可变分支，远端内容可随分支推进而漂移；若
将来有 release，应选择不可变 tag 或完整 commit SHA，而不是继续依赖 `main`。本项目的
`scaffold_bundle.py install` 仍只为已经创建并离线验证的本地 bundle 渲染计划，不用于仓库的远程
bootstrap。

- Codex CLI 证据和权限边界见[官方插件说明](https://help.openai.com/en/articles/20001256-plugins-in-codex/)。
- Claude 的 marketplace/清单语义见[插件参考](https://code.claude.com/docs/en/plugins-reference)。
- Hermes 的便携包和 Git source 语义见其[插件文档](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)；本项目 0.2 只渲染并接受明确的 `<owner>/<repository>` Git source。
- OpenClaw 0.2.0 没有原生 `openclaw.plugin.json` 或 runtime code；兼容发现不是运行时承诺。

只有操作者另行授权实际宿主操作、使用刚渲染的 token 并观察目标宿主结果，才能更新为“本机
安装验证”。
