# 迁移到 0.2.0

0.2.0 改为离线、确认门控的跨宿主 Skill 包创作器。旧训练、provider、配置、doctor、run、report
和实验文档不再属于本产品接口，也没有自动迁移工具。

`bcbad16` 是 main 进入 0.2.0 前的最后一个提交。必须保留旧接口的项目应将依赖明确 pin 到
自己验证过的 `0.1.x` revision；若要精确恢复这条旧 main 历史，可使用 `bcbad16`，不要继续
跟随 main：

```text
git checkout bcbad16
# 或在锁文件/子模块中固定经验证的 0.1.x revision
```

迁移时不要迁入旧配置、环境变量、provider endpoint、训练数据或运行报告。改为收集新 Skill 的
brief，执行 `preview`、检查文件与 token、确认一次 `apply`、离线 `validate`；宿主安装仍须另行
批准。已退休的评估和实验检查清单不能作为 0.2.0 的承诺。
