<div align="center">
  <img src="docs/assets/agent-skillopt-hero.gif" alt="Agent-SkillOpt：安全、可复现、证据优先的技能优化流程" width="100%">
</div>

<h1 align="center">Agent-SkillOpt</h1>

<p align="center">用一次明确确认，创建并离线验证可移植的四宿主 Skill 包</p>

<p align="center">
  <a href="https://github.com/naipi11/Agent-SkillOpt/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/naipi11/Agent-SkillOpt/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&amp;logoColor=white">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-2ea44f.svg"></a>
</p>

Agent-SkillOpt 是中文优先的离线 Skill 创作器：一个可移植的 [Agent Plugins v1
核心](https://agent-plugins.org/specification)，加四个薄适配面——Codex marketplace、Claude
Code marketplace、Hermes Agent 便携包、OpenClaw 兼容包发现。创建和验证不会发起网络、读取
secret、安装依赖或执行生成 Skill 的脚本。

## 安全工作流

唯一流程是：自然语言 brief → stdin `preview` → 检查返回的目录、文件、token →
**一次明确确认** → 精确 `apply` → 离线 `validate` → 为所选宿主渲染 `install`。实际宿主执行
是单独的外部状态变更，必须再次明确请求并提供与新安装计划匹配的 token。

以下是「写发布说明」的本地 preview。源检出中 `$skillDirectory` 是仓库的绝对路径；在已安装
插件中，必须改为当前所用 `SKILL.md` 所在的绝对目录，不能假设当前目录或检出位置。

```powershell
$skillDirectory = (Resolve-Path .\skills\agent-skillopt).Path
$bundleRoot = Join-Path (Get-Location) 'out\release-notes'
$spec = @'
{
  "name": "release-notes",
  "description": "从已核实的变更起草简洁发布说明。",
  "body": "先收集已核实的变更，再起草发布说明。",
  "output_directory": "REPLACE_WITH_ABSOLUTE_BUNDLE_ROOT"
}
'@.Replace('REPLACE_WITH_ABSOLUTE_BUNDLE_ROOT', $bundleRoot.Replace('\\', '\\\\'))
$spec | python "$skillDirectory\scripts\scaffold_bundle.py" preview --spec -
```

检查返回 JSON 的 `output_directory`、`files` 和 `confirmation_token`。预览不会创建输出目录；
可选 resource 没有顶层 `resources` 字段，而是 `files` 中的资源路径条目。只有它们完全正确时，
才原样使用该 token：

```powershell
$spec | python "$skillDirectory\scripts\scaffold_bundle.py" apply --spec - --confirm <preview-token>
python "$skillDirectory\scripts\scaffold_bundle.py" validate --path "$bundleRoot"
```

`apply` 不覆盖现有目录。它在同级唯一 staging 目录写入并验证，随后才无覆盖发布；失败会清理
自己的 staging（受系统锁阻止时会报告残留路径）。验证失败时不要安装。

## 仅渲染安装计划

Codex、Claude 和 OpenClaw 的本地包计划不需要 source；下面命令只返回 argv 数组、网络标记和
安装 token，属于 **PLAN ONLY**：

```powershell
python "$skillDirectory\scripts\scaffold_bundle.py" install --host <codex|claude|openclaw> --path "$bundleRoot"
```

Hermes 必须提供明确的 `<owner>/<repository>` Git source；这同样只渲染计划，不访问网络或执行宿主命令：

```powershell
python "$skillDirectory\scripts\scaffold_bundle.py" install --host hermes --path "$bundleRoot" --source <owner>/<repository>
```

每一步是一个 argv 元组，路径永远是一个参数而不是 shell 拼接。`<bundle-root>` 必须替换为
已经 preview/validate 的绝对目录，`release-notes` 替换为规范化包名；以下命令严格对应
`build_install_plan` 的渲染：

| 宿主 | 计划 argv（只能在后续独立确认后执行） |
| --- | --- |
| [Codex](https://help.openai.com/en/articles/20001256-plugins-in-codex/) | `codex plugin marketplace add <bundle-root>`<br>`codex plugin add release-notes@release-notes` |
| [Claude Code](https://code.claude.com/docs/en/plugins-reference) | `claude plugin marketplace add <bundle-root>`<br>`claude plugin install release-notes@release-notes` |
| [Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins) | `hermes plugins install <owner>/<repository> --no-enable`<br>`hermes plugins enable release-notes` |
| [OpenClaw](https://docs.openclaw.ai/plugins/bundles) | `openclaw plugins install <bundle-root>`<br>`openclaw plugins inspect release-notes`<br>`openclaw gateway restart` |

Hermes 需要明确的 `<owner>/<repository>` Git source（不是裸索引名、本地路径或 URL），会访问网络且远程内容可变。**Hermes Git install/enable
和 OpenClaw gateway restart 都是外部状态变更，绝不能因“渲染计划”自动执行。** Codex 与
Claude 的 marketplace/add/install 也会改变用户级宿主状态。安装 token 绑定宿主、已验证路径、
内容快照、命令及 Hermes source，但不 pin 远端 commit，也不能替代权限和来源审查。

## 本地验证

```powershell
python -m compileall src
python -m pytest tests -v
python scripts/validate_bundle.py .
python -m ruff check src tests
```

CI 在 Windows 与 Ubuntu 的 Python 3.10、3.12 执行离线检查，且不会下载宿主 CLI。请阅读
[兼容性矩阵](docs/compatibility.md)、[安全边界](docs/security.md) 与
[0.2.0 迁移说明](docs/migration-v0.2.md)。许可证：MIT。
