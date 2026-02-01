#!/usr/bin/env bash
set -euo pipefail

# PreGrade ML-friendly venv (Python 3.10)
# Needed because onnxruntime/torch wheels may not exist for Python 3.13 yet.

PY=/usr/local/bin/python3.10
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

cd "$ROOT_DIR"

if [ ! -x "$PY" ]; then
  echo "Python 3.10 not found at $PY"
  exit 1
fi

rm -rf .venv
$PY -m venv .venv
source .venv/bin/activate

python --version
pip install -U pip
pip install -r requirements.txt

echo "Done. Activate with: source .venv/bin/activate"