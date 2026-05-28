#!/usr/bin/env bash
# SkillOpt 一键训练脚本 — DeepSeek
# usage: bash train_quick.sh [--config deepseek.yaml] [--epochs 3] [--batch 10] [--lr 4]
set -euo pipefail

CONFIG="configs/searchqa/deepseek.yaml"
EPOCHS=3
BATCH=10
LR=4
OUT="outputs/run_$(date +%Y%m%d_%H%M%S)"

while [[ $# -gt 0 ]]; do
    case $1 in
        --config)  CONFIG="$2";  shift 2 ;;
        --epochs)  EPOCHS="$2";  shift 2 ;;
        --batch)   BATCH="$2";   shift 2 ;;
        --lr)      LR="$2";      shift 2 ;;
        --out)     OUT="$2";     shift 2 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

# -----------------------------------------------
# 环境检查
# -----------------------------------------------
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: OPENAI_API_KEY not set. Run: export OPENAI_API_KEY=***    exit 1
fi
if [ -z "${OPENAI_BASE_URL:-}" ]; then
    echo "WARNING: OPENAI_BASE_URL not set. If using DeepSeek: export OPENAI_BASE_URL=https://api.deepseek.com"
fi
if [ ! -f "scripts/train.py" ]; then
    echo "ERROR: Not in SkillOpt project root. cd to the SkillOpt directory first."
    exit 1
fi

echo "============================================"
echo "  SkillOpt Training — DeepSeek"
echo "============================================"
echo "  Config:  $CONFIG"
echo "  Epochs:  $EPOCHS"
echo "  Batch:   $BATCH"
echo "  LR:      $LR"
echo "  Out:     $OUT"
echo "============================================"

python scripts/train.py \
    --config "$CONFIG" \
    --num_epochs "$EPOCHS" \
    --batch_size "$BATCH" \
    --edit_budget "$LR" \
    --out_root "$OUT"

echo ""
echo "Done! Results: $OUT"
echo ""
echo "Best skill:  $OUT/best_skill.md"
echo "Summary:     $OUT/summary.json"
echo ""
python3 -c "
import json
s=json.load(open('$OUT/summary.json'))
print(f'Best val: {s[\"best_selection_hard\"]:.4f}  |  Test: {s[\"test_hard\"]:.4f}  |  Δ: {s[\"test_delta_hard\"]:+.4f}')
print(f'Steps: {s[\"total_steps\"]}  |  Accepts: {s[\"total_accepts\"]}  |  Rejects: {s[\"total_rejects\"]}')
"
