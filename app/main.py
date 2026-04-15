from pathlib import Path
import io

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import qrcode

from app.analyzer import analyze_audio

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Voice Expression MVP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/analyze")
async def api_analyze(
    file: UploadFile = File(...),
    sentence: str = Form(default="")
):
    try:
        raw = await file.read()
        if not raw:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "空音频，未读取到录音内容。"},
            )

        result = analyze_audio(raw, filename=file.filename or "recording.webm")

        return {
            "ok": True,
            "sentence": sentence,
            "result": result,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": f"音频处理失败：{e}"},
        )


@app.get("/qr")
def generate_qr(url: str = "http://13.215.87.153"):
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")
