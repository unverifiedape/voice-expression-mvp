#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/voice-expression-mvp
SERVICE_NAME=voice-expression
PORT=8010

sudo apt update
sudo apt install -y python3-venv python3-pip ffmpeg nginx

sudo mkdir -p "$APP_DIR"
sudo chown -R ubuntu:ubuntu "$APP_DIR"

# Copy current project files into target dir.
rsync -av --delete ./ "$APP_DIR"/ --exclude venv --exclude .git --exclude __pycache__

cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt

sudo cp voice-expression.service /etc/systemd/system/${SERVICE_NAME}.service
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

sudo cp nginx.voice-expression.conf /etc/nginx/sites-available/${SERVICE_NAME}
sudo ln -sf /etc/nginx/sites-available/${SERVICE_NAME} /etc/nginx/sites-enabled/${SERVICE_NAME}
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "Done. Health check: curl http://127.0.0.1:${PORT}/health"
echo "Public page: http://YOUR_SERVER_IP/"
