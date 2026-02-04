#!/usr/bin/env bash
set -euo pipefail

# Safe venv bootstrap for PreGrade.
# - Prefers Python 3.10 if installed (onnxruntime wheels), else falls back to python3.
# - DOES NOT delete an existing .venv.

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

PY310=/usr/local/bin/python3.10

if [ -x "$PY310" ]; then
  PY="$PY310"
else
  PY=$(command -v python3 || true)
fi

if [ -z "${PY:-}" ]; then
  echo "python3 not found. Install Python 3.10+ and retry." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating venv at .venv using: $PY"
  "$PY" -m venv .venv
else
  echo "Using existing .venv (will not delete)."
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python --version
pip install -U pip
pip install -r requirements.txt

echo "Done. Activate with: source .venv/bin/activate"