#!/usr/bin/env python3
"""
三分钟精读书 视频合成脚本
将图片+音频合成为带字幕的 MP4 视频，替代扣子工作流中的剪映小助手。

依赖：
- imageio-ffmpeg（自动提供 ffmpeg 二进制）
- moviepy 方案见 compose_video_moviepy.py（备用）

使用方法：
  python compose_video.py < segments.json

segments.json 格式：
{
  "output": "output.mp4",
  "segments": [
    {"image": "1.png", "audio": "1.mp3", "caption": "字幕文本"},
    ...
  ]
}
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG = "ffmpeg"


def detect_font():
    """自动检测系统可用的中文字体，返回 ffmpeg subtitles 滤镜可用的 FontName"""
    import platform

    system = platform.system().lower()
    candidates = []

    if system == "windows":
        candidates = [
            ("C:/Windows/Fonts/msyh.ttc", "Microsoft YaHei"),
            ("C:/Windows/Fonts/msyhbd.ttc", "Microsoft YaHei"),
            ("C:/Windows/Fonts/simhei.ttf", "SimHei"),
            ("C:/Windows/Fonts/simsun.ttc", "SimSun"),
        ]
    elif system == "darwin":
        candidates = [
            ("/System/Library/Fonts/PingFang.ttc", "PingFang SC"),
            ("/System/Library/Fonts/STHeiti Medium.ttc", "STHeiti"),
            ("/Library/Fonts/Arial Unicode.ttf", "Arial Unicode MS"),
        ]
    else:
        candidates = [
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "Noto Sans CJK SC"),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "Noto Sans CJK SC"),
            ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "WenQuanYi Zen Hei"),
            ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "WenQuanYi Micro Hei"),
        ]

    for path, name in candidates:
        if os.path.exists(path):
            return name

    try:
        result = subprocess.run(
            ["fc-list", ":lang=zh", "family"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            return result.stdout.strip().split("\n")[0].split(",")[0].strip()
    except (FileNotFoundError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        pass

    return "Sans"


def get_duration(audio_path: str) -> float:
    """使用 ffmpeg 获取音频时长"""
    cmd = [FFMPEG, "-i", audio_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if m:
        h, m_, s = m.groups()
        return int(h) * 3600 + int(m_) * 60 + float(s)
    raise RuntimeError(f"无法获取音频时长: {audio_path}")


def make_srt(segments, durations, output_path, gap=0.3):
    """生成 SRT 字幕文件"""
    lines = []
    start = 0.0

    for i, (seg, dur) in enumerate(zip(segments, durations), 1):
        end = start + dur

        def fmt(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = t % 60
            return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

        lines.append(str(i))
        lines.append(f"{fmt(start)} --> {fmt(end)}")
        lines.append(seg.get("caption", ""))
        lines.append("")
        start = end + gap

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path


def compose_video(
    segments,
    output_path=None,
    output=None,
    cover=None,
    video_width=1920,
    video_height=1080,
    fps=24,
    gap=0.3,
):
    if output_path is None and output:
        output_path = output
    if not output_path:
        raise ValueError("必须提供 output_path 或 output")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="book_video_")

    # 如果指定了封面图，替换第一分镜的图片（保持音频不变）
    if cover and os.path.exists(cover) and len(segments) > 0:
        original_img = segments[0].get("image", "")
        segments[0]["image"] = cover
        print(f"封面图已启用：{cover}（替换原第一分镜图 {original_img}）")

    clip_files = []
    durations = []

    for i, seg in enumerate(segments):
        img = seg["image"]
        aud = seg["audio"]

        if not os.path.exists(img):
            print(f"警告：图片不存在 {img}")
            continue
        if not os.path.exists(aud):
            print(f"警告：音频不存在 {aud}")
            continue

        dur = get_duration(aud)
        durations.append(dur)
        clip_out = os.path.join(tmpdir, f"clip_{i:03d}.mp4")

        total_frames = max(1, int(dur * fps))
        fade_dur = min(0.3, dur / 2)

        # Ken Burns: 偶数分镜缓慢放大 1.0→1.1，奇数分镜缓慢缩小 1.1→1.0
        if i % 2 == 0:
            zoom_expr = "min(zoom+0.0008,1.1)"
        else:
            zoom_expr = "if(eq(on,0),1.1,max(zoom-0.0008,1.0))"

        vf = (
            f"scale={video_width}:{video_height}:force_original_aspect_ratio=decrease,"
            f"pad={video_width}:{video_height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"zoompan=z='{zoom_expr}':d={total_frames}:s={video_width}x{video_height}:fps={fps},"
            f"fade=t=in:st=0:d={fade_dur},"
            f"fade=t=out:st={max(0, dur - fade_dur)}:d={fade_dur}"
        )

        cmd = [
            FFMPEG, "-y", "-loop", "1", "-i", img, "-i", aud,
            "-c:v", "libx264",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-t", str(dur), "-vf", vf, "-shortest",
            clip_out
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        clip_files.append(clip_out)
        print(f"[{i+1}/{len(segments)}] clip {dur:.2f}s")

    # 1. 拼接无字幕视频
    concat_list = os.path.join(tmpdir, "clips.txt")
    with open(concat_list, "w") as f:
        for cf in clip_files:
            f.write(f"file '{cf}'\n")

    no_subs = os.path.join(tmpdir, "no_subs.mp4")
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", no_subs],
        capture_output=True, check=True
    )

    # 2. 生成 SRT 字幕
    srt_path = os.path.join(tmpdir, "subtitles.srt")
    make_srt(segments, durations, srt_path, gap=gap)

    # 3. 烧录字幕到最终视频
    # Windows 下 SRT 路径使用正斜杠 + 冒号转义
    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
    font_name = detect_font()
    print(f"字幕字体：{font_name}")
    style = f"FontName={font_name},FontSize=28,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=1,Alignment=2"

    subprocess.run(
        [FFMPEG, "-y", "-i", no_subs, "-vf",
         f"subtitles='{srt_escaped}':force_style='{style}'",
         "-c:a", "copy", output_path],
        capture_output=True, check=True
    )

    shutil.rmtree(tmpdir, ignore_errors=True)

    total = sum(durations) + gap * (len(durations) - 1)
    print(f"\n视频合成完成：{output_path}")
    print(f"总时长：{total:.1f}秒 | 分镜数：{len(clip_files)}")


if __name__ == "__main__":
    data = json.loads(sys.stdin.read())
    compose_video(**data)
