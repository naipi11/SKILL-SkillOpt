#!/usr/bin/env bash
set -euo pipefail

python -m compileall src
python -m pytest tests -v
python -m ruff check src tests
