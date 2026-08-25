---
name: agent-skillopt
description: Create review-gated portable Skill packages for coding agents.
---

# Agent-SkillOpt

用此 Skill 创建一个可版本控制、可离线验证的四宿主 Skill 包。创建与验证默认离线；
不得读取密钥、安装依赖、访问网络或执行用户提供的脚本。

## 收集最小规格

一次只询问一个缺失项，并把已回答的完整规格保留在当前对话记忆中。依次收集：

1. 规范化的 Skill 名称。
2. 预期结果与何时应使用此 Skill。
3. 关键约束与授权边界。
4. 项目本地的目标目录。
5. 有意义的离线验证方式。

仅在有明确用途时加入 reference、script、asset 或测试资源；不要默认生成可选资源。
依据 [portable-bundle-contract](references/portable-bundle-contract.md) 和
[skill-authoring-rubric](references/skill-authoring-rubric.md) 组织正文与资源。

## 预览、确认与创建

先解析当前正在阅读的 SKILL.md 的绝对路径，并令 `SKILL_DIRECTORY` 为该文件所在的绝对
目录。不要假定仓库检出目录、当前工作目录或任一宿主的安装路径。将完整 JSON 规格通过
标准输入交给紧邻当前 Skill 的确定性包装器；不要将规格写成临时文件：

```text
<JSON specification> | python <absolute-SKILL-directory>/scripts/scaffold_bundle.py preview --spec -
```

展示预览 JSON 的 `output_directory`、全部 `files` 和 `confirmation_token`。可选资源是
`files` 中的路径条目，不存在顶层 `resources` 字段。随后立即停止，等待用户对该提案做出
明确批准。不得在用户批准前调用 apply。

批准后，使用同一份完整 JSON 规格和预览返回的完全一致令牌：

```text
<JSON specification> | python <absolute-SKILL-directory>/scripts/scaffold_bundle.py apply --spec - --confirm <preview-token>
python <absolute-SKILL-directory>/scripts/scaffold_bundle.py validate --path <created-bundle>
```

令牌缺失、过期、规格或目标目录改变时，重新预览。确定性脚手架不可用时，报告该限制；
绝不能手写包文件作为替代方案。验证失败时不要安装。

## 仅渲染安装计划

离线验证成功后，询问用户选择一个宿主。Codex、Claude 和 OpenClaw 仅渲染本地包计划：

```text
python <absolute-SKILL-directory>/scripts/scaffold_bundle.py install --host <codex|claude|openclaw> --path <created-bundle>
```

Hermes 必须声明明确的 `<owner>/<repository>` Git source；下面命令也只渲染计划，远端内容可变且在实际执行时需要网络。
如需把随后 Hermes 安装固定到已复核的精确内容身份，再提供可选 `--source-ref <40-char-sha>`：

```text
python <absolute-SKILL-directory>/scripts/scaffold_bundle.py install --host hermes --path <created-bundle> --source <owner>/<repository> --source-ref <40-char-sha>
```

说明渲染出的命令和网络边界，参考 [host-installation](references/host-installation.md)。
不得执行安装、启用、检查或重启。只有用户随后单独请求在选定宿主执行该计划，并提供
与该渲染计划匹配的确认令牌时，才可以请求带 `--execute --confirm <install-token>` 的执行。
