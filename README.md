# book-video-generator

输入书名 + 作者，一键生成 3 分钟读书解说视频。

从书评文案撰写、分镜生成、AI 插图、TTS 配音到字幕合成，全流程自动化，最终输出一个带字幕的 MP4 视频。

> 源于扣子工作流 `Pipadushu_video_1`，已移植为 [Agent Skills 开放标准](https://agentskills.io) 格式，跨平台兼容。

---

## 效果演示

输入：
```
书名：《原子习惯》
作者：James Clear
```

输出：
- 16 个分镜的 3 分钟解说视频（1920×1080 MP4）
- 每个分镜配 AI 插图 + TTS 配音 + 字幕
- 全程约 119 秒，文件大小约 6MB

**在线观看**：[https://chenjun198711.github.io/book-video-generator/](https://chenjun198711.github.io/book-video-generator/)

> 也可直接下载视频文件：[`demo/原子习惯_三分钟精读书.mp4`](demo/原子习惯_三分钟精读书.mp4)

---

## 工作流程

```
书名 + 作者
    │
    ▼
┌─────────────────────────────────┐
│ 阶段1: 联网搜索书籍信息           │
│ → LLM 生成约1000字书评文案        │
└──────────┬──────────────────────┘
           ▼
┌─────────────────────────────────┐
│ 阶段2: LLM 拆分为8-50个分镜       │
│ 每个分镜 = 字幕 + 画面描述 + 图像提示词 │
└──────────┬──────────────────────┘
           ▼
┌─────────────────────────────────┐
│ 阶段3: LLM 生成4个板块标题        │
│ 用于视频进度条（每标题≤6字）       │
└──────────┬──────────────────────┘
           ▼
┌─────────────────────────────────┐
│ 阶段4: 并行生成素材               │
│  4a. AI 图像生成 → 16张插图       │
│  4b. edge-tts → 16段配音MP3      │
└──────────┬──────────────────────┘
           ▼
┌─────────────────────────────────┐
│ 阶段5: ffmpeg 合成最终视频         │
│  图片+音频→片段 → 拼接 → 烧录字幕  │
│  → output/书名_三分钟精读书.mp4   │
└─────────────────────────────────┘
```

---

## 文件结构

```
book-video-generator/
├── SKILL.md                          # 技能主指令（5阶段工作流定义 + 平台工具映射）
├── README.md                         # 本文件
├── LICENSE                           # MIT
├── .gitignore
├── demo/                             # 演示视频
│   └── 原子习惯_三分钟精读书.mp4        # 《原子习惯》完整生成效果
├── references/
│   ├── prompts.md                    # 3个LLM提示词原文 + 图像参数 + 代码节点逻辑
│   ├── CROSS_PLATFORM.md             # 各平台详细安装适配指南
│   └── workflow-original.yaml        # 原始扣子工作流完整YAML（备份）
└── scripts/
    ├── generate_audio.py             # TTS语音生成（edge-tts，微软免费TTS）
    ├── generate_image.py             # 跨平台AI图像生成（支持4种API后端）
    ├── generate_cover.py             # 封面图生成（Pillow，自动换行+模糊背景）
    ├── compose_video.py              # 视频合成（ffmpeg两步法，主方案，含Ken Burns+转场+字体检测）
    └── compose_video_moviepy.py      # 视频合成（moviepy方案，备用）
```

---

## 快速开始

### 1. 安装技能

根据你使用的 AI Agent 平台，将技能目录复制到对应位置：

| 平台 | 技能目录 |
|------|---------|
| WorkBuddy | `~/.workbuddy/skills/` |
| OpenClaw | `~/.openclaw/skills/` |
| Codex CLI | `~/.codex/skills/` |
| TRAE Work | `~/.trae/skills/` |
| Claude Code | `~/.claude/skills/` |

```bash
# 示例：克隆到 WorkBuddy 技能目录
git clone https://github.com/chenjun198711/book-video-generator.git \
  ~/.workbuddy/skills/book-video-generator
```

### 2. 安装 Python 依赖

```bash
pip install edge-tts imageio-ffmpeg pillow
```

> `imageio-ffmpeg` 会自动下载 ffmpeg 二进制，无需单独安装系统级 ffmpeg。

### 3. 使用

在 AI Agent 对话中直接说：

> 帮我生成《原子习惯》James Clear 的三分钟精读视频

或：

> 三分钟精读《被讨厌的勇气》岸见一郎

技能会自动按 5 个阶段执行，最终输出 `output/{书名}_三分钟精读书.mp4`。

---

## 扣子工作流 → 本 Skill 映射

| 扣子组件 | 扣子插件/模型 | 本 Skill 替代方案 |
|---------|-------------|----------------|
| 书评文案 LLM | DeepSeek V3.2 | 平台 LLM + WebSearch |
| 分镜描述 LLM | DeepSeek V3.2 | 平台 LLM（保留原 Prompt） |
| 标题进度条 LLM | 豆包 1.8 深度思考 | 平台 LLM（保留原 Prompt） |
| 图像生成 | 扣子内置（model_id=8） | ImageGen / generate_image.py |
| 抠图 | 扣子抠图插件 | 不需要（或 ImageGen 自带） |
| TTS 语音 | 扣子内置 TTS | edge-tts（微软免费） |
| 视频合成 | 剪映小助手插件 | ffmpeg（两步法） |

---

## 脚本说明

### generate_audio.py — TTS 语音生成

```bash
# 单句生成
python3 scripts/generate_audio.py --text "字幕文本" --output audio_001.mp3

# 批量生成（从 JSON 文件）
python3 scripts/generate_audio.py --batch captions.json --output-dir audio/ --voice zh-CN-XiaoxiaoNeural
```

可选语音：
- `zh-CN-XiaoxiaoNeural` — 女声，活泼（默认）
- `zh-CN-YunxiNeural` — 男声，沉稳
- `zh-CN-XiaoyiNeural` — 女声，温柔
- `zh-CN-YunjianNeural` — 男声，阳光

### generate_image.py — 跨平台 AI 图像生成

支持 4 种 API 后端，通过环境变量配置：

```bash
# OpenAI DALL-E 3
export OPENAI_API_KEY="sk-..."
python3 scripts/generate_image.py --prompt "描述" --output scene_001.png --api openai

# Stability AI
export STABILITY_API_KEY="sk-..."
python3 scripts/generate_image.py --prompt "描述" --output scene_001.png --api stability

# 火山引擎即梦 AI
export VOLCENGINE_AK="..." VOLCENGINE_SK="..."
python3 scripts/generate_image.py --prompt "描述" --output scene_001.png --api volcengine

# 本地 Stable Diffusion WebUI
export SD_WEBUI_URL="http://127.0.0.1:7860"
python3 scripts/generate_image.py --prompt "描述" --output scene_001.png --api local

# 批量生成（从分镜 JSON）
python3 scripts/generate_image.py --batch storyboard.json --output-dir images/
```

### compose_video.py — 视频合成

```bash
# 通过 stdin 传入 segments.json
python3 scripts/compose_video.py < segments.json
```

`segments.json` 格式：
```json
{
  "output": "output/书名_三分钟精读书.mp4",
  "cover": "images/cover.png",
  "segments": [
    {"image": "images/scene_000.png", "audio": "audio/audio_000.mp3", "caption": "字幕文本"},
    {"image": "images/scene_001.png", "audio": "audio/audio_001.mp3", "caption": "字幕文本"}
  ]
}
```

> `cover` 字段可选。指定后会用封面图替换第一分镜的图片（保持开场音频不变）。

合成参数：
- 分辨率：1920×1080（16:9）
- 帧率：24fps
- 动态效果：Ken Burns 缓慢缩放 + 0.3s 淡入淡出转场
- 字幕：白色文字 + 黑色描边，底部居中
- 字体：自动检测系统可用中文字体（Windows: 微软雅黑 / macOS: PingFang SC / Linux: Noto Sans CJK）

---

## 跨平台兼容性

| 组件 | WorkBuddy | OpenClaw | Codex CLI | TRAE Work | Claude Code |
|------|-----------|----------|-----------|-----------|-------------|
| SKILL.md | 原生 | 兼容 | 兼容 | 兼容 | 兼容 |
| LLM 提示词 | 直接用 | 直接用 | 直接用 | 直接用 | 直接用 |
| Python 脚本 | 直接用 | 直接用 | 直接用 | 直接用 | 直接用 |
| 联网搜索 | WebSearch | 内置 | Shell/MCP | 内置 | WebSearch |
| 图像生成 | ImageGen | 插件 | generate_image.py | MCP | 内置 |

详见 [references/CROSS_PLATFORM.md](references/CROSS_PLATFORM.md)。

---

## 已知限制

1. **AI 插图水印** — 部分图像生成 API 会在图片右下角添加水印，合成前可用 PIL 裁剪底部
2. **标题进度条** — 阶段3生成了板块标题，但当前 compose_video.py 未将其渲染为视频中的进度条 overlay
3. **图像风格一致性** — 原工作流用固定颜色参数保证风格统一，当前脚本的 API 调用未强制这些参数

---

## 技术栈

- **LLM** — 任何支持中文的 LLM（DeepSeek / GPT / Claude / 豆包等）
- **TTS** — [edge-tts](https://github.com/rany2/edge-tts)（微软 Edge 免费 TTS）
- **视频合成** — [ffmpeg](https://ffmpeg.org/)（通过 [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) 自动提供二进制）
- **图像生成** — OpenAI DALL-E / Stability AI / 火山引擎 / 本地 SD WebUI

---

## License

[MIT](LICENSE)
