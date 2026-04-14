#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/voice_expression_mvp
PYTHON_BIN=python3
SERVICE_NAME=voice-expression-mvp

sudo apt update
sudo apt install -y ffmpeg python3-venv nginx

sudo mkdir -p "$APP_DIR"
sudo rsync -av --delete ./ "$APP_DIR/"
cd "$APP_DIR"

$PYTHON_BIN -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

sudo tee /etc/systemd/system/${SERVICE_NAME}.service >/dev/null <<EOF
[Unit]
Description=Voice Expression MVP
After=network.target

[Service]
User=root
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${APP_DIR}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

echo "Done. Add Nginx config next."
