# Agent-SkillOpt

面向中文使用者的 Microsoft SkillOpt 集成、诊断、可复现实验与证据报告工具包。

Agent-SkillOpt 是一个轻量集成层：它读取本地 YAML 配置，检查用户自己管理的
SkillOpt 检出，渲染安全的上游调用，并保存脱敏的运行证据。它不 fork 上游优化
核心，不会修改上游文件，也不会默认访问网络、下载数据或消耗模型 API 额度。

## 当前目标

- P0：安装、配置、doctor 与不覆盖已有文件的初始化。
- P1：无网络 dry-run、显式网络门禁与脱敏 manifest。
- P2：不伪造指标的报告、baseline/candidate/holdout 证据契约。

通用 OpenAI-compatible 训练后端以 Microsoft SkillOpt 提交
9c776fcb51ae681c046d6f619b55e5f337d4f900 为首个兼容基线。
PyPI v0.2.0 早于该后端，不能用于此兼容训练路径。

## 安装

需要 Python 3.10 或更高版本。下面的安装步骤只解析 Python 依赖；不会连接模型
提供商，也不会读取或输出任何 API 密钥。

    python -m pip install -e ".[dev]"

## 默认无网络工作流

首先查看命令和创建项目配置：

    agent-skillopt --help
    agent-skillopt init --path .

在准备好本地 SkillOpt 检出和数据目录后，仅做本地检查与命令渲染：

    agent-skillopt doctor --config agent-skillopt.yaml
    agent-skillopt run --config agent-skillopt.yaml --dry-run

dry-run 不启动子进程、不发起网络请求，也不要求已设置密钥。它只显示经过脱敏的
上游命令并提示缺失的非公开前置条件。

## 真正运行前的门禁

只有在你已单独批准以下范围后，才可以使用带有 allow-network 的运行命令：

1. 具体模型、预算与并发。
2. 将要发往提供商的数据、轨迹或样本范围。
3. 提供商的数据处理、保留与计费政策。

运行时仅使用配置中声明的环境变量名（例如 DEEPSEEK_API_KEY）。密钥值不得写入
YAML、命令行、日志、测试、manifest 或 Git 历史。

## 上游与数据

请自行维护 Microsoft SkillOpt 本地检出。Agent-SkillOpt 只检查其路径、版本和所需
文件，绝不自动 clone、patch 或下载。SearchQA 数据准备应调用上游的材料化工具；
本项目不复制基准数据。

## 兼容性与安全

- 已验证和待验证环境见 docs/compatibility.md。
- 数据外发、密钥与漏洞处理见 docs/security.md。
- 实验指标与授权规则见 docs/evaluation.md 和 docs/experiment-checklist.md。
- SKILL.md 只声明已验证的操作契约，不声称可在所有 Agent 宿主中完全一致运行。

## 开发验证

    python -m compileall src
    python -m pytest tests -v
    python -m ruff check src tests
    bash -n scripts/validate.sh

许可证：MIT。Microsoft SkillOpt 的归属与边界见 NOTICE。
