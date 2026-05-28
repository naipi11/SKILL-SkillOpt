# SkillOpt Trainer

用 DeepSeek API 一键训练 AI Agent 的 skill 文档——像训练神经网络一样优化 prompt。

## 安装

```bash
# Hermes
git clone https://github.com/naipi11/SKILL-SkillOpt.git ~/.hermes/skills/skillopt-trainer

# Claude Code
git clone https://github.com/naipi11/SKILL-SkillOpt.git ~/.claude/skills/skillopt-trainer

# Codex (OpenAI)
git clone https://github.com/naipi11/SKILL-SkillOpt.git ~/.codex/skills/skillopt-trainer

# OpenClaw
git clone https://github.com/naipi11/SKILL-SkillOpt.git ~/.openclaw/skills/skillopt-trainer

# OpenCode
git clone https://github.com/naipi11/SKILL-SkillOpt.git ~/.opencode/skills/skillopt-trainer
```

其他 Agent：clone 后把 `SKILL.md` 放到 agent 的 skill/prompt 目录即可。

## 快速开始

```bash
# 1. 安装 SkillOpt
git clone https://github.com/microsoft/SkillOpt.git && cd SkillOpt
python3 -m venv venv && source venv/bin/activate && pip install -e .

# 2. 配置 DeepSeek
export OPENAI_API_KEY=***   export OPENAI_BASE_URL="https://api.deepseek.com"

# 3. 打补丁（让 SkillOpt 支持非 Azure API）
#    编辑 skillopt/model/azure_openai.py，_make_client() endpoint 为空时回退到 OpenAI()

# 4. 下载 + 转换数据
curl -L -o data/train.zip "https://huggingface.co/datasets/kyunghyuncho/search_qa/resolve/main/data/train_test_val/train.zip"
python scripts/convert_searchqa.py data/train.zip data/split 500 "2:1:7"

# 5. 训练
python scripts/train.py --config configs/searchqa/deepseek.yaml --num_epochs 3
```

产出 `outputs/<run>/best_skill.md`——可部署到任意 agent。

## 原理

```
初始 skill → Target 执行任务 → 失败轨迹 → Optimizer 分析 → 写编辑 → Gate 验证 → 迭代 → 最优 skill
```

不碰模型权重，只优化自然语言。DeepSeek V4 Pro 做 Optimizer，V4 Flash 做 Target。

## 文件

| 文件 | 说明 |
|------|------|
| `SKILL.md` | Agent 交互式完整指南（加载后按 7 步流程引导用户） |
| `scripts/train_quick.sh` | 一键训练脚本（Linux / macOS） |
| `scripts/train_quick.py` | 一键训练脚本（Windows / macOS / Linux） |
| `README.md` | 项目说明 |
