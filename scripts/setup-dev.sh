#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

rm -rf .venv
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir --no-compile ".[dev]"

cat > .venv/bin/score2logic <<PY
#!$ROOT_DIR/.venv/bin/python
from pathlib import Path
import sys

repo_src = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(repo_src))

from score2logic.cli import app

if __name__ == "__main__":
    sys.argv[0] = sys.argv[0].removesuffix(".exe")
    sys.exit(app())
PY
chmod +x .venv/bin/score2logic

echo "score2logic dev environment is ready."
echo "Run: source .venv/bin/activate"
