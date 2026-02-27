#!/usr/bin/env bash
# install_service.sh — copy and enable systemd service
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SERVICE_FILE="$PROJECT_DIR/talevision.service"
SERVICE_DEST="/etc/systemd/system/talevision.service"

if [ ! -f "$SERVICE_FILE" ]; then
  echo "ERROR: $SERVICE_FILE not found"
  exit 1
fi

echo "[talevision] Installing systemd service..."
sudo cp "$SERVICE_FILE" "$SERVICE_DEST"
sudo systemctl daemon-reload
sudo systemctl enable talevision

echo "[talevision] Service installed and enabled."
echo "            Start with: sudo systemctl start talevision"
echo "            Logs:       journalctl -u talevision -f"
