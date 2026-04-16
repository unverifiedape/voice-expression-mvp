from __future__ import annotations

import io
import uuid
from pathlib import Path
from urllib.parse import unquote

import qrcode
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.analyzer import AudioAnalysisError, analyze_voice

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Voice Expression MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/qr")
def qr(url: str = Query(..., min_length=1)) -> Response:
    final_url = unquote(url)
    img = qrcode.make(final_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.post("/api/analyze-voice")
async def analyze_voice_api(
    audio: UploadFile = File(...),
    sentence: str = Form(default=""),
) -> dict:
    if not audio.filename:
        raise HTTPException(status_code=400, detail="缺少音频文件。")

    if audio.content_type and not (
        audio.content_type.startswith("audio/")
        or audio.content_type in {"video/webm", "application/octet-stream"}
    ):
        raise HTTPException(status_code=400, detail="请上传音频文件。")

    raw_bytes = await audio.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="空音频文件。")

    suffix = Path(audio.filename).suffix or ".webm"
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    save_path = UPLOADS_DIR / safe_name
    save_path.write_bytes(raw_bytes)

    try:
        result = analyze_voice(raw_bytes=raw_bytes, filename=audio.filename)
    except AudioAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"音频处理失败：{exc}") from exc

    audio_url = f"/uploads/{safe_name}"
    return {
        "ok": True,
        "result": result,
        "audio_url": audio_url,
        "sentence": sentence,
    }
