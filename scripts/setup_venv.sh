#!/usr/bin/env bash
# setup_venv.sh — create Python venv and install dependencies
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "[talevision] Creating virtual environment..."
python3 -m venv venv

echo "[talevision] Installing requirements..."
venv/bin/pip install --upgrade pip wheel
venv/bin/pip install -r requirements.txt

echo "[talevision] Done. Activate with: source venv/bin/activate"
