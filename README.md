只覆盖原项目的 static/index.html

本地：
1. 用这个包里的 static/index.html 覆盖仓库同名文件
2. git add .
3. git commit -m "feat: viral verdict card update"
4. git push

服务器：
cd /opt/voice-expression-mvp
git pull
sudo systemctl restart voice-expression
sudo systemctl restart nginx
