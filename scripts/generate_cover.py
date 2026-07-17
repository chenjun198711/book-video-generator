#!/usr/bin/env python3
"""
封面图生成脚本
为三分钟精读一本书视频生成专属封面图（1920x1080），包含书名、作者、品牌文字。

设计：
- 背景：可选分镜图模糊+暗化，或深蓝渐变
- 顶部："3分钟精读一本书" 品牌文字 + 橙色分隔线
- 中部：书名（大字，自动换行居中）
- 中下：作者名
- 底部：账号名称水印（可选，不传则不显示）

依赖：Pillow (PIL)

使用方法：
  # 用第一张分镜图做背景
  python generate_cover.py --book-name "原子习惯" --author "James Clear" --output cover.png --bg scene_000.png

  # 无背景图，使用渐变
  python generate_cover.py --book-name "原子习惯" --author "James Clear" --output cover.png

  # 指定竖屏尺寸
  python generate_cover.py --book-name "原子习惯" --author "James Clear" --output cover.png --width 1080 --height 1920
"""

import argparse
import os
import platform
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ── 字体检测 ──────────────────────────────────────────────

def detect_font_path():
    """自动检测系统可用的中文字体文件路径，返回 (path, is_bold)"""
    system = platform.system().lower()
    candidates = []

    if system == "windows":
        candidates = [
            ("C:/Windows/Fonts/msyhbd.ttc", True),   # 微软雅黑 Bold
            ("C:/Windows/Fonts/msyh.ttc", False),     # 微软雅黑
            ("C:/Windows/Fonts/simhei.ttf", True),    # 黑体
            ("C:/Windows/Fonts/simsun.ttc", False),   # 宋体
        ]
    elif system == "darwin":
        candidates = [
            ("/System/Library/Fonts/PingFang.ttc", True),
            ("/System/Library/Fonts/STHeiti Medium.ttc", True),
            ("/Library/Fonts/Arial Unicode.ttf", False),
        ]
    else:
        candidates = [
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", True),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", True),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", False),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", False),
            ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", False),
            ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", False),
        ]

    for path, is_bold in candidates:
        if os.path.exists(path):
            return path, is_bold

    return None, False


def load_font(size):
    """加载指定大小的中文字体"""
    font_path, _ = detect_font_path()
    if font_path:
        return ImageFont.truetype(font_path, size)
    print("警告：未找到中文字体，使用默认字体（可能无法显示中文）", file=sys.stderr)
    return ImageFont.load_default()


# ── 绘制工具 ──────────────────────────────────────────────

def draw_text_centered(draw, text, y, font, img_width, fill=(255, 255, 255, 255), shadow=True):
    """居中绘制文字，可选阴影"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (img_width - text_width) // 2

    if shadow:
        draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 160))

    draw.text((x, y), text, font=font, fill=fill)


def wrap_text(draw, text, font, max_width):
    """将文本按最大宽度自动换行，返回行列表"""
    lines = []
    current = ""
    for char in text:
        test = current + char
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines


# ── 背景生成 ──────────────────────────────────────────────

def make_gradient_bg(width, height):
    """生成深蓝渐变背景"""
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        r = int(15 + (35 - 15) * ratio)
        g = int(25 + (45 - 25) * ratio)
        b = int(55 + (75 - 55) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
    return img


def make_blur_bg(bg_path, width, height):
    """用分镜图做模糊+暗化背景"""
    bg = Image.open(bg_path).convert("RGB")
    bg = bg.resize((width, height), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
    bg = bg.convert("RGBA")
    # 叠加半透明黑色遮罩
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 130))
    return Image.alpha_composite(bg, overlay)


# ── 主函数 ────────────────────────────────────────────────

ACCENT_COLOR = (255, 127, 114, 230)  # #FF7F72 与分镜插图主角上衣同色

def generate_cover(
    book_name,
    author_name,
    output_path,
    bg_image=None,
    width=1920,
    height=1080,
    ip_name=None,
):
    """
    生成封面图

    参数：
    - book_name: 书名
    - author_name: 作者名
    - output_path: 输出 PNG 路径
    - bg_image: 背景图路径（可选，用第一张分镜图）
    - width / height: 封面尺寸
    - ip_name: 底部账号名称（可选，不传则不显示水印）
    """

    # 1. 准备背景
    if bg_image and os.path.exists(bg_image):
        canvas = make_blur_bg(bg_image, width, height)
        print(f"背景：{bg_image}（模糊+暗化）")
    else:
        canvas = make_gradient_bg(width, height)
        print("背景：深蓝渐变")

    draw = ImageDraw.Draw(canvas)

    # 2. 顶部品牌文字
    brand_font = load_font(38)
    draw_text_centered(draw, "3 分钟精读一本书", 70, brand_font, width,
                       fill=(255, 255, 255, 210))

    # 橙色分隔线
    line_y = 135
    line_w = min(420, width // 3)
    line_x = (width - line_w) // 2
    draw.line([(line_x, line_y), (line_x + line_w, line_y)],
              fill=ACCENT_COLOR, width=3)

    # 3. 书名（大字，自动换行）
    title_font_size = 80 if width >= 1920 else 56
    title_font = load_font(title_font_size)
    max_title_width = width - 200
    title_lines = wrap_text(draw, f"《{book_name}》", title_font, max_title_width)

    line_height = int(title_font_size * 1.25)
    # 书名垂直居中于 height 的 30%~65% 区域
    title_area_top = int(height * 0.30)
    title_area_bot = int(height * 0.65)
    total_h = len(title_lines) * line_height
    start_y = title_area_top + (title_area_bot - title_area_top - total_h) // 2

    for i, line in enumerate(title_lines):
        draw_text_centered(draw, line, start_y + i * line_height, title_font, width,
                           fill=(255, 255, 255, 255))

    # 4. 作者名
    author_font = load_font(42 if width >= 1920 else 30)
    author_y = int(height * 0.68)
    draw_text_centered(draw, f"作者：{author_name}", author_y, author_font, width,
                       fill=(255, 255, 255, 230))

    # 5. 底部装饰线 + 账号名（仅当 ip_name 非空时显示）
    if ip_name:
        bottom_y = height - 100
        bx = width // 2
        draw.line([(bx - 50, bottom_y), (bx + 50, bottom_y)],
                  fill=ACCENT_COLOR, width=2)

        ip_font = load_font(28 if width >= 1920 else 20)
        draw_text_centered(draw, ip_name, bottom_y + 15, ip_font, width,
                           fill=(255, 255, 255, 160))

    # 6. 保存
    canvas.convert("RGB").save(output_path, "PNG", quality=95)
    print(f"封面图已生成：{output_path}  ({width}x{height})")
    return output_path


# ── CLI ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="生成三分钟精读一本书封面图")
    parser.add_argument("--book-name", required=True, help="书名")
    parser.add_argument("--author", required=True, help="作者名")
    parser.add_argument("--output", required=True, help="输出 PNG 路径")
    parser.add_argument("--bg", help="背景图路径（可选，用第一张分镜图）")
    parser.add_argument("--ip-name", default=None, help="底部账号名称（可选，不传则不显示水印）")
    parser.add_argument("--width", type=int, default=1920, help="宽度（默认 1920）")
    parser.add_argument("--height", type=int, default=1080, help="高度（默认 1080）")

    args = parser.parse_args()

    generate_cover(
        book_name=args.book_name,
        author_name=args.author,
        output_path=args.output,
        bg_image=args.bg,
        width=args.width,
        height=args.height,
        ip_name=args.ip_name,
    )


if __name__ == "__main__":
    main()
