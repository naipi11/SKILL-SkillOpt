# 宿主安装边界

先为一个已离线验证的本地包渲染计划。渲染不会执行命令；任何实际操作都需要用户在稍后
单独请求，并提交该渲染结果的精确确认令牌。

| 宿主 | 渲染的后续命令 | 边界 |
| --- | --- | --- |
| Codex | `codex plugin marketplace add <bundle-root>`，再 `codex plugin add <name>@<name>` | 改变用户级 marketplace/plugin 状态。 |
| Claude Code | `claude plugin marketplace add <bundle-root>`，再 `claude plugin install <name>@<name>` | 改变用户级 marketplace/plugin 状态。 |
| Hermes Agent | `hermes plugins install <owner>/<repo> --no-enable`，再 `hermes plugins enable <name>` | 需要远程 Git 内容；令牌绑定源字符串但不能固定远程内容。 |
| OpenClaw | `openclaw plugins install <bundle-root>`，`openclaw plugins inspect <name>`，`openclaw gateway restart` | 会安装、检查并重启网关；本包依靠 Codex-compatible discovery。 |

0.2.0 没有 `openclaw.plugin.json`、Hermes `plugin.yaml`、MCP 配置、hooks 或原生宿主
可执行逻辑。OpenClaw 发现 `.codex-plugin/` 后使用共享 `skills/`；Hermes 使用根
Agent Plugins v1 便携包。

计划中的本地包路径与内容会在执行前重新验证和指纹比对；目录或内容变化、确认令牌不匹配
或命令参数不安全时必须失败。最终快照后、外部宿主实际消费该路径前仍存在同权限修改的
操作系统竞态；Hermes 的远程源内容也可变。这些是不能省略的信任边界。
