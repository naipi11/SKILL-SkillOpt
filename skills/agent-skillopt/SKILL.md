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

将完整 JSON 规格通过标准输入交给本 Skill 的确定性包装器；不要将规格写成临时文件：

```text
<JSON specification> | python skills/agent-skillopt/scripts/scaffold_bundle.py preview --spec -
```

展示预览返回的输出目录、全部文件、每项可选资源及确认令牌。随后立即停止，等待用户对该
提案做出明确批准。不得在用户批准前调用 apply。

批准后，使用同一份完整 JSON 规格和预览返回的完全一致令牌：

```text
<JSON specification> | python skills/agent-skillopt/scripts/scaffold_bundle.py apply --spec - --confirm <preview-token>
python skills/agent-skillopt/scripts/scaffold_bundle.py validate --path <created-bundle>
```

令牌缺失、过期、规格或目标目录改变时，重新预览。确定性脚手架不可用时，报告该限制；
绝不能手写包文件作为替代方案。验证失败时不要安装。

## 仅渲染安装计划

离线验证成功后，询问用户选择一个宿主，并仅渲染该宿主的安装计划：

```text
python skills/agent-skillopt/scripts/scaffold_bundle.py install --host <codex|claude|hermes|openclaw> --path <created-bundle>
```

说明渲染出的命令和网络边界，参考 [host-installation](references/host-installation.md)。
不得执行安装、启用、检查或重启。只有用户随后单独请求在选定宿主执行该计划，并提供
与该渲染计划匹配的确认令牌时，才可以请求带 `--execute --confirm <install-token>` 的执行。
