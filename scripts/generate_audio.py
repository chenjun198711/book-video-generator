#!/usr/bin/env python3
"""
三分钟精读书 TTS 语音生成脚本
默认使用火山引擎 TTS（豆包语音合成 2.0，需 API Key），备选 edge-tts（微软免费 TTS）。

火山引擎：V1 API + X-Api-Key 认证，TTS 2.0 音色，基于返回时长估算词级时间戳
edge-tts：原生 WordBoundary 词级时间戳，精确同步

环境变量：
  VOLC_TTS_API_KEY  火山引擎 API Key（新版控制台获取）

用法：
  # 单段生成（自动选择引擎）
  python generate_audio.py --text "你好世界" --output audio.mp3

  # 指定引擎
  python generate_audio.py --text "你好世界" --output audio.mp3 --engine edge

  # 批量生成
  python generate_audio.py --batch captions.json --output-dir audio/

  # 列出可用音色
  python generate_audio.py --list-voices
"""

import asyncio
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid


# ── 火山引擎 TTS（V1 API + X-Api-Key）─────────────────────────

VOLC_TTS_URL = "https://openspeech.bytedance.com/api/v1/tts"
VOLC_TTS_RESOURCE_ID = "seed-tts-2.0"

# 火山引擎 TTS 2.0 音色（适合读书解说）
VOLC_DEFAULT_VOICE = "zh_female_zhixingnv_uranus_bigtts"

VOLC_VOICES = {
    # 有声阅读专用
    "zh_female_zhixingnv_uranus_bigtts": "知性女声 2.0（推荐读书）",
    "zh_male_xuanyijieshuo_uranus_bigtts": "悬疑解说 2.0（有声阅读）",
    "zh_male_baqiqingshu_uranus_bigtts": "霸气青叔 2.0（有声阅读）",
    # 视频配音
    "zh_female_qingxinnvsheng_uranus_bigtts": "清新女声 2.0",
    "zh_female_liuchangnv_uranus_bigtts": "流畅女声 2.0",
    "zh_male_cixingjieshuonan_uranus_bigtts": "磁性解说男声 2.0",
    "zh_male_jieshuoxiaoming_uranus_bigtts": "解说小明 2.0",
    "zh_male_dayi_uranus_bigtts": "大壹 2.0",
    "zh_male_shenyeboke_uranus_bigtts": "深夜播客 2.0",
    "zh_male_ruyayichen_uranus_bigtts": "儒雅逸辰 2.0",
}


