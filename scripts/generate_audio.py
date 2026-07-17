#!/usr/bin/env python3
"""
三分钟精读书 TTS 语音生成脚本
使用 edge-tts（微软 Edge 免费 TTS）将字幕文本转为 MP3 音频。
替代扣子工作流中的 TTS 插件。
"""

import asyncio
import os
import sys


async def generate_audio(text: str, output_path: str, voice: str = "zh-CN-XiaoxiaoNeural"):
    """
    生成单段 TTS 音频

    voice 可选：
    - zh-CN-XiaoxiaoNeural (女声，活泼)
    - zh-CN-YunxiNeural (男声，沉稳)
    - zh-CN-XiaoyiNeural (女声，温柔)
    - zh-CN-YunjianNeural (男声，阳光)
    """
    try:
        import edge_tts
    except ImportError:
        print("正在安装 edge-tts...")
        os.system(f"{sys.executable} -m pip install edge-tts -q")
        import edge_tts

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

    return output_path


async def batch_generate(captions: list, output_dir: str, voice: str = "zh-CN-XiaoxiaoNeural"):
    """批量生成多段字幕的 TTS 音频"""
    results = []
    for i, text in enumerate(captions):
        output = os.path.join(output_dir, f"audio_{i:03d}.mp3")
        await generate_audio(text, output, voice)
        results.append(output)
        print(f"[{i+1}/{len(captions)}] {output}")
    return results


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="TTS 语音生成")
    parser.add_argument("--text", type=str, help="字幕文本")
    parser.add_argument("--output", type=str, default="audio.mp3", help="输出路径")
    parser.add_argument("--voice", type=str, default="zh-CN-XiaoxiaoNeural", help="语音角色")
    parser.add_argument("--batch", type=str, help="批量模式：JSON 文件路径，格式 ['文本1','文本2',...]")
    parser.add_argument("--output-dir", type=str, default="audio_output", help="批量输出目录")

    args = parser.parse_args()

    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as f:
            captions = json.load(f)
        asyncio.run(batch_generate(captions, args.output_dir, args.voice))
    elif args.text:
        asyncio.run(generate_audio(args.text, args.output, args.voice))
    else:
        print("请提供 --text 或 --batch 参数")
        sys.exit(1)
