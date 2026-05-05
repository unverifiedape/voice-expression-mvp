from __future__ import annotations

import io
import json
import uuid
import os
import sqlite3
import time
import html
from pathlib import Path
from urllib.parse import unquote

import qrcode
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, Request
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

ANALYTICS_DB = BASE_DIR / "analytics.db"
ADMIN_TOKEN = os.getenv("ANALYTICS_ADMIN_TOKEN", "").strip()

def _analytics_conn():
    conn = sqlite3.connect(ANALYTICS_DB)
    conn.row_factory = sqlite3.Row
    return conn

def _init_analytics_db() -> None:
    conn = _analytics_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            path TEXT DEFAULT '',
            sid TEXT DEFAULT '',
            data TEXT DEFAULT '{}',
            ip TEXT DEFAULT '',
            ua TEXT DEFAULT '',
            referrer TEXT DEFAULT '',
            ts INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_event_ts ON events(event, ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_sid_ts ON events(sid, ts)")
    conn.commit()
    conn.close()

def _client_ip(request: Request | None) -> str:
    if request is None:
        return ""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:80]
    return (request.client.host if request.client else "")[:80]

def _record_event(event: str, data: dict | None = None, request: Request | None = None, path: str = "", sid: str = "") -> None:
    try:
        payload = data or {}
        sid = str(sid or payload.get("sid") or payload.get("id") or "")[:80]
        if request is not None and not path:
            path = str(request.url.path)[:240]
        conn = _analytics_conn()
        conn.execute(
            "INSERT INTO events(event,path,sid,data,ip,ua,referrer,ts) VALUES(?,?,?,?,?,?,?,?)",
            (
                str(event)[:80],
                str(path or "")[:240],
                sid,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:6000],
                _client_ip(request),
                (request.headers.get("user-agent", "")[:500] if request else ""),
                (request.headers.get("referer", "")[:500] if request else ""),
                int(time.time()),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        # analytics must never break the product flow
        pass

def _require_admin(token: str | None) -> None:
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="需要 analytics token")

def _pct(a: int, b: int) -> str:
    return "0%" if not b else f"{round(a * 100 / b, 1)}%"

_init_analytics_db()

app = FastAPI(title="Voice Expression MVP V1.6.5 QR Fix")

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
    return {"ok": True, "version": "v1.6.9-secure-analytics", "static": str(STATIC_DIR), "analytics": True}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/s")
