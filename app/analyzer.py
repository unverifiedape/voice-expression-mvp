import os
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from typing import Dict, Any

import numpy as np
from pydub import AudioSegment
from pydub.silence import split_on_silence


FFMPEG_BIN = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
FFPROBE_BIN = shutil.which("ffprobe") or "/usr/bin/ffprobe"


class AudioProcessingError(Exception):
    pass


@dataclass
class AudioFeatures:
    duration_sec: float
    rms_mean: float
    rms_std: float
    zcr_mean: float
    silent_ratio: float
    peak: float


def ensure_binary_exists(path: str, name: str) -> None:
    if not path or not os.path.exists(path):
        raise AudioProcessingError(f"{name} 不存在，请确认系统已安装 {name}")


def convert_to_wav(input_path: str, output_path: str) -> None:
    ensure_binary_exists(FFMPEG_BIN, "ffmpeg")
    cmd = [
        FFMPEG_BIN, "-y", "-i", input_path,
        "-ac", "1", "-ar", "16000", "-f", "wav", output_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise AudioProcessingError(f"音频转 wav 失败: {e.stderr.decode(errors='ignore')}")


def trim_silence(input_wav: str, output_wav: str) -> None:
    try:
        sound = AudioSegment.from_wav(input_wav)
    except Exception as e:
        raise AudioProcessingError(f"读取 wav 失败: {e}")

    if len(sound) == 0:
        raise AudioProcessingError("音频为空")

    silence_thresh = max(sound.dBFS - 14, -50)
    chunks = split_on_silence(
        sound,
        min_silence_len=300,
        silence_thresh=silence_thresh,
        keep_silence=120,
    )

    if not chunks:
        sound.export(output_wav, format="wav")
        return

    combined = chunks[0]
    for chunk in chunks[1:]:
        combined += chunk

    combined.export(output_wav, format="wav")


def load_wav_as_float32(wav_path: str) -> tuple[np.ndarray, int]:
    try:
        with wave.open(wav_path, "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)
    except Exception as e:
        raise AudioProcessingError(f"读取 wav 数据失败: {e}")

    if sampwidth != 2:
        raise AudioProcessingError("当前仅支持 16-bit wav")

    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    return audio, framerate


def frame_signal(signal: np.ndarray, frame_size: int, hop_size: int) -> np.ndarray:
    if len(signal) < frame_size:
        pad = np.zeros(frame_size - len(signal), dtype=np.float32)
        signal = np.concatenate([signal, pad])

    frames = []
    for start in range(0, len(signal) - frame_size + 1, hop_size):
        frames.append(signal[start:start + frame_size])

    if not frames:
        frames.append(signal[:frame_size])

    return np.stack(frames)


def extract_features(wav_path: str) -> AudioFeatures:
    signal, sr = load_wav_as_float32(wav_path)

    if len(signal) == 0:
        raise AudioProcessingError("音频为空")

    duration_sec = len(signal) / float(sr)
    frame_size = int(sr * 0.03)
    hop_size = int(sr * 0.01)
    frames = frame_signal(signal, frame_size, hop_size)

    rms = np.sqrt(np.mean(np.square(frames), axis=1) + 1e-10)
    zcr = np.mean(np.abs(np.diff(np.sign(frames), axis=1)), axis=1) / 2.0

    silence_threshold = 0.015
    silent_ratio = float(np.mean(rms < silence_threshold))
    peak = float(np.max(np.abs(signal)))

    return AudioFeatures(
        duration_sec=float(duration_sec),
        rms_mean=float(np.mean(rms)),
        rms_std=float(np.std(rms)),
        zcr_mean=float(np.mean(zcr)),
        silent_ratio=silent_ratio,
        peak=peak,
    )


def classify_expression(features: AudioFeatures) -> Dict[str, Any]:
    energy = features.rms_mean
    energy_var = features.rms_std
    silence = features.silent_ratio
    zcr = features.zcr_mean
    duration = features.duration_sec

    if silence > 0.45:
        label = "试探犹豫型"
        traits = [
            "停顿偏多，表达略显犹豫",
            "情绪释放不算强",
            "容易给人保留、拿不准的感觉",
        ]
    elif energy < 0.035 and energy_var < 0.02:
        label = "冷静控制型"
        traits = [
            "情绪压得比较低",
            "表达更稳，不容易被看透",
            "有时会被误解为冷淡或距离感强",
        ]
    elif energy > 0.08 or energy_var > 0.04:
        label = "热情外放型"
        traits = [
            "声音能量更高，起伏更明显",
            "表达更外露，更容易被感知到情绪",
            "通常给人直接、热烈的感觉",
        ]
    elif zcr > 0.12:
        label = "直接强势型"
        traits = [
            "语气更利落，边界感更强",
            "表达倾向于直接推进",
            "有时会显得不太留余地",
        ]
    else:
        label = "平稳克制型"
        traits = [
            "整体表达比较平稳",
            "有控制感，但不算太疏离",
            "通常给人理性、收着说的感觉",
        ]

    return {
        "label": label,
        "traits": traits,
        "scores": {
            "energy": round(min(max(energy * 1200, 0), 100), 1),
            "variation": round(min(max(energy_var * 2000, 0), 100), 1),
            "pause": round(min(max(silence * 100, 0), 100), 1),
            "sharpness": round(min(max(zcr * 800, 0), 100), 1),
        },
        "debug": {
            "duration_sec": round(duration, 3),
            "rms_mean": round(energy, 5),
            "rms_std": round(energy_var, 5),
            "zcr_mean": round(zcr, 5),
            "silent_ratio": round(silence, 5),
            "peak": round(features.peak, 5),
        }
    }


def analyze_audio_file(input_path: str) -> Dict[str, Any]:
    ensure_binary_exists(FFMPEG_BIN, "ffmpeg")
    ensure_binary_exists(FFPROBE_BIN, "ffprobe")

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_wav = os.path.join(tmpdir, "raw.wav")
        clean_wav = os.path.join(tmpdir, "clean.wav")

        convert_to_wav(input_path, raw_wav)
        trim_silence(raw_wav, clean_wav)
        features = extract_features(clean_wav)
        return classify_expression(features)
