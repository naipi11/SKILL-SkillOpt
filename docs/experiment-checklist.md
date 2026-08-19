# 实验检查清单

## 开始前：本地、无网络

- [ ] `agent-skillopt doctor --config agent-skillopt.yaml` 没有 error。
- [ ] `agent-skillopt run --config agent-skillopt.yaml --dry-run` 已检查渲染命令。
- [ ] Microsoft SkillOpt 本地检出与兼容基线
  `9c776fcb51ae681c046d6f619b55e5f337d4f900` 已核对。
- [ ] 数据路径、授权范围、数据版本和保留要求已记录。
- [ ] YAML、命令行、运行目录和 Git 历史中均没有密钥值。

## 若要真实联网运行

- [ ] 已单独批准模型名称、最大预算、并发数和停止条件。
- [ ] 已单独批准将会发送到提供商的数据、轨迹和样本范围。
- [ ] 已核对提供商的数据处理、区域、保留和计费政策。
- [ ] 密钥只在父进程环境中以配置声明的环境变量名提供。
- [ ] 运行命令显式带有 `--allow-network`。

## 结果与报告

- [ ] 运行目录有脱敏的 `manifest.json`。
- [ ] 每个已报告分数都有明确 `samples`；holdout 尤其如此。
- [ ] `baseline` / `candidate` 没有与 `holdout` 的最终结论混用。
- [ ] 成本只记录已知值；未知成本保持 `null`，不估算。
- [ ] 使用 `agent-skillopt report --run-dir <run-directory>` 生成本地报告。
- [ ] 报告的证据警告已在指标结论之前阅读和保留。
