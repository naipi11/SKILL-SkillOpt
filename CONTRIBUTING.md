# 贡献指南

欢迎贡献跨宿主 Skill 创作工具。所有变更必须保持离线、可审计，并遵守下列规则：

1. 不提交凭据、密钥、用户数据或包含它们的日志。
2. 新行为先写会失败的 pytest，再写最小实现。
3. 安装行为必须得到明确批准；不得把未批准的安装作为测试或默认行为。
4. 所有验证必须离线完成，并附带可复现的测试证据。

提交前运行：

    python -m compileall src
    python -m pytest tests -v
    python scripts/validate_bundle.py .
    python -m ruff check src tests
    bash -n scripts/validate.sh
