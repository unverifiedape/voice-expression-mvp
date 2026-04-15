覆盖以下文件：
1. app/main.py
2. static/index.html
3. requirements.txt

本地执行：
git add .
git commit -m "feat: challenge qr verdict card"
git push

AWS执行：
cd /opt/voice-expression-mvp
git pull
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl restart voice-expression
sudo systemctl restart nginx
