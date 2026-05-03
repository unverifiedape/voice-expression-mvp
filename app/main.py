from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from urllib.parse import unquote

import qrcode
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.analyzer import AudioAnalysisError, analyze_voice

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
SHARES_DIR = BASE_DIR / "shares"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
SHARES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Voice Expression MVP V1.6")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


def _safe_suffix(filename: str | None, content_type: str | None = None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".webm", ".mp3", ".m4a", ".mp4", ".wav", ".ogg", ".aac"}:
        return suffix
    if content_type:
        if "mp4" in content_type or "m4a" in content_type:
            return ".m4a"
        if "ogg" in content_type:
            return ".ogg"
        if "wav" in content_type:
            return ".wav"
    return ".webm"


def _check_audio(audio: UploadFile) -> None:
    if not audio.filename:
        raise HTTPException(status_code=400, detail="缺少音频文件。")
    if audio.content_type and not (
        audio.content_type.startswith("audio/")
        or audio.content_type in {"video/webm", "application/octet-stream"}
    ):
        raise HTTPException(status_code=400, detail="请上传音频文件。")


def _load_share(share_id: str) -> dict:
    if not share_id or "/" in share_id or ".." in share_id:
        raise HTTPException(status_code=400, detail="无效分享ID。")
    meta_path = SHARES_DIR / f"{share_id}.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="分享不存在或已过期。")
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="分享数据损坏。") from exc


@app.get("/health")
def health() -> dict:
    return {"ok": True, "version": "v1.6-viral", "static": str(STATIC_DIR)}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/s.html")
def share_page() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "s.html",
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
    _check_audio(audio)
    raw_bytes = await audio.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="空音频文件。")

    suffix = _safe_suffix(audio.filename, audio.content_type)
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


@app.post("/api/upload")
async def upload_share_audio(
    audio: UploadFile = File(...),
    meta: str = Form(default="{}"),
) -> dict:
    """Create a viral share id: audio + result metadata."""
    _check_audio(audio)
    raw_bytes = await audio.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="空音频文件。")

    share_id = uuid.uuid4().hex[:16]
    suffix = _safe_suffix(audio.filename, audio.content_type)
    filename = f"{share_id}{suffix}"
    audio_path = UPLOADS_DIR / filename
    audio_path.write_bytes(raw_bytes)

    try:
        meta_obj = json.loads(meta or "{}")
        if not isinstance(meta_obj, dict):
            meta_obj = {}
    except Exception:
        meta_obj = {}

    payload = {
        "id": share_id,
        "filename": filename,
        "audio_url": f"/api/audio?id={share_id}",
        "meta": meta_obj,
    }
    (SHARES_DIR / f"{share_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return {"ok": True, "id": share_id, "audio_url": payload["audio_url"], "share_url": f"/s.html?id={share_id}"}


@app.get("/api/share")
def get_share(id: str = Query(..., min_length=1)) -> JSONResponse:
    payload = _load_share(id)
    return JSONResponse(payload, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/api/audio")
def get_audio(id: str = Query(..., min_length=1)) -> FileResponse:
    payload = _load_share(id)
    filename = payload.get("filename")
    if not filename or "/" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="音频不存在。")
    audio_path = UPLOADS_DIR / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="音频不存在。")
    return FileResponse(
        audio_path,
        media_type="audio/webm",
        headers={"Cache-Control": "public, max-age=604800"},
    )
