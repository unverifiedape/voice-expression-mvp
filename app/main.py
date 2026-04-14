from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.analyzer import AudioAnalysisError, analyze_voice

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Voice Expression MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/analyze-voice")
async def analyze_voice_api(audio: UploadFile = File(...)) -> dict:
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

    try:
        result = analyze_voice(raw_bytes=raw_bytes, filename=audio.filename)
    except AudioAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"音频处理失败：{exc}") from exc

    return {"ok": True, "result": result}
