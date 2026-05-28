#!/usr/bin/env python3
"""SkillOpt one-click training — cross-platform (Windows / macOS / Linux)"""
import argparse, json, os, sys, subprocess
from datetime import datetime

parser = argparse.ArgumentParser(description="SkillOpt one-click training — DeepSeek")
parser.add_argument("--config", default="configs/searchqa/deepseek.yaml")
parser.add_argument("--epochs", type=int, default=3)
parser.add_argument("--batch", type=int, default=10)
parser.add_argument("--lr", type=int, default=4)
parser.add_argument("--out", default=f"outputs/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
args = parser.parse_args()

if not os.environ.get("OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY not set.")
    print('  export OPENAI_API_KEY=***   or: set OPENAI_API_KEY=***    sys.exit(1)
if not os.environ.get("OPENAI_BASE_URL"):
    print("WARNING: OPENAI_BASE_URL not set. For DeepSeek:")
    print("  export OPENAI_BASE_URL=https://api.deepseek.com")

if not os.path.isfile("scripts/train.py"):
    print("ERROR: Not in SkillOpt project root. cd to SkillOpt directory first.")
    sys.exit(1)

print("=" * 44)
print("  SkillOpt Training — DeepSeek")
print("=" * 44)
print(f"  Config:  {args.config}")
print(f"  Epochs:  {args.epochs}")
print(f"  Batch:   {args.batch}")
print(f"  LR:      {args.lr}")
print(f"  Out:     {args.out}")
print("=" * 44)

cmd = [
    sys.executable, "scripts/train.py",
    "--config", args.config,
    "--num_epochs", str(args.epochs),
    "--batch_size", str(args.batch),
    "--edit_budget", str(args.lr),
    "--out_root", args.out,
]
subprocess.run(cmd, check=True)

summary_path = os.path.join(args.out, "summary.json")
if os.path.isfile(summary_path):
    with open(summary_path) as f:
        s = json.load(f)
    print(f"\nDone!")
    print(f"Best skill:  {args.out}/best_skill.md")
    print(f"Summary:     {summary_path}")
    print(f"\nBest val: {s['best_selection_hard']:.4f}  |  Test: {s['test_hard']:.4f}  |  Delta: {s['test_delta_hard']:+.4f}")
    print(f"Steps: {s['total_steps']}  |  Accepts: {s['total_accepts']}  |  Rejects: {s['total_rejects']}")
