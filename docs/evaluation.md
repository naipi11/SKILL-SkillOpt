# 实验评估与证据规则

`agent-skillopt report` 只读取本地运行目录中的 `manifest.json` 与可选的
`metrics.json`，不会连接模型提供商、读取密钥、估算 token 用量或查询价格表。

## 指标契约

`metrics.json` 的每个指标必须显式提供有限数值的 `score`、正整数的 `samples`，
以及可选的 `cost_usd`。`cost_usd` 只能是 `null` 或显式报告的非负数；工具绝不会
从模型名称、token、价格表或其他线索推导成本。布尔值不属于合法的数值或样本数。

```json
{
  "baseline": {"score": 0.62, "samples": 100, "cost_usd": null},
  "candidate": {"score": 0.68, "samples": 100, "cost_usd": null},
  "holdout": {"score": 0.65, "samples": 120, "cost_usd": null},
  "upstream_summary": {"source": "synthetic-example"}
}
```

上例是合成格式示例，不代表真实模型或数据集表现。完整可复制文件见
`examples/metrics.example.json`。

当没有 `metrics.json`、JSON 无效、顶层不是对象，或某项指标不符合契约时，报告会
保留相应证据警告，不会补出分数、样本数或成本。`holdout` 缺少 `samples` 时不会被
接纳为最终评估证据。

`upstream_summary` 仅作为清晰标记的原始上游摘要字段输出；其中名称含 key、token、
secret、password、authorization 或 credential 的字段会被过滤。不要把密钥、完整端点
或私有样本写入该字段。

## 选择与最终评估的边界

- `baseline` 与 `candidate` 用于开发期间的比较和选择。
- `holdout` 只用于最终评估，不能反过来驱动提示、策略、超参数或候选方案选择。
- 对 holdout 的每一次结果都应同时记录样本数、数据版本和运行 manifest，以避免把
  选择偏差误写成泛化结论。

## 本地生成报告

下面的命令只读写本地文件：

    agent-skillopt report --run-dir runs/example --output-dir reports/example

输出目录会得到 `report.json` 和 `report.md`。如果未指定 `--output-dir`，报告会写入
该运行目录。缺少 `manifest.json` 是输入错误，命令返回状态码 2。

## 付费实验的额外批准

报告命令不授权真实训练或网络调用。开始任意付费 live experiment 前，必须由负责人
单独批准具体模型、最大预算、并发数和可外发的数据范围，并确认提供商的数据处理、
保留与计费条件。
