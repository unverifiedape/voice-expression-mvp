#!/usr/bin/env bash
set -euo pipefail
APP=/opt/voice-expression-mvp
TOKEN="${1:-change-this-token}"
cd "$APP"
python3 -m py_compile app/main.py
sudo cp voice-expression.service /etc/systemd/system/voice-expression.service
sudo cp nginx.voice-expression.conf /etc/nginx/sites-available/voice-expression
sudo ln -sf /etc/nginx/sites-available/voice-expression /etc/nginx/sites-enabled/voice-expression
sudo sed -i "s/ANALYTICS_ADMIN_TOKEN=.*/ANALYTICS_ADMIN_TOKEN=${TOKEN//\//\\/}\"/" /etc/systemd/system/voice-expression.service
sudo systemctl daemon-reload
sudo nginx -t
sudo systemctl restart voice-expression
sudo systemctl reload nginx
sudo systemctl status voice-expression --no-pager -l
printf "\nOK. Analytics: https://showmecard.com/admin/analytics?token=%s\n" "$TOKEN"
