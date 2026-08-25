# 兼容性与本机证据

0.2.1 以 [Agent Plugins v1](https://agent-plugins.org/specification) 为一个便携核心，并提供
Codex、Claude Code、Hermes Agent、OpenClaw 四个适配面。结构校验、安装元数据和实际运行是不同层级的证据。

| 范围 | 实际命令/契约 | 本机证据（Windows，2026-08-25） | 状态 |
| --- | --- | --- | --- |
| 根结构 | `C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe scripts\\validate_bundle.py .` | 0.2.1 候选树退出 0，输出 `VALID`；只检查清单和共享 Skill 结构。 | 结构已验证；不等同于宿主运行 |
| Codex 远程 marketplace | `codex plugin marketplace add naipi11/Agent-SkillOpt --ref b9c38b8d0fcfc4aaffc98c4d6b91bfe8f8f80c70` → `codex plugin add agent-skillopt@agent-skillopt` | 已成功添加 marketplace；其本地 Git 快照 `HEAD` 为该 SHA；`codex plugin list --available --json` 显示 `agent-skillopt@agent-skillopt` v0.2.0、`installed: true`、`enabled: true`。 | 已实际安装并验证元数据；未证明 Skill 已在新 task 运行 |
| Claude Code 远程 marketplace | `claude plugin marketplace add naipi11/Agent-SkillOpt --scope user` → `claude plugin install agent-skillopt@agent-skillopt --scope user --yes` | 已成功安装 user scope；marketplace 本地 Git 快照 `HEAD` 为 `b9c38b8d0fcfc4aaffc98c4d6b91bfe8f8f80c70`；`claude plugin list --json` 显示 v0.2.0、`enabled: true`。未在对话中执行 `/reload-plugins`。 | 已实际安装并验证元数据；未证明当前/新会话已加载 |
| Hermes Agent | `hermes plugins install naipi11/Agent-SkillOpt --ref b9c38b8d0fcfc4aaffc98c4d6b91bfe8f8f80c70 --no-enable` → `hermes plugins show agent-skillopt` → `hermes plugins enable agent-skillopt --no-allow-tool-override` | 默认安装安全扫描把已发布的 0.2.0 树判为 `dangerous` 并阻断；`show` 返回未找到，未启用、未修改 `plugins.scan_on_install`。 | 被安全扫描正确阻断；未安装、未启用 |
| OpenClaw | [bundle contract](https://docs.openclaw.ai/plugins/bundles) | 本机没有 `openclaw` CLI；未执行 install、inspect 或 gateway restart。 | 合约目标；未本机安装验证 |
| 本地 bundle 执行器 | `scaffold_bundle.py install --host hermes --path . --source naipi11/Agent-SkillOpt --source-ref <40-char-sha>` | 0.2.1 候选树只读渲染了绑定 SHA 的 token/argv；未传 `--execute`，没有运行宿主命令。 | 计划/确认契约已验证；不是安装成功证据 |

上述 Codex 与 Claude Code 证据只针对已发布 commit
`b9c38b8d0fcfc4aaffc98c4d6b91bfe8f8f80c70` 的 0.2.0 内容：没有执行 refresh、update 或 Claude 对话
reload，也没有运行安装后的 Skill。候选 0.2.1 树修复了 Hermes 计划的不可变 ref、失败报告和扫描误报，
但尚未发布，因此不能被表述为已在远端宿主安装。

Hermes 依照其[安装时安全扫描规则](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)
阻止了已发布树。候选树已用同一 `plugin_guard` 复扫为 `safe`（仍有受审查的 medium 提示：受控的
`shell=False` 子进程、CI 安装和大 GIF），但只有在发布后重新扫描和安装成功才能更新 Hermes 状态。不得关闭
`plugins.scan_on_install`，也不得尝试用 `--force` 绕过 `dangerous` verdict。

远程项目安装与本地生成 bundle 安装是两条不同路径。Codex、Claude Code 和 Hermes 命令会访问网络并改变
用户状态；OpenClaw 路径要求一个已验证的本地 bundle 根目录。依据 Claude Code 官方插件契约，Git
marketplace 可能会按其设置在后台刷新；初始配置后，即使没有新的明确用户命令，也可能发生远程获取。显式
安装或更新同样会访问网络并改变宿主状态。`main` 是可变分支，远端内容可随分支推进而漂移。Codex 支持
`--ref`，而 Claude GitHub 简写使用默认分支（当前为 `main`）；两者不应被表述为相同的 ref 语义。Claude
远程 marketplace source 仅支持 branch/tag ref，不能承诺以 commit SHA 固定安装。release tag 也只是 Git
ref，并非天然不可变；仅在受保护且受信任时使用，并在 release notes 中记录、复核其解析出的 40 位 commit
SHA，作为精确内容身份的审计/验证事实。

- Codex CLI 证据和权限边界见[官方插件说明](https://help.openai.com/en/articles/20001256-plugins-in-codex/)。
- Claude 的 marketplace/清单语义见[插件参考](https://code.claude.com/docs/en/plugins-reference)。
- Hermes 的便携包和 Git source 语义见其[插件文档](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)；本项目只接受明确的 `<owner>/<repository>` Git source。
- OpenClaw 0.2.1 没有原生 `openclaw.plugin.json` 或 runtime code；兼容发现不是运行时承诺。

各宿主安装是多步骤、非原子的外部状态变更。失败后应先用 `codex plugin list`、`claude plugin list`
或 `hermes plugins show <name>` 只读检查，再依据实际宿主状态按官方文档移除残留或补做缺失步骤；不得把
重跑整组命令当作恢复。OpenClaw 未本机安装，本文不提供未经验证的检查、移除或修复 argv。

`pyproject.toml`、`src/agent_skillopt/__init__.py`、根 `plugin.json`、`.codex-plugin/plugin.json` 与
`.claude-plugin/plugin.json` 必须始终声明同一静态版本。每次发布改变远程插件内容时，维护者必须同步递增
这五处版本，并记录解析后的 40 位 commit SHA；静态版本未变时，宿主可能不会把内容变更视为可更新版本。
