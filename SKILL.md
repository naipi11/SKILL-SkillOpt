---
name: skillopt-trainer
description: "用 DeepSeek API 训练 SkillOpt agent skill，从零到 best_skill.md"
version: 2.3.0
author: naipi11
license: MIT
metadata:
  tags: [skillopt, prompt-optimization, deepseek, skill-learning, agent-training]
  platforms: [linux, macos, windows]
---

# SkillOpt + DeepSeek — 通用训练指南

用微软 SkillOpt 框架 + DeepSeek API 训练可部署的自然语言 skill 文档。
不需要 Azure、不需要 GPU、不需要本地模型——纯 API 调用。

## Agent 行为（加载此 Skill 时执行）

加载此 Skill 后，**必须进入交互流程**，不要直接跑命令。按以下顺序引导用户：

### Step 1 — 确认环境

检查本地是否已有 SkillOpt 仓库和 venv。如果没有，引导用户克隆安装。

### Step 2 — 选择训练目标

```
1. SearchQA — 阅读理解（已有数据模板，最快上手）
2. 其他内置 benchmark — DocVQA / SpreadsheetBench / ALFWorld 等
3. 自定义任务 — 我自己的场景（客服/代码审查/SQL/翻译/...）
```

根据用户选择，进入对应分支。

### Step 3 — 准备数据

- **选 SearchQA**：从 HuggingFace 下载 + `convert_searchqa.py` 转换。**关键：取至少 5000 条**，否则 train 太少 Optimizer 吃不饱
- **选其他内置 benchmark**：告知数据格式，确认用户有数据
- **选自定义任务**：引导按 `env_template` 写 adapter（`rollout()` + `loader`）

### Step 4 — 确认超参

根据数据量推荐（train 量是关键）：

| train 量 | batch_size | learning_rate | 预期 steps/epoch |
|----------|-----------|---------------|-----------------|
| < 200 | 数据的 ~10% | 3~4 | 8~12 |
| 200~500 | 20~50 | 4~5 | 10~15 |
| 500~2000 | 50~100 | 5~6 | 10~20 |
| 2000+ | 100~200 | 6~8 | 10~20 |

通用：epochs=3, lr_scheduler=cosine, analyst_workers=8。

**数据量红线**：train < 200 条时 Optimizer 很难从有限样本中提炼可泛化规则。如果能扩大数据，优先扩大而非调参。

### Step 5 — 启动训练

```bash
# CLI
python scripts/train.py --config configs/searchqa/deepseek.yaml --num_epochs 3

# WebUI
pip install gradio && python -m skillopt_webui.app --port 7860
```

训练中查看进度：
```bash
cat outputs/<run>/runtime_state.json | python3 -m json.tool
# 看 last_completed_step
```

### Step 6 — 解读结果

训练结束后读 `summary.json`。**建议重命名 skill 避免多任务混淆：**

```bash
cp outputs/<run>/best_skill.md outputs/searchqa-v1.md
```

```bash
python3 -c "
import json
s=json.load(open('outputs/<run>/summary.json'))
print(f'Best val: {s[\"best_selection_hard\"]:.4f}')
print(f'Test:     {s[\"test_hard\"]:.4f}')
print(f'Baseline: {s[\"baseline_test_hard\"]:.4f}')
print(f'Delta:    {s[\"test_delta_hard\"]:+.4f}')
print(f'Steps: {s[\"total_steps\"]}  Accepts: {s[\"total_accepts\"]}  Rejects: {s[\"total_rejects\"]}')
"
```

**判断成功**：test_hard > baseline_test_hard，delta 正数且 > 2%。如果 delta < 2% 或 Accept < 2 次，大概率是 train 数据量不足。

### Step 7 — 部署到任意 Agent

`best_skill.md` 是纯 Markdown。一句命令：

```bash
# Hermes
git clone https://github.com/naipi11/SKILL-SkillOpt.git ~/.hermes/skills/skillopt-trainer
# Claude Code
git clone https://github.com/naipi11/SKILL-SkillOpt.git ~/.claude/skills/skillopt-trainer
# Codex / OpenClaw / OpenCode
git clone https://github.com/naipi11/SKILL-SkillOpt.git ~/.<agent>/skills/skillopt-trainer
```

---

## 底层参考

### 前置条件

```bash
git clone https://github.com/microsoft/SkillOpt.git && cd SkillOpt
python3 -m venv venv && source venv/bin/activate && pip install -e .
export OPENAI_API_KEY=***   export OPENAI_BASE_URL="https://api.deepseek.com"
```

**打代码补丁（必需）：** `skillopt/model/azure_openai.py` 的 `_make_client()`——endpoint 为空时回退到 `OpenAI()`。共需改 4 处类型标注。

### 数据准备

```bash
# 下载
curl -L -o data/searchqa_raw/train.zip \
  "https://huggingface.co/datasets/kyunghyuncho/search_qa/resolve/main/data/train_test_val/train.zip"

# 转换（≥5000 条，保证 train 足够大）
python scripts/convert_searchqa.py data/searchqa_raw/train.zip data/split 5000 "2:1:7"
```

### 配置模板

`configs/searchqa/deepseek.yaml`：
```yaml
_base_: ../_base_/default.yaml
model:
  backend: openai_chat
  optimizer: deepseek-v4-pro
  target: deepseek-v4-flash
  reasoning_effort: high
  azure_openai_endpoint: ""
train:
  train_size: 0
  batch_size: 80
gradient:
  minibatch_size: 4
  merge_batch_size: 4
  analyst_workers: 8
optimizer:
  learning_rate: 5
  lr_scheduler: cosine
env:
  name: searchqa
  split_mode: split_dir
  split_dir: data/split
  workers: 4
```

### 自定义 Benchmark

复制 `skillopt/envs/_template`，实现 env.py（`rollout` + `evaluate`）和 loader.py（`load_raw_items`），注册即可。适用于任何「输入 → LLM → 评分」的任务。

### 已知坑

1. **数据量是第一瓶颈**——实测：5000 条源数据 (1000 train) → +9%；500 条 (100 train) → +1.4%。Optimizer 需要足够的失败样本才能提炼可泛化规则
2. 代码补丁必须打，否则只认 Azure
3. val < 30 条 Gate 不可靠；val 越大 Gate 越准
4. reasoning_effort 同时传给两个模型，Flash 可能报错——报错就关
5. epoch > 4 边际递减，实测 epoch 3 后基本收敛
6. **WebUI 重启 = 训练被杀**——独立进程，不要在训练期间重启 WebUI
7. 模型名 `deepseek-chat`/`deepseek-reasoner` 将于 2026/07 弃用，用 `deepseek-v4-pro`/`deepseek-v4-flash`
8. DeepSeek 国内直连，不需要代理
