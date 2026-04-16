这份是完整可覆盖版，包含：
- app/main.py
- app/analyzer.py
- static/index.html
- requirements.txt
- deploy/voice-expression.service
- deploy/voice-expression.conf

核心变化：
1. 保留真实语音分析（librosa + pydub）
2. 上传录音后保存到 /uploads
3. 后端返回 audio_url
4. 分享链接携带真实音频 URL
5. 扫码进入挑战页可播放原始录音
6. 保留二维码分享卡

本地覆盖后：
git add .
git commit -m "feat: full audio share flow"
git push

AWS 更新：
cd /opt/voice-expression-mvp
git pull
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo cp deploy/voice-expression.service /etc/systemd/system/voice-expression.service
sudo cp deploy/voice-expression.conf /etc/nginx/sites-available/voice-expression.conf
sudo ln -sf /etc/nginx/sites-available/voice-expression.conf /etc/nginx/sites-enabled/voice-expression.conf
sudo systemctl daemon-reload
sudo systemctl restart voice-expression
sudo systemctl restart nginx

验证：
curl http://127.0.0.1:8010/health
