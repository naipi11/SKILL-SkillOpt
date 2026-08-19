# 贡献指南

欢迎提交问题、文档修正和代码改进。请先阅读 README、兼容矩阵与安全政策。

## 基本规则

1. 不提交 API 密钥、真实任务轨迹、用户数据或含密钥的日志。
2. 不修改或 vendoring Microsoft SkillOpt 上游源码；集成逻辑必须留在本仓库。
3. 新的行为改动先增加会失败的 pytest，再写最小实现。
4. 所有声明的兼容性必须有 CI 或可复现的手工验证证据。
5. 任何付费或数据外发测试都需要维护者针对模型、预算、并发和数据范围的明确批准。

提交前运行：

    python -m compileall src
    python -m pytest tests -v
    python -m ruff check src tests
    bash -n scripts/validate.sh
