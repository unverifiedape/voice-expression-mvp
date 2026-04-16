# Voice Expression MVP

一个最小可跑的语音表达测试示例：
- 用户在前端选择一句固定文本并录音
- 后端统一转码、裁切静音、做音量归一化
- 提取基础声学特征并映射到 4 种表达类型

## 类型
- 冷静控制型
- 热情外放型
- 试探犹豫型
- 直接强势型

## 本地运行

### 1. 安装系统依赖
Linux / Ubuntu:

```bash
sudo apt update
sudo apt install -y ffmpeg python3-venv
```

### 2. 创建虚拟环境并安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### 3. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

打开：

```text
http://127.0.0.1:8000
```

## API

### 健康检查

```bash
curl http://127.0.0.1:8000/health
```

### 分析接口
字段名固定为 `audio`

```bash
curl -X POST http://127.0.0.1:8000/api/analyze-voice \
  -F "audio=@/path/to/sample.webm"
```

## 目录

```text
voice_expression_mvp/
├── app/
│   ├── analyzer.py
│   └── main.py
├── static/
│   └── index.html
├── requirements.txt
└── README.md
```

## 生产部署建议

最简单路线：
- 1 台 Ubuntu 云服务器
- 2C / 4G 就够 MVP
- 用 uvicorn + systemd 跑服务
- 用 Nginx 反代到 127.0.0.1:8000

## 风险和说明
- 第一版没有做复杂降噪，只做了裁静音与基础归一化
- 第一版只适合固定句式测试，不适合开放式自由说话
- 如果浏览器不支持 `audio/webm`，可以改前端录音策略或引入备用录音库
