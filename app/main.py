import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.analyzer import analyze_audio_file, AudioProcessingError

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Voice Expression MVP")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/analyze")
async def analyze_audio(file: UploadFile = File(...), sentence: str = Form(...)):
    suffix = Path(file.filename or "audio.webm").suffix or ".webm"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / f"input{suffix}"
        try:
            with open(input_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)

            result = analyze_audio_file(str(input_path))
            return {"ok": True, "sentence": sentence, "result": result}

        except AudioProcessingError as e:
            return JSONResponse(status_code=400, content={"ok": False, "error": f"音频处理失败：{str(e)}"})
        except Exception as e:
            return JSONResponse(status_code=500, content={"ok": False, "error": f"分析失败：{str(e)}"})


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