@app.get("/s.html")
def share_page() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "s.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/api/qr")
@app.get("/qr")
def qr(url: str = Query(..., min_length=1)) -> Response:
    final_url = unquote(url)
    img = qrcode.make(final_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.post("/api/analyze-voice")
async def analyze_voice_api(
    request: Request,
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
    _record_event("analysis_complete", {"score": result.get("score"), "type": result.get("type"), "audio_url": audio_url}, request=request)
    return {
        "ok": True,
        "result": result,
        "audio_url": audio_url,
        "sentence": sentence,
    }


@app.post("/api/upload")
async def upload_share_audio(
    request: Request,
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
    _record_event("share_created", {"sid": share_id, "score": meta_obj.get("score"), "type": meta_obj.get("type")}, request=request, sid=share_id)
    return {"ok": True, "id": share_id, "audio_url": payload["audio_url"], "share_url": f"/s.html?id={share_id}"}


@app.get("/api/share")
def get_share(request: Request, id: str = Query(..., min_length=1)) -> JSONResponse:
    payload = _load_share(id)
    _record_event("share_data_loaded", {"sid": id}, request=request, sid=id)
    return JSONResponse(payload, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/api/audio")
def get_audio(request: Request, id: str = Query(..., min_length=1)) -> FileResponse:
    payload = _load_share(id)
    _record_event("share_audio_play_request", {"sid": id}, request=request, sid=id)
    filename = payload.get("filename")
    if not filename or "/" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="音频不存在。")
    audio_path = UPLOADS_DIR / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="音频不存在。")
    return FileResponse(
        audio_path,
        media_type=("audio/webm" if filename.endswith(".webm") else "audio/mp4" if filename.endswith((".m4a",".mp4")) else "audio/mpeg" if filename.endswith(".mp3") else "audio/wav" if filename.endswith(".wav") else "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=604800"},
    )


@app.post("/api/track")
async def track_event(request: Request) -> dict:
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}
    event = str(body.get("event") or "unknown")[:80]
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    path = str(body.get("path") or data.get("path") or "")[:240]
    sid = str(body.get("sid") or data.get("sid") or "")[:80]
    _record_event(event, data, request=request, path=path, sid=sid)
    return {"ok": True}

@app.get("/admin/analytics")
def analytics_dashboard(request: Request, token: str | None = Query(default=None)) -> Response:
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        return Response(
            content="""
            <!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
            <title>Analytics Login</title><style>body{font-family:-apple-system,BlinkMacSystemFont,Arial;background:#0b0b0b;color:#fff;padding:28px}form{max-width:420px;margin:15vh auto;background:#161616;border:1px solid #333;border-radius:22px;padding:24px}input,button{width:100%;box-sizing:border-box;border-radius:14px;padding:14px;font-size:16px}input{background:#050505;color:#fff;border:1px solid #444}button{margin-top:12px;border:0;background:#d7ff3f;color:#111;font-weight:900}</style></head>
            <body><form method='get'><h2>Analytics Login</h2><p style='color:#aaa'>输入服务器环境变量 ANALYTICS_ADMIN_TOKEN。</p><input name='token' type='password' autocomplete='current-password' placeholder='Admin token'><button>进入数据面板</button></form></body></html>
            """,
            media_type="text/html",
            status_code=401,
        )
    conn = _analytics_conn()
    total = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
    rows = conn.execute("SELECT event, COUNT(*) AS c FROM events GROUP BY event ORDER BY c DESC").fetchall()
    def c(event: str) -> int:
        row = conn.execute("SELECT COUNT(*) AS c FROM events WHERE event=?", (event,)).fetchone()
        return int(row["c"] or 0)
    page_view = c("page_view")
    record_start = c("record_start")
    analysis_complete = c("analysis_complete")
    share_created = c("share_created")
    share_landing = c("share_landing")
    share_audio = c("share_audio_play_request")
    recent = conn.execute("SELECT event,path,sid,data,ip,ts FROM events ORDER BY id DESC LIMIT 80").fetchall()
    top_shares = conn.execute("SELECT sid, COUNT(*) AS c FROM events WHERE sid!='' GROUP BY sid ORDER BY c DESC LIMIT 30").fetchall()
    conn.close()
    event_rows = "".join(f"<tr><td>{html.escape(r['event'])}</td><td>{r['c']}</td></tr>" for r in rows)
    recent_rows = "".join(f"<tr><td>{time.strftime('%m-%d %H:%M', time.localtime(r['ts']))}</td><td>{html.escape(r['event'])}</td><td>{html.escape(r['path'] or '')}</td><td>{html.escape(r['sid'] or '')}</td><td>{html.escape(r['ip'] or '')}</td></tr>" for r in recent)
    share_rows = "".join(f"<tr><td>{html.escape(r['sid'])}</td><td>{r['c']}</td></tr>" for r in top_shares)
    cards = [
        ("总事件", total), ("首页访问", page_view), ("开始录音", record_start), ("分析完成", analysis_complete),
        ("生成分享", share_created), ("分享页访问", share_landing), ("原声请求", share_audio),
        ("首页→开始", _pct(record_start,page_view)), ("开始→完成", _pct(analysis_complete,record_start)), ("完成→分享", _pct(share_created,analysis_complete)),
    ]
    card_html = "".join(f"<div class='card'><div class='label'>{k}</div><div class='num'>{v}</div></div>" for k,v in cards)
    content = f"""
    <!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>RelationshipTest Analytics</title>
    <style>body{{margin:0;background:#090909;color:#f7f2ea;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',Arial,sans-serif}}.wrap{{max-width:1180px;margin:0 auto;padding:24px}}h1{{font-size:30px;margin:0 0 6px}}.sub{{color:#8e8a83;margin-bottom:22px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}.card{{background:#151515;border:1px solid #2a2a2a;border-radius:18px;padding:16px}}.label{{color:#aaa;font-size:13px}}.num{{font-size:30px;font-weight:950;margin-top:8px;color:#d7ff3f}}.panel{{margin-top:18px;background:#121212;border:1px solid #292929;border-radius:20px;padding:16px;overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}td,th{{border-bottom:1px solid #252525;padding:10px;text-align:left;white-space:nowrap}}th{{color:#aaa}}.hint{{color:#777;font-size:12px;margin-top:14px}}</style></head>
    <body><div class='wrap'><h1>RelationshipTest Analytics</h1><div class='sub'>安全数据面板 · SQLite 本地统计 · 不影响用户流程</div><div class='grid'>{card_html}</div>
    <div class='panel'><h2>事件统计</h2><table><thead><tr><th>事件</th><th>次数</th></tr></thead><tbody>{event_rows}</tbody></table></div>
    <div class='panel'><h2>分享 SID 热度</h2><table><thead><tr><th>SID</th><th>事件数</th></tr></thead><tbody>{share_rows}</tbody></table></div>
    <div class='panel'><h2>最近事件</h2><table><thead><tr><th>时间</th><th>事件</th><th>路径</th><th>SID</th><th>IP</th></tr></thead><tbody>{recent_rows}</tbody></table></div>
    <div class='hint'>安全：设置 ANALYTICS_ADMIN_TOKEN 后需要 token 才能进入。数据库文件：/opt/voice-expression-mvp/analytics.db</div></div></body></html>
    """
    return Response(content=content, media_type="text/html", headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
