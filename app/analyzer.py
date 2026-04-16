from __future__ import annotations

import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import librosa
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

TARGET_SR = 16000
MAX_DURATION_SECONDS = 8.0
MIN_DURATION_SECONDS = 1.2


@dataclass
class FeatureSet:
    duration_sec: float
    rms_mean: float
    rms_std: float
    pitch_mean: float
    pitch_std: float
    voiced_ratio: float
    pause_ratio: float
    tempo_proxy: float
    end_drop: float
    zcr_mean: float


TYPE_LIBRARY: Dict[str, Dict[str, object]] = {
    "calm_controller": {
        "emoji": "🧊",
        "title": "冷静控制型",
        "summary": "表达很稳，情绪释放偏低，容易给人克制和收着的感觉。",
        "traits": [
            "情绪压得比较低",
            "不容易被人一下看透",
            "容易被误解为冷淡或距离感强",
        ],
    },
    "warm_expressive": {
        "emoji": "🔥",
        "title": "热情外放型",
        "summary": "声音起伏更明显，表达比较外显，容易让人感到直接和有存在感。",
        "traits": [
            "情绪更容易被听出来",
            "表达感染力比较强",
            "有时会被理解成太直接或太满",
        ],
    },
    "hesitant_tester": {
        "emoji": "🌫️",
        "title": "试探犹豫型",
        "summary": "停顿和迟疑感更明显，像是在边想边说，容易带出不确定感。",
        "traits": [
            "说话时会边想边试探",
            "容易让人感觉没那么笃定",
            "在关系里常被听成拿不准或想保留空间",
        ],
    },
    "direct_assertive": {
        "emoji": "⚡",
        "title": "直接强势型",
        "summary": "声能更集中，句子收得更快，更容易让人感到明确和不拖泥带水。",
        "traits": [
            "表达目标感比较强",
            "说话更像在下判断",
            "有时会被误听成强势或不给余地",
        ],
    },
}


class AudioAnalysisError(Exception):
    pass


def trim_silence_stable(
    audio: AudioSegment,
    silence_thresh: int = -45,
    min_silence_len: int = 200,
    keep_silence: int = 120,
) -> AudioSegment:
    if len(audio) == 0:
        return audio

    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
    )

    if not nonsilent_ranges:
        return audio

    start = max(0, nonsilent_ranges[0][0] - keep_silence)
    end = min(len(audio), nonsilent_ranges[-1][1] + keep_silence)

    if start >= end:
        return audio

    return audio[start:end]


def _load_audio_from_upload(raw_bytes: bytes, filename: str) -> Tuple[np.ndarray, int]:
    suffix = Path(filename or "upload.webm").suffix or ".webm"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as src_file:
        src_file.write(raw_bytes)
        src_file.flush()

        audio = AudioSegment.from_file(src_file.name)
        audio = audio.set_channels(1).set_frame_rate(TARGET_SR)

        silence_thresh = int(audio.dBFS - 18) if math.isfinite(audio.dBFS) else -38
        trimmed = trim_silence_stable(
            audio,
            silence_thresh=silence_thresh,
            min_silence_len=180,
            keep_silence=80,
        )
        if len(trimmed) == 0:
            trimmed = audio

        peak = trimmed.max_dBFS
        if math.isfinite(peak):
            target_peak = -3.0
            trimmed = trimmed.apply_gain(target_peak - peak)

        samples = np.array(trimmed.get_array_of_samples()).astype(np.float32)
        if trimmed.sample_width == 2:
            samples /= 32768.0
        elif trimmed.sample_width == 4:
            samples /= 2147483648.0
        else:
            max_val = float(2 ** (8 * trimmed.sample_width - 1))
            samples /= max_val

        return samples, TARGET_SR


