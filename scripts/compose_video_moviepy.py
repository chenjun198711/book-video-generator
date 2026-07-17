#!/usr/bin/env python3
"""
三分钟精读书 视频合成脚本（moviepy 版本）
使用 moviepy 将图片+音频+字幕合成为 MP4
"""

import json
import os
import platform
import sys

from moviepy import (
    ImageClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
)


def detect_font_path():
    """自动检测系统可用的中文字体文件路径"""
    system = platform.system().lower()
    candidates = []

    if system == "windows":
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ]
    elif system == "darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]

    for path in candidates:
        if os.path.exists(path):
            return path

    print("警告：未找到中文字体，字幕可能无法显示中文", file=sys.stderr)
    return None


def compose_video(segments, output_path, video_width=1920, video_height=1080, fps=24):
    """
    合成视频

    segments: [{"image": path, "audio": path, "caption": text}, ...]
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    clips = []
    total_duration = 0

    for i, seg in enumerate(segments):
        image = seg["image"]
        audio = seg["audio"]
        caption = seg.get("caption", "")

        if not os.path.exists(image):
            print(f"警告：图片不存在 {image}")
            continue
        if not os.path.exists(audio):
            print(f"警告：音频不存在 {audio}")
            continue

        audio_clip = AudioFileClip(audio)
        duration = audio_clip.duration

        # 图片裁剪缩放为 1920x1080
        img_clip = (
            ImageClip(image)
            .with_duration(duration)
            .resized(new_size=(video_width, video_height))
        )
        img_clip = img_clip.with_audio(audio_clip)

        # 字幕：白色文字+黑色描边
        if caption:
            font_path = detect_font_path()
            txt_clip = (
                TextClip(
                    text=caption,
                    font=font_path or "C:/Windows/Fonts/msyh.ttc",
                    font_size=76,
                    color="white",
                    stroke_color="black",
                    stroke_width=3,
                    size=(video_width, video_height),
                    text_align="center",
                    vertical_align="bottom",
                    margin=(0, 0, 0, 80),
                )
                .with_duration(duration)
                .with_position(("center", "bottom"))
            )

            clip = CompositeVideoClip([img_clip, txt_clip], size=(video_width, video_height))
            clip = clip.with_duration(duration)
        else:
            clip = img_clip

        clips.append(clip)
        total_duration += duration
        print(f"[{i+1}/{len(segments)}] {duration:.2f}s - {caption[:30]}...")

    print(f"\n拼接 {len(clips)} 个片段，总时长 {total_duration:.1f}s")
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp-audio.m4a",
        remove_temp=True,
        threads=4,
        logger=None,
    )

    print(f"\n视频合成完成：{output_path}")
    print(f"总时长：{total_duration:.1f}秒 | 分镜数：{len(clips)}")


if __name__ == "__main__":
    data = json.loads(sys.stdin.read())
    output_path = data.get("output") or data.get("output_path")
    compose_video(data["segments"], output_path)
