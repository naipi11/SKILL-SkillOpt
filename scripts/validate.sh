#!/usr/bin/env bash
set -euo pipefail

python -m compileall src skills/agent-skillopt/scripts
python -m pytest tests -v
python scripts/validate_bundle.py .
python -m ruff check src tests skills/agent-skillopt/scripts
