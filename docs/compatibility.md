# 兼容性与本机证据

0.2.1 以 [Agent Plugins v1](https://agent-plugins.org/specification) 为一个便携核心，并提供
Codex、Claude Code、Hermes Agent、OpenClaw 四个适配面。结构校验、安装元数据和实际运行是不同层级的证据。

| 范围 | 实际命令/契约 | 本机证据（Windows，2026-08-25） | 状态 |
| --- | --- | --- | --- |
| 根结构 | `C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe scripts\\validate_bundle.py .` | 已发布 `v0.2.1` 树退出 0，输出 `VALID`；只检查清单和共享 Skill 结构。 | 结构已验证；不等同于宿主运行 |
| Codex 远程 marketplace | `codex plugin marketplace remove agent-skillopt` → `codex plugin marketplace add naipi11/Agent-SkillOpt --ref 9a3c9e1765a5ff0561af5221906879670f5c4536` → `codex plugin add agent-skillopt@agent-skillopt` | marketplace checkout、`last_revision` 与 `ref` 均为该 SHA；`codex plugin list --available --json` 显示 `agent-skillopt@agent-skillopt` v0.2.1、`installed: true`、`enabled: true`。 | 已实际安装并验证元数据；未证明 Skill 已在新 task 运行 |
| Claude Code 远程 marketplace | `claude plugin marketplace update agent-skillopt` → `claude plugin update agent-skillopt@agent-skillopt --scope user --yes` | marketplace 本地 Git 快照 `HEAD` 为 `9a3c9e1765a5ff0561af5221906879670f5c4536`；`claude plugin list --json` 显示 user scope v0.2.1、`enabled: true`。CLI 报告重启后才应用。 | 已实际安装并验证元数据；当前会话尚需重启，未证明运行 |
| Hermes Agent | `hermes plugins install naipi11/Agent-SkillOpt --ref 9a3c9e1765a5ff0561af5221906879670f5c4536 --no-enable` → `hermes plugins show agent-skillopt` → `hermes plugins enable agent-skillopt` | 默认扫描未阻断安装；`show` 显示 v0.2.1、`Status: enabled`；配置为 `allow_tool_override: false`，CLI 报告下一个 session 生效。 | 已实际安装并启用；尚未证明新 session 运行 |
| OpenClaw | [bundle contract](https://docs.openclaw.ai/plugins/bundles) | 本机没有 `openclaw` CLI；未执行 install、inspect 或 gateway restart。 | 合约目标；未本机安装验证 |
| 本地 bundle 执行器 | `scaffold_bundle.py install --host hermes --path . --source naipi11/Agent-SkillOpt --source-ref <40-char-sha>` | 已发布 `v0.2.1` 树只读渲染了绑定 SHA 的 token/argv；未传 `--execute`，没有运行宿主命令。 | 计划/确认契约已验证；不是安装成功证据 |

上述 Codex、Claude Code 与 Hermes 证据针对已发布 commit
`9a3c9e1765a5ff0561af5221906879670f5c4536` 的 `v0.2.1`：Codex 已安装/启用并 pin 到该 SHA；
Claude Code 已在 user scope 安装/启用但需重启；Hermes 已安装/启用、`allow_tool_override: false`，
于下一个 session 生效。三者均未证明安装后 Skill 已实际运行。

Hermes 依照其[安装时安全扫描规则](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)
完成了 `v0.2.1` 的安装和启用，且未开启 `allow_tool_override`。这不是 Skill 已实际运行的证据；不得关闭
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
