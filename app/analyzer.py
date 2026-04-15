from typing import Dict


def analyze_audio(raw_bytes: bytes, filename: str = "recording.webm") -> Dict:
    """
    临时稳定版分析器：
    先保证整条链路可运行，返回固定结构，便于继续测试分享与裂变流程。
    后续可再替换成真正的音频特征分析逻辑。
    """
    size = len(raw_bytes) if raw_bytes else 0

    if size > 180000:
        label = "热情外放型"
    elif size > 120000:
        label = "直接强势型"
    elif size > 70000:
        label = "冷静控制型"
    elif size > 30000:
        label = "试探犹豫型"
    else:
        label = "平稳克制型"

    return {
        "label": label,
        "score": 0.68,
        "meta": {
            "filename": filename,
            "bytes": size,
            "mode": "temporary_fallback_analyzer",
        },
    }
