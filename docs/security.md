# 安全边界

## 创建和验证默认离线

`preview` 只在内存中计划文件，`apply` 只在确认后写本地文件，`validate` 只读本地结构。三者
都不读取凭据、不发起网络、不安装依赖，也不执行生成 Skill 的 script、hook 或 resource。
规格、argv、token、文档、测试和日志都不得保存 secret。

## 质量评分与安全审查

每个由脚手架生成的包至少包含 `tests/cases/*.json`。`review` 会在正式结构验证后，
只读扫描 Skill 正文、资源和案例，输出确定性的 `quality_score`、安全状态和发现项；
它不执行 Skill、script、hook、模型或宿主命令。secret-like 值、指令覆盖、破坏性操作
等高风险模式会阻断报告；shell、网络和环境变量访问等中风险模式要求人工复核。

`evaluate` 只读取操作者或宿主另行收集的 `responses.json`，按案例中的
`required_contains` / `forbidden_contains` 做文本评分。它不启动模型、不联网，也不把
静态评分当作所有 Agent 宿主的运行效果证明。报告始终明确标记
`executed: false` 和 `network_accessed: false`。

创建 token 绑定规范化规格和输出目录。现有目标总是拒绝且不会覆盖用户文件；确认后先写入
目标同级唯一 staging 目录、验证后再发布。异常只清理本次 staging；系统锁导致清理失败时，
必须报告残留路径，不能删除目标或静默忽略。

## 命令计划不是执行

没有 `--execute` 的 `install` 只返回 argv、`network_required` 和确认令牌。执行时不用 shell，
逐个传递已渲染 argv；token 必须匹配重新构造的计划。它绑定宿主、规范路径、目录身份、内容
指纹、argv 与 Hermes source，并拒绝可能被 Windows batch wrapper 重解释的动态参数。

token 不包含凭据。未提供 `--source-ref` 时，它不 pin Hermes 远端 commit；提供时仅绑定指定的
40 位 commit SHA，仍不能替代来源审查。最终本地快照后到外部宿主消费路径前，同权限进程仍可能修改
目录；目录、内容、source、source ref 或 token 改变时必须重新 preview/validate/render。

## 明确的宿主风险

- 安装本项目 `agent-skillopt` 的远程命令会访问网络：Codex 的 `codex plugin marketplace add`、
  `codex plugin add`，Claude Code 的 `claude plugin marketplace add --scope user`、`claude plugin install
  --scope user --yes`，以及 Hermes 的 `plugins install`。它们都会改变用户级 marketplace、缓存或插件
  状态；Hermes 的 `enable` 另会启用插件。2026-08-25 的上一版 `v0.2.1` 实际 Codex/Claude/Hermes 安装（Hermes 的
  `allow_tool_override: false`）和 OpenClaw 缺失证据记录在[兼容性矩阵](compatibility.md)；这些只证明
  对应步骤/元数据，不证明 Skill 运行。
- `main` 是可变分支；远端内容可在同一 branch ref 下漂移。Codex 当前本地 CLI 支持 `--ref`，但
  Claude 的远程 GitHub 简写使用默认分支（当前为 `main`），不能把两端表述为相同的 ref 语义；Claude
  远程 marketplace source 只支持 branch/tag ref，不承诺能以 commit SHA 固定安装。release tag 同样
  是 Git ref，不天然不可变，只有受保护且受信任时才可使用；应在 release notes 中记录并复核其解析
  的 40 位 commit SHA，以审计和验证精确内容身份。依据 Claude Code 官方插件契约，Git marketplace
  可能会按其设置在后台刷新；初始配置后，即使没有新的明确用户命令，也可能发生远程获取。显式安装或
  更新同样会访问网络并改变宿主状态。本轮单机快照包括指定的 marketplace/plugin update，但不包含后续
  refresh/update 或 Skill 实际运行；Claude Code 的上一版 `v0.2.1` 更新需要重启后才会生效。
- 远程仓库 bootstrap 与本地生成 bundle 的安装计划不同：`scaffold_bundle.py install` 仍只为已经
  创建并离线验证的本地 bundle 渲染计划，不会安装此仓库的远程 marketplace source。
- Codex 与 Claude Code 的本地 bundle marketplace/add/install 同样改变用户级配置或缓存。
- Hermes 的 Git install 会获取远程内容，`enable` 会改变外部宿主状态；本地生成 bundle 的 `--source-ref`
  仅接受精确 40 位 SHA，并映射到 Hermes `--ref`。未提供该 pin 时，source token 绑定不是内容审计。
- OpenClaw install、inspect、gateway restart 会触及宿主状态或重建网关运行时，且未本机安装验证。

所有安装序列均为非原子多步骤操作：失败可能保留 marketplace、已下载但未启用的插件，或已安装但未
重启的网关。停止后先使用宿主的只读状态查询（Codex `codex plugin list`、Claude Code `claude plugin
list`、Hermes `hermes plugins show <name>`），再依官方文档清理或修复。OpenClaw 未本机安装验证，本文
不提供未经验证的检查、移除或修复命令。

发布远程内容时，`pyproject.toml`、`src/agent_skillopt/__init__.py`、根 `plugin.json`、
`.codex-plugin/plugin.json` 与 `.claude-plugin/plugin.json` 的静态 `version` 必须同步递增，并记录
解析后的 40 位 commit SHA。否则旧版本标识可能让宿主保留过期内容。

离线验证成功后仍必须由操作者另行批准，用新渲染 token 执行。可渲染命令或结构 `VALID` 都不
代表已安装、已启用或安全运行。
