# <skill-name>

一句话描述此 Skill 的明确结果和触发场景。

## 使用

说明所需输入、授权边界、产生的输出，以及可离线复现的验证命令。

## 资源

只列出该 Skill 实际使用的包内 resources；未使用时删除本节。

## 测试案例与评估

在 `tests/cases/` 中保存至少一个离线案例，并为每个案例声明 prompt、
required_contains 和 forbidden_contains。先运行静态安全审查，再将单独收集的响应交给
`agent-skillopt evaluate --path . --responses responses.json` 评分。
