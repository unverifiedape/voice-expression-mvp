# V1.7.1 高危发言榜 + 听原声

本版本在当前运行版基础上新增：

- 首页「查看今日高危发言 →」进入 `/ranking.html`
- 新增高危发言榜页面 `static/ranking.html`
- 新增后端接口 `/api/ranking`
- 榜单按伤人指数排序，展示已生成分享链接的原声
- 每条榜单支持「听原声」和「打开分享页」
- 保留现有录音、分析、分享图、复制听声音链接、analytics 埋点逻辑

## 覆盖文件

直接覆盖项目目录：

```bash
/opt/voice-expression-mvp/app/main.py
/opt/voice-expression-mvp/static/index.html
/opt/voice-expression-mvp/static/ranking.html
```

## 上线后重启

```bash
cd /opt/voice-expression-mvp
python3 -m py_compile app/main.py
sudo systemctl restart voice-expression
sudo systemctl reload nginx
```

## 访问

首页：

```text
https://showmecard.com/
```

高危发言榜：

```text
https://showmecard.com/ranking.html
```

API：

```text
https://showmecard.com/api/ranking
```

## 注意

榜单只读取 `shares/*.json` 中已经生成分享链接的音频。用户只录音但没有生成分享图/复制听声音链接时，不会进入榜单。
