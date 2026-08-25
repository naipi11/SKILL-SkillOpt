# 宿主安装边界

先为一个已离线验证的本地包渲染计划。渲染不会执行命令；任何实际操作都需要用户在稍后
单独请求，并提交该渲染结果的精确确认令牌。

| 宿主 | 渲染的后续命令 | 边界 |
| --- | --- | --- |
| Codex | `codex plugin marketplace add <bundle-root>`，再 `codex plugin add <name>@<name>` | 改变用户级 marketplace/plugin 状态。 |
| Claude Code | `claude plugin marketplace add <bundle-root>`，再 `claude plugin install <name>@<name>` | 改变用户级 marketplace/plugin 状态。 |
| Hermes Agent | `hermes plugins install <owner>/<repository> --ref <40-char-sha> --no-enable`，再 `hermes plugins enable <name>` | 只接受明确的 owner/repository Git source（非裸索引名、本地路径或 URL）；`--source-ref` 可选且只能为精确 40 位 SHA，会映射到 Hermes 的 `--ref`。如需在启用前做只读检查，可单独执行 `hermes plugins show <name>`。 |
| OpenClaw | `openclaw plugins install <bundle-root>`，`openclaw plugins inspect <name>`，`openclaw gateway restart` | 会安装、检查并重启网关；本包依靠 Codex-compatible discovery。 |

0.2.1 没有 `openclaw.plugin.json`、Hermes `plugin.yaml`、MCP 配置、hooks 或原生宿主
可执行逻辑。按照 [OpenClaw bundle documentation](https://docs.openclaw.ai/plugins/bundles)，
OpenClaw 预期通过 `.codex-plugin/` 发现并使用共享 `skills/`；这是文档化的兼容目标，
不是本地安装验证结果。Hermes 使用根 Agent Plugins v1 便携包。

这些命令不是原子事务。前一步成功、后一步失败时，可能已留下 marketplace、下载的插件或已安装而
未重启的宿主状态。先停止，使用 Codex 的 `codex plugin list`、Claude Code 的 `claude plugin list`
或 Hermes 的 `hermes plugins show <name>` 只读确认实际状态；然后依据相应宿主官方文档移除残留或仅
重试缺失步骤。OpenClaw 没有本机 CLI 证据，本文不杜撰其检查、移除或修复命令。

计划中的本地包路径与内容会在执行前重新验证和指纹比对；目录或内容变化、确认令牌不匹配
或命令参数不安全时必须失败。最终快照后、外部宿主实际消费该路径前仍存在同权限修改的
操作系统竞态；未使用 `--source-ref` 时 Hermes 的远程源内容也可变。这些是不能省略的信任边界。