def _volc_tts(text: str, output_path: str, speaker: str,
              api_key: str) -> tuple:
    """调用火山引擎 V1 API 生成 TTS 音频

    使用 X-Api-Key 认证 + seed-tts-2.0 资源 ID + TTS 2.0 音色。
    基于返回的音频时长估算词级时间戳（TTS 2.0 不原生支持时间戳）。

    Returns: (audio_path, words_path)
    """
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": VOLC_TTS_RESOURCE_ID,
    }

    body = json.dumps({
        "app": {
            "appid": "api_key",
            "token": "api_key",
            "cluster": "volcano_tts",
        },
        "user": {"uid": "book-video-generator"},
        "audio": {
            "voice_type": speaker,
            "encoding": "mp3",
            "speed_ratio": 1.0,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
            "with_timestamp": 1,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        VOLC_TTS_URL, data=body, headers=headers, method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"火山引擎TTS HTTP错误 {e.code}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"火山引擎TTS网络错误: {e.reason}") from e

    result = json.loads(raw)

    code = result.get("code", -1)
    if code != 3000:
        message = result.get("message", "未知错误")
        raise RuntimeError(f"火山引擎TTS错误 (code={code}): {message}")

    # 解码音频数据
    audio_data = base64.b64decode(result["data"])

    # 获取音频时长（毫秒）
    addition = result.get("addition", {})
    duration_ms = int(addition.get("duration", 0))

    # 估算词级时间戳（TTS 2.0 不原生支持时间戳）
    words = _estimate_word_timestamps(text, duration_ms)

    # 写入文件
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_data)

    words_path = output_path.rsplit(".", 1)[0] + ".words.json"
    with open(words_path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    return output_path, words_path


# ── 词级时间戳估算 ────────────────────────────────────────────

# 标点符号（占用时间但不发音）
_PUNCT_CHARS = set("，。！？；：、…—「」\"\"''《》【】（）()[] \n\t\r")


def _estimate_word_timestamps(text: str, duration_ms: int) -> list:
    """基于文本长度和音频时长估算词级时间戳

    TTS 2.0 不原生支持词级时间戳，通过均匀分配时长来估算。
    标点符号占用较少时间（模拟自然停顿）。

    Args:
        text: 原始字幕文本
        duration_ms: 音频时长（毫秒）

    Returns: [{"text": "字", "start": 0.0, "end": 0.3}, ...]
    """
    if not text or duration_ms <= 0:
        return []

    duration_s = duration_ms / 1000.0

    # 逐字符处理（保留标点以匹配 build_phrases 的逻辑）
    chars = list(text)

    # 为每个字符分配权重：普通字符=1.0，标点=0.25
    weights = []
    for c in chars:
        if c in _PUNCT_CHARS:
            weights.append(0.25)
        else:
            weights.append(1.0)

    total_weight = sum(weights)
    if total_weight <= 0:
        return []

    words = []
    current_time = 0.0
    for c, w in zip(chars, weights):
        char_duration = (w / total_weight) * duration_s
        words.append({
            "text": c,
            "start": round(current_time, 3),
            "end": round(current_time + char_duration, 3),
        })
        current_time += char_duration

    return words


# ── edge-tts（备选，原生 WordBoundary）────────────────────────

EDGE_DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

EDGE_VOICES = {
    "zh-CN-XiaoxiaoNeural": "晓晓（女声，活泼）",
    "zh-CN-YunxiNeural": "云希（男声，沉稳）",
    "zh-CN-XiaoyiNeural": "晓伊（女声，温柔）",
    "zh-CN-YunjianNeural": "云健（男声，阳光）",
}


async def _edge_tts(text: str, output_path: str, voice: str) -> tuple:
    """使用 edge-tts 生成 TTS 音频（备选方案）

    原生支持 WordBoundary 词级时间戳，精确同步。

    Returns: (audio_path, words_path)
    """
    try:
        import edge_tts
    except ImportError:
        print("正在安装 edge-tts...")
        os.system(f"{sys.executable} -m pip install edge-tts -q")
        import edge_tts

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")

    audio_data = b""
    words = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            offset = chunk["offset"] / 1e7
            duration = chunk["duration"] / 1e7
            words.append({
                "text": chunk["text"],
                "start": round(offset, 3),
                "end": round(offset + duration, 3),
            })

    with open(output_path, "wb") as f:
        f.write(audio_data)

    words_path = output_path.rsplit(".", 1)[0] + ".words.json"
    with open(words_path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    return output_path, words_path


# ── 统一接口 ──────────────────────────────────────────────────

def _detect_engine(engine: str, voice: str) -> str:
    """自动检测应使用的 TTS 引擎

    优先级：
    1. --engine 显式指定
    2. voice 名称匹配（_uranus_bigtts → volcano, *Neural → edge）
    3. 环境变量 VOLC_TTS_API_KEY 存在 → volcano
    4. 回退到 edge
    """
    if engine != "auto":
        return engine

    # 根据 voice 名称推断
    if "_uranus_bigtts" in voice or "_tob" in voice:
        return "volcano"
    if "Neural" in voice:
        return "edge"

    # 根据环境变量判断
    api_key = os.environ.get("VOLC_TTS_API_KEY", "")
    if api_key:
        return "volcano"

    return "edge"


def generate_audio(text: str, output_path: str, voice: str = "",
                   engine: str = "auto") -> tuple:
    """生成单段 TTS 音频（统一接口）

    自动选择引擎：
    - 火山引擎 TTS（默认，需 VOLC_TTS_API_KEY）
    - edge-tts（备选，免费无需配置）

    Args:
        text: 要合成的文本
        output_path: 输出 MP3 路径
        voice: 音色名称（留空则使用引擎默认音色）
        engine: "auto" | "volcano" | "edge"

    Returns: (audio_path, words_path)

    会在 output_path 同目录下生成 .words.json 词级时间戳文件。
    """
    detected = _detect_engine(engine, voice)

    if detected == "volcano":
        api_key = os.environ.get("VOLC_TTS_API_KEY", "")
        if not api_key:
            print("[警告] 火山引擎TTS缺少 API Key（VOLC_TTS_API_KEY），"
                  "自动切换到 edge-tts")
            detected = "edge"
            if not voice or "_uranus_bigtts" in voice or "_tob" in voice:
                voice = EDGE_DEFAULT_VOICE
        else:
            if not voice:
                voice = VOLC_DEFAULT_VOICE

    if detected == "edge":
        if not voice or "_uranus_bigtts" in voice or "_tob" in voice:
            voice = EDGE_DEFAULT_VOICE

    if detected == "volcano":
        return _volc_tts(text, output_path, voice, api_key)
    else:
        return asyncio.run(_edge_tts(text, output_path, voice))


def batch_generate(captions: list, output_dir: str, voice: str = "",
                   engine: str = "auto") -> list:
    """批量生成多段字幕的 TTS 音频及词级时间戳

    Args:
        captions: 字幕文本列表
        output_dir: 输出目录
        voice: 音色名称（留空使用默认）
        engine: "auto" | "volcano" | "edge"

    Returns: [audio_path, ...]
    """
    detected = _detect_engine(engine, voice)
    engine_label = "火山引擎" if detected == "volcano" else "edge-tts"
    print(f"TTS 引擎: {engine_label}")

    results = []
    for i, text in enumerate(captions):
        output = os.path.join(output_dir, f"audio_{i:03d}.mp3")
        audio_path, words_path = generate_audio(text, output, voice, detected)
        results.append(audio_path)
        print(f"[{i+1}/{len(captions)}] {os.path.basename(audio_path)} "
              f"(+ {os.path.basename(words_path)}, {len(text)} 字)")
    return results


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="TTS 语音生成（火山引擎默认 / edge-tts备选，含词级时间戳）"
    )
    parser.add_argument("--text", type=str, help="字幕文本")
    parser.add_argument("--output", type=str, default="audio.mp3", help="输出路径")
    parser.add_argument("--voice", type=str, default="",
                        help="音色（留空用默认；火山: zh_female_zhixingnv_uranus_bigtts / edge: zh-CN-XiaoxiaoNeural）")
    parser.add_argument("--engine", type=str, default="auto",
                        choices=["auto", "volcano", "edge"],
                        help="TTS引擎：auto(自动) / volcano(火山引擎) / edge(edge-tts)")
    parser.add_argument("--batch", type=str,
                        help="批量模式：JSON文件路径，格式 [\"文本1\",\"文本2\",...]")
    parser.add_argument("--output-dir", type=str, default="audio_output",
                        help="批量输出目录")
    parser.add_argument("--list-voices", action="store_true",
                        help="列出可用音色")

    args = parser.parse_args()

    if args.list_voices:
        print("═ 火山引擎 TTS 2.0 音色（需 VOLC_TTS_API_KEY）═")
        print("  认证方式：X-Api-Key（新版控制台单个 Key）")
        print()
        for vid, desc in VOLC_VOICES.items():
            default = " ← 默认" if vid == VOLC_DEFAULT_VOICE else ""
            print(f"  {vid:50s} {desc}{default}")
        print()
        print("═ edge-tts 音色（免费，无需配置）═")
        for vid, desc in EDGE_VOICES.items():
            default = " ← 默认" if vid == EDGE_DEFAULT_VOICE else ""
            print(f"  {vid:40s} {desc}{default}")
        sys.exit(0)

    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as f:
            captions = json.load(f)
        batch_generate(captions, args.output_dir, args.voice, args.engine)
    elif args.text:
        audio_path, words_path = generate_audio(
            args.text, args.output, args.voice, args.engine
        )
        print(f"音频: {audio_path}")
        print(f"时间戳: {words_path}")
    else:
        print("请提供 --text 或 --batch 参数（或 --list-voices 查看音色）")
        sys.exit(1)
