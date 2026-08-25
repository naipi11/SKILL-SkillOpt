# 安全边界

## 创建和验证默认离线

`preview` 只在内存中计划文件，`apply` 只在确认后写本地文件，`validate` 只读本地结构。三者
都不读取凭据、不发起网络、不安装依赖，也不执行生成 Skill 的 script、hook 或 resource。
规格、argv、token、文档、测试和日志都不得保存 secret。

创建 token 绑定规范化规格和输出目录。现有目标总是拒绝且不会覆盖用户文件；确认后先写入
目标同级唯一 staging 目录、验证后再发布。异常只清理本次 staging；系统锁导致清理失败时，
必须报告残留路径，不能删除目标或静默忽略。

## 命令计划不是执行

没有 `--execute` 的 `install` 只返回 argv、`network_required` 和确认令牌。执行时不用 shell，
逐个传递已渲染 argv；token 必须匹配重新构造的计划。它绑定宿主、规范路径、目录身份、内容
指纹、argv 与 Hermes source，并拒绝可能被 Windows batch wrapper 重解释的动态参数。

token 不包含凭据，也不 pin Hermes 远端 commit。最终本地快照后到外部宿主消费路径前，同权限
进程仍可能修改目录；目录、内容、source 或 token 改变时必须重新 preview/validate/render。

## 明确的宿主风险

- 远程 marketplace 获取会访问网络，且 Claude Code 的 `/plugin marketplace add`、`/plugin install`、
  `/reload-plugins` 与 Codex 的 `codex plugin marketplace add`、`codex plugin add` 都会改变用户级
  marketplace、缓存或插件状态。当前证据仅覆盖离线清单与 CLI 命令契约，**不**覆盖实际远程安装。
- `main` 是可变分支；远端内容可在同一 branch ref 下漂移。Codex 当前本地 CLI 支持 `--ref`，但
  Claude 的远程 GitHub 简写使用默认分支（当前为 `main`），不能把两端表述为相同的 ref 语义；Claude
  远程 marketplace source 只支持 branch/tag ref，不承诺能以 commit SHA 固定安装。release tag 同样
  是 Git ref，不天然不可变，只有受保护且受信任时才可使用；应在 release notes 中记录并复核其解析
  的 40 位 commit SHA，以审计和验证精确内容身份。刷新或更新不是自动行为，必须由用户显式发起、
  重新审查来源并访问网络；本项目没有测试实际远程刷新、更新或安装。
- 远程仓库 bootstrap 与本地生成 bundle 的安装计划不同：`scaffold_bundle.py install` 仍只为已经
  创建并离线验证的本地 bundle 渲染计划，不会安装此仓库的远程 marketplace source。
- Codex 与 Claude Code 的本地 bundle marketplace/add/install 同样改变用户级配置或缓存。
- Hermes 的 Git install 会获取可变远程内容，`enable` 会改变外部宿主状态；source token 绑定
  不是内容审计。
- OpenClaw install、inspect、gateway restart 会触及宿主状态或重建网关运行时，且未本机安装验证。

离线验证成功后仍必须由操作者另行批准，用新渲染 token 执行。可渲染命令或结构 `VALID` 都不
代表已安装、已启用或安全运行。
