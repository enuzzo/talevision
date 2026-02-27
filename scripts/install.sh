#!/usr/bin/env bash
# install.sh — full Pi Zero W setup
# Run as the 'pi' user (NOT root). Uses sudo where needed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔══════════════════════════════════════╗"
echo "║   TaleVision — Pi Zero W Installer   ║"
echo "╚══════════════════════════════════════╝"
echo

echo "[1/5] Installing system dependencies..."
sudo apt-get update -q
sudo apt-get install -y -q \
  python3 python3-pip python3-venv python3-pil \
  ffmpeg \
  libopenjp2-7 libtiff5 \
  fonts-dejavu

echo "[2/5] Enabling SPI (required for Inky display)..."
if ! grep -q "^dtparam=spi=on" /boot/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null; then
  BOOT_CFG="/boot/firmware/config.txt"
  [ -f /boot/config.txt ] && BOOT_CFG="/boot/config.txt"
  echo "dtparam=spi=on" | sudo tee -a "$BOOT_CFG" > /dev/null
  echo "    SPI enabled — reboot required after installation."
else
  echo "    SPI already enabled."
fi

echo "[3/5] Adding pi user to gpio group..."
sudo usermod -aG gpio pi || true

echo "[4/5] Setting up Python venv..."
cd "$PROJECT_DIR"
bash "$SCRIPT_DIR/setup_venv.sh"

echo "[5/5] Installing systemd service..."
bash "$SCRIPT_DIR/install_service.sh"

echo
echo "╔══════════════════════════════════════╗"
echo "║   Installation complete!              ║"
echo "║                                       ║"
echo "║   Next steps:                         ║"
echo "║   1. Add MP4 files to media/          ║"
echo "║   2. Edit config.yaml if needed       ║"
echo "║   3. sudo systemctl start talevision  ║"
echo "║   4. Open http://<pi-ip>:5000         ║"
echo "╚══════════════════════════════════════╝"
