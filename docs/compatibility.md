# 兼容性矩阵

本表只记录已经执行过的本地验证，或已配置且实际由 CI 执行过的组合。未列出的
系统、Agent 宿主、模型或上游提交均不应被理解为受支持。

## 当前验证证据

| 层级 | 组合 | 证据 | 状态 |
| --- | --- | --- | --- |
| 本地开发 | Windows + Python 3.11 | 本仓库离线 pytest 与静态验证 | 已验证 |
| 上游集成目标 | Microsoft SkillOpt 9c776fcb51ae681c046d6f619b55e5f337d4f900 | 需要 scripts/train.py、SearchQA config 与 openai_compatible_backend.py | 配置目标，待本地检出验证 |
| 提供商 | HTTPS OpenAI-compatible endpoint | 仅接口契约；未进行付费 live 测试 | 未验证 |

## CI 覆盖计划

仓库 CI 定义 Windows 和 Ubuntu 上的 Python 3.10、3.12 编译、测试与 Ruff，并在
Ubuntu 验证 shell 脚本语法。CI 尚未在远端运行之前，这些条目不是已验证的兼容性
声明。

## 不在承诺范围内

- 不承诺 PyPI SkillOpt v0.2.0 能使用本项目的 OpenAI-compatible 训练路径。
- 不承诺任意模型、端点或别名都具有相同行为。
- 不承诺 SKILL.md 在所有 Agent 宿主、IDE 或运行器中产生相同的行为。
- 不承诺未知的上游提交；doctor 会把特征缺失判为错误，把不同的提交判为未验证。

新增兼容条目时，请记录操作系统、Python 版本、Agent-SkillOpt 版本、上游 revision、
实际运行命令的脱敏版本，以及测试或 CI 证据。
