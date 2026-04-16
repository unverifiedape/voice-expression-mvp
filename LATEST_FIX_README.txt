这版是最新完整可覆盖版，已修复：
1. pydub.silence.strip_silence 不存在的问题，改为 detect_nonsilent 稳定裁剪。
2. systemd service 改为 python -m uvicorn 启动。
3. service 增加 PATH 与 FFMPEG_BINARY，确保 ffmpeg/ffprobe 可用。
4. 保留当前项目里真实音频分享链路与 challenge audio 参数。

覆盖后请在 AWS 执行：
cd /opt/voice-expression-mvp
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo cp deploy/voice-expression.service /etc/systemd/system/voice-expression.service
sudo systemctl daemon-reload
sudo systemctl restart voice-expression
sudo systemctl restart nginx
curl http://127.0.0.1:8010/health
