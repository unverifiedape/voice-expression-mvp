这份修复包基于你上传的最新版本生成，修复了两处：
1. app/main.py 改为相对导入：from .analyzer import analyze_audio
2. 补回缺失的 app/analyzer.py

本地覆盖后执行：
git add .
git commit -m "fix: restore analyzer and import path"
git push

AWS 执行：
cd /opt/voice-expression-mvp
git pull
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl daemon-reload
sudo systemctl restart voice-expression
sudo systemctl restart nginx
curl http://127.0.0.1:8010/health