def extract_features(raw_bytes: bytes, filename: str) -> FeatureSet:
    y, sr = _load_audio_from_upload(raw_bytes, filename)

    duration = len(y) / float(sr)
    if duration < MIN_DURATION_SECONDS:
        raise AudioAnalysisError("录音太短了，请至少录 1.2 秒。")
    if duration > MAX_DURATION_SECONDS:
        y = y[: int(MAX_DURATION_SECONDS * sr)]
        duration = MAX_DURATION_SECONDS

    y = librosa.util.normalize(y)

    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    zcr = librosa.feature.zero_crossing_rate(y=y, frame_length=1024, hop_length=256)[0]

    f0, voiced_flag, _ = librosa.pyin(
        y,
        sr=sr,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C6"),
        frame_length=1024,
        hop_length=256,
    )
    voiced_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])

    rms_mean = float(np.mean(rms)) if len(rms) else 0.0
    rms_std = float(np.std(rms)) if len(rms) else 0.0
    pitch_mean = float(np.mean(voiced_f0)) if len(voiced_f0) else 0.0
    pitch_std = float(np.std(voiced_f0)) if len(voiced_f0) else 0.0
    voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag is not None else 0.0

    pause_threshold = max(rms_mean * 0.45, 0.015)
    pause_ratio = float(np.mean(rms < pause_threshold)) if len(rms) else 0.0

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=256)
    tempo_proxy = float(np.mean(onset_env)) if len(onset_env) else 0.0

    end_window = y[int(len(y) * 0.75) :]
    if len(end_window) > 512:
        end_rms = librosa.feature.rms(y=end_window, frame_length=512, hop_length=128)[0]
        end_drop = float(end_rms[0] - end_rms[-1]) if len(end_rms) > 1 else 0.0
    else:
        end_drop = 0.0

    return FeatureSet(
        duration_sec=duration,
        rms_mean=rms_mean,
        rms_std=rms_std,
        pitch_mean=pitch_mean,
        pitch_std=pitch_std,
        voiced_ratio=voiced_ratio,
        pause_ratio=pause_ratio,
        tempo_proxy=tempo_proxy,
        end_drop=end_drop,
        zcr_mean=float(np.mean(zcr)) if len(zcr) else 0.0,
    )


def _score_axes(features: FeatureSet) -> Dict[str, float]:
    emotional_energy = clamp01(
        0.40 * scale(features.rms_std, 0.02, 0.09)
        + 0.35 * scale(features.pitch_std, 12.0, 55.0)
        + 0.25 * scale(features.tempo_proxy, 0.5, 6.0)
    )
    control_index = clamp01(
        0.45 * (1.0 - scale(features.pause_ratio, 0.08, 0.45))
        + 0.30 * (1.0 - scale(features.pitch_std, 12.0, 60.0))
        + 0.25 * scale(features.end_drop, -0.01, 0.06)
    )
    hesitation_index = clamp01(
        0.55 * scale(features.pause_ratio, 0.10, 0.50)
        + 0.25 * (1.0 - scale(features.voiced_ratio, 0.55, 0.95))
        + 0.20 * (1.0 - scale(features.tempo_proxy, 0.5, 5.0))
    )
    distance_index = clamp01(
        0.40 * (1.0 - emotional_energy)
        + 0.35 * scale(features.end_drop, 0.0, 0.08)
        + 0.25 * (1.0 - scale(features.rms_mean, 0.04, 0.18))
    )
    return {
        "emotional_energy": emotional_energy,
        "control_index": control_index,
        "hesitation_index": hesitation_index,
        "distance_index": distance_index,
    }


def classify_expression(features: FeatureSet) -> Dict[str, object]:
    axes = _score_axes(features)
    e = axes["emotional_energy"]
    c = axes["control_index"]
    h = axes["hesitation_index"]
    d = axes["distance_index"]

    if h >= 0.58:
        type_key = "hesitant_tester"
        confidence = int(68 + 20 * h - 8 * e)
    elif e >= 0.58 and c < 0.62:
        type_key = "warm_expressive"
        confidence = int(66 + 18 * e)
    elif c >= 0.62 and d >= 0.54:
        type_key = "calm_controller"
        confidence = int(70 + 15 * c + 8 * d - 8 * h)
    else:
        type_key = "direct_assertive"
        confidence = int(65 + 12 * c + 10 * e)

    confidence = max(61, min(92, confidence))
    type_info = TYPE_LIBRARY[type_key]

    return {
        "type_key": type_key,
        "emoji": type_info["emoji"],
        "title": type_info["title"],
        "summary": type_info["summary"],
        "traits": type_info["traits"],
        "confidence": confidence,
        "axes": {k: round(v * 100, 1) for k, v in axes.items()},
        "raw_features": {
            "duration_sec": round(features.duration_sec, 3),
            "rms_mean": round(features.rms_mean, 5),
            "rms_std": round(features.rms_std, 5),
            "pitch_mean": round(features.pitch_mean, 2),
            "pitch_std": round(features.pitch_std, 2),
            "voiced_ratio": round(features.voiced_ratio, 3),
            "pause_ratio": round(features.pause_ratio, 3),
            "tempo_proxy": round(features.tempo_proxy, 3),
            "end_drop": round(features.end_drop, 5),
            "zcr_mean": round(features.zcr_mean, 5),
        },
    }


def analyze_voice(raw_bytes: bytes, filename: str) -> Dict[str, object]:
    features = extract_features(raw_bytes, filename)
    return classify_expression(features)


def scale(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return (value - lo) / (hi - lo)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
