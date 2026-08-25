# 可移植包契约

每个生成包必须只有一个规范 Skill：`skills/<name>/SKILL.md`。根 `plugin.json` 采用
Agent Plugins v1，且只包含标准字段；`$schema` 固定为
`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`。根清单必须包含规范化
名称、语义化版本和非空描述；Codex 与 Claude 清单还必须精确指向 `./skills/`。

四个清单表面为根清单、`.codex-plugin/plugin.json`、`.agents/plugins/marketplace.json`、
`.claude-plugin/plugin.json` 与 `.claude-plugin/marketplace.json`。两个 marketplace 都只
能包含一个同名插件条目，并以 `./` 指向包根。若写入 repository、license、author、
homepage、keywords 或 extensions 等可选身份元数据，适配器中的值必须与根清单一致。

离线验证会拒绝缺少文件、清单格式错误、身份漂移、多个 Skill 目录、未完成标记、路径
遍历、符号链接或 Windows reparse point。验证器只检查结构：不会执行 Skill、脚本或
用户提供的内容，也不会读取密钥、联网或安装软件。

创建前先预览，apply 必须使用同一标准化规格生成的精确令牌。目标已存在时必须失败，
不能覆盖。包创建完成后运行其离线验证器；不要用手工文件替换确定性输出。
