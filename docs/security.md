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

- Codex 与 Claude Code 的 marketplace/add/install 改变用户级配置或缓存。
- Hermes 的 Git install 会获取可变远程内容，`enable` 会改变外部宿主状态；source token 绑定
  不是内容审计。
- OpenClaw install、inspect、gateway restart 会触及宿主状态或重建网关运行时，且未本机安装验证。

离线验证成功后仍必须由操作者另行批准，用新渲染 token 执行。可渲染命令或结构 `VALID` 都不
代表已安装、已启用或安全运行。
