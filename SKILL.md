---
name: book-video-generator
slug: book-video-generator
version: 2.6.0
displayName: 三分钟精读一本书视频生成器
description: 三分钟精读一本书视频生成器。输入书名+作者，一键生成3分钟读书解说视频（书评文案→AI插图→TTS配音→字幕→最终合成MP4）。触发词：三分钟精读书、生成读书视频、精读一本书、book video、做读书视频、书评视频。跨平台兼容 WorkBuddy / OpenClaw / Codex CLI / TRAE Work。
---

# 三分钟精读一本书 视频生成器

## 概述

将任意书籍自动生成一个 3 分钟解说视频：从书评文案撰写、分镜生成、AI 插图、TTS 配音到字幕合成，全流程自动化。

源于扣子工作流 "Pipadushu_video_1"，本 Skill 遵循 [Agent Skills 开放标准](https://agentskills.io)，跨平台兼容 WorkBuddy、OpenClaw、Codex CLI、TRAE Work。

使用本地开源工具替代扣子插件：剪映小助手 → ffmpeg，扣子图像生成 → 平台图像生成工具，扣子 TTS → 火山引擎 TTS（默认）/ edge-tts（备选）。

## 平台工具映射

本 Skill 的工作流涉及 3 个平台相关工具，各平台替代方案如下。执行时根据当前运行平台选择对应工具。

### 联网搜索（阶段 1 用于搜索书籍信息）

| 平台 | 工具 | 说明 |
|------|------|------|
| WorkBuddy | `WebSearch` | 内置工具，直接调用 |
| OpenClaw | 内置 web search | 自动可用 |
| Codex CLI | `shell: curl` 或 MCP 搜索插件 | 通过 shell 命令或安装搜索 MCP |
| TRAE Work | 内置联网搜索 | 自动可用 |

### 图像生成（阶段 4a 用于生成分镜插图）

| 平台 | 工具 | 说明 |
|------|------|------|
| WorkBuddy | `ImageGen` | 内置延迟工具，调用 DeferExecuteTool |
| OpenClaw | `tools` 声明 或 插件 | 在 frontmatter 中声明图像生成 tool，或安装图像插件 |
| Codex CLI | 外部脚本调用 API | 用 Python 脚本调用 DALL-E / Stability AI / 火山引擎等 API |
| TRAE Work | MCP 图像生成服务 | 通过 MCP 接入火山引擎、通义万相等 |

> 无论使用哪个平台，图像生成的 prompt 统一使用分镜中的 `desc_promopt` 字段。

### LLM 调用（阶段 1-3 用于生成文案和分镜）

所有平台均内置 LLM 对话能力，直接将 `references/prompts.md` 中的 System Prompt 发送给当前平台的 LLM 即可。

## 输入

| 参数 | 说明 | 必填 |
|------|------|------|
| `book_name` | 书籍名称 | 是 |
| `author_name` | 作者名称 | 是 |
| `ip_name` | 账号名称（用于封面图底部水印） | 否，默认不显示 |

## 环境准备

执行前确保以下 Python 依赖已安装：

```bash
pip install edge-tts imageio-ffmpeg pillow
```

> 脚本会在首次运行时自动安装缺失的依赖，但建议预先安装以避免中断。

ffmpeg 由 `imageio-ffmpeg` 包自动提供二进制，无需单独安装系统级 ffmpeg。

### TTS 引擎配置（可选）

| 引擎 | 凭证 | 时间戳 | 说明 |
|------|------|--------|------|
| 火山引擎 TTS（默认） | `VOLC_TTS_API_KEY` | 基于音频时长估算 | 豆包语音合成 2.0，中文自然度最高，可商用，需在[火山引擎控制台](https://console.volcengine.com/speech/new)获取 API Key |
| edge-tts（备选） | 无需配置 | WordBoundary 原生精确 | 微软免费 TTS，pip 安装即用，无凭证时自动回退 |

设置火山引擎凭证：
```bash
export VOLC_TTS_API_KEY="your-api-key"
```

> 未设置火山引擎凭证时，脚本自动使用 edge-tts，功能完整不受影响。
> 火山引擎 TTS 2.0 不原生支持词级时间戳，脚本基于返回的音频时长按字符均匀估算时间戳（标点符号占比较短时间），字幕同步精度略低于 edge-tts 但完全可用。

## 完整工作流（5 个阶段）

### 阶段 1：生成书评文案

**目标**：根据书名+作者，用 LLM 生成约 1000 字的 3 分钟视频文案。

**操作**：
1. 用当前平台的**联网搜索工具**搜索书籍真实信息（简介、解读、出版年份）
2. 使用 system prompt（见 `references/prompts.md` 第 1 节），要求 LLM 输出 JSON：

```json
{
  "book_name": "...",
  "author_name": "...",
  "year": "yyyy-MM",
  "content": "1000+字书评文案（含开篇引言+核心内容+观点提炼）",
  "category": "图书分类"
}
```

**要点**：
- 文案需满足约 3 分钟口播时长（约 700-1000 字）
- 开篇引言必须极具吸引力
- 信息来源需通过搜索获取，确保内容准确

### 阶段 2：生成分镜脚本

**目标**：将书评文案拆分为 8-50 个分镜，每个分镜包含字幕文案、画面描述、AI 图像提示词。

**操作**：
使用 system prompt（见 `references/prompts.md` 第 2 节），输入阶段 1 的 content，输出：
```json
{
  "list": [
    {
      "story_name": "分镜名称",
      "desc": "画面描述",
      "cap": "字幕文案（一句话）",
      "desc_promopt": "图像生成提示词"
    }
  ],
  "keywords": ["重点词1", "重点词2"]
}
```

然后在 list 开头插入引言分镜（模仿原工作流 node 150774 的逻辑）：
```python
list.insert(0, {
    "story_name": "引言",
    "desc": "每日精读一本书",
    "cap": f"3分钟精读一本书，今天我们读《{book_name}》",
    "desc_promopt": "每日精读一本书"
})
```

**风格约束**：扁平插画风，人物卡通风简洁线条，背景扁平化符号，柔和明亮低饱和度色调。

### 阶段 3：生成标题进度条

**目标**：根据文案内容划分为 4 个板块，每板块 6 字以内标题，用于视频顶部进度条显示。

**操作**：
使用 system prompt（见 `references/prompts.md` 第 3 节），输出 4 个标题（title1-title4）。

**使用方式**：4 个标题通过 `segments.json` 的 `chapter_titles` 字段传入 `compose_video.py`，在视频顶部渲染为进度条（当前板块橙色高亮 + 底部进度线）。同时需要 `segment_chapters` 字段指定每个分镜所属的板块索引（0-3），未指定时自动均匀分配。

### 阶段 4：生成素材（并行）

本阶段生成视频所需的全部素材：

#### 4a. AI 插图生成

对每个分镜的 `desc_promopt`，调用当前平台的**图像生成工具**生成插图。

**统一风格参数**（原工作流图像生成节点配置）：
- 尺寸：1024x768
- 风格：扁平风（flat illustration）
- 主角上衣 #FF7F72，裤子 #243139
- 30% 透明玻璃效果背景
- 负向提示词：无

**各平台调用方式**：

- **WorkBuddy**：调用 `ImageGen` 工具（通过 DeferExecuteTool），参数 `prompt` = desc_promopt，`size` = "1024x768"
- **OpenClaw**：调用 frontmatter 中声明的图像生成 tool
- **Codex CLI**：运行 `python3 scripts/generate_image.py --prompt "<desc_promopt>" --output "scene_001.png"`（需自备 API Key）
- **TRAE Work**：通过 MCP 调用已接入的图像生成服务

> 生成的图片统一命名为 `scene_000.png` ~ `scene_NNN.png`，存放到 `output/{book_name}/images/` 目录。

#### 4b. TTS 语音合成

对每个分镜的 `cap`（字幕文案），使用 TTS 引擎生成 MP3 音频，同时生成词级时间戳（保存为同名 `.words.json` 文件，用于阶段 5 的逐句字幕精确同步）。

**双引擎架构**：
- **火山引擎 TTS**（默认）：V1 API + X-Api-Key 认证，豆包语音合成 2.0 音色，中文自然度最高，可商用，需设置环境变量 `VOLC_TTS_API_KEY`
- **edge-tts**（备选）：免费无需配置，原生 WordBoundary 词级时间戳，未设置火山引擎凭证时自动回退

**默认音色**：
- 火山引擎：`zh_female_zhixingnv_uranus_bigtts`（知性女声 2.0，适合读书解说）
- edge-tts：`zh-CN-XiaoxiaoNeural`（晓晓，女声）

查看所有可用音色：`python3 scripts/generate_audio.py --list-voices`

运行（所有平台通用，自动选择引擎）：
```bash
python3 scripts/generate_audio.py --text "<字幕>" --output "audio_001.mp3"
```

指定引擎或音色：
```bash
# 强制使用火山引擎
python3 scripts/generate_audio.py --text "<字幕>" --output "audio_001.mp3" --engine volcano --voice zh_female_zhixingnv_uranus_bigtts

# 强制使用 edge-tts
python3 scripts/generate_audio.py --text "<字幕>" --output "audio_001.mp3" --engine edge --voice zh-CN-XiaoxiaoNeural
```

批量模式：
```bash
python3 scripts/generate_audio.py --batch captions.json --output-dir audio/ --voice "zh_female_zhixingnv_uranus_bigtts"
```

#### 4c. 开场封面图

为视频第一帧生成专属封面图（1920x1080），包含书名、作者、品牌文字。

**操作**：运行 `python3 scripts/generate_cover.py`

```bash
# 用第一张分镜图做模糊背景（推荐，与视频风格一致）
python3 scripts/generate_cover.py \
  --book-name "原子习惯" \
  --author "James Clear" \
  --output output/原子习惯/images/cover.png \
  --bg output/原子习惯/images/scene_000.png

# 无背景图，使用深蓝渐变
python3 scripts/generate_cover.py \
  --book-name "原子习惯" \
  --author "James Clear" \
  --output output/原子习惯/images/cover.png
```

**封面布局**：
- 顶部：「3 分钟精读一本书」品牌文字 + 橙色分隔线（#FF7F72，与分镜主角上衣同色）
- 中部：书名大字（自动换行居中，80pt）
- 中下：作者名（42pt）
- 底部：账号名称水印（**可选**，通过 `--ip-name` 指定，不传则不显示）

**字体**：自动检测系统中文字体（Windows: 微软雅黑 / macOS: PingFang SC / Linux: Noto Sans CJK），无需手动修改。

> 封面图在阶段 5 合成时，通过 segments.json 中的 `cover` 字段指定，会替换第一分镜的图片（保持开场音频不变）。
>
> ```json
> {
>   "output": "output/书名_三分钟精读书.mp4",
>   "cover": "output/书名/images/cover.png",
>   "chapter_titles": ["开篇引言", "核心方法", "实践技巧", "总结"],
>   "segment_chapters": [0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3],
>   "keywords": ["原子习惯", "微小改变", "复利效应"],
>   "segments": [
>     {"image": "images/scene_000.png", "audio": "audio/audio_000.mp3", "caption": "字幕文本"},
>     ...
>   ]
> }
> ```
> - `cover`：可选，封面图路径，替换第一分镜图片
> - `chapter_titles`：可选，板块标题列表，用于顶部进度条显示
> - `segment_chapters`：可选，每个分镜所属板块索引（0-based），未提供时自动均匀分配
> - `keywords`：可选，关键词列表，字幕中匹配到的关键词显示为橙色高亮

### 阶段 5：视频合成

**目标**：将所有素材合成为最终 MP4 视频。

**操作**：运行 `python3 scripts/compose_video.py`，该脚本执行：
1. 计算每个分镜时长（基于 TTS 音频时长 + 0.3s 间隔）
2. 图片缩放/裁剪为 1920x1080（16:9）
3. 为每个分镜添加 **Ken Burns 缓慢缩放**效果（偶数分镜放大 1.0→1.1，奇数分镜缩小 1.1→1.0）
4. 为每个分镜添加 **0.3s 淡入淡出转场**（dip-to-black）
5. 使用 ffmpeg 将图片+音频合成为视频片段
6. **进度条 overlay**：顶部显示板块标题（当前板块橙色高亮+实心圆点，其余灰色+空心圆点），底部进度线显示总体播放进度
7. 生成**逐句单行 ASS 字幕**（基于 TTS 词级时间戳精确同步语音，按标点+字数拆分为单行短句，白色加粗文字+黑色描边，**关键词橙色高亮**）
8. 拼接所有片段为完整视频

**字幕参数**（对应原工作流 add_captions_1 节点）：
- 字体颜色：白色 (#FFFFFF)
- 关键词高亮：橙色 (#FF7F72)，通过 ASS 内联颜色标签 `{\c&H727FFF&}` 实现
- 边框颜色：黑色 (#000000)
- 字号：64pt（加粗）
- 位置：底部居中（MarginV=30）
- 字体：**自动检测**系统可用中文字体（Windows: 微软雅黑 / macOS: PingFang SC / Linux: Noto Sans CJK SC），无需手动修改
- 字幕格式：**ASS**（Advanced SubStation Alpha），支持行内颜色标签，关键词高亮显示
- **逐句单行显示**：利用 TTS 词级时间戳（火山引擎基于音频时长估算 / edge-tts WordBoundary 原生精确），将长字幕按标点拆分为单行短句，每句时间与语音同步

**进度条参数**：
- 位置：画面顶部（80px 高度）
- 背景：半透明深色（alpha=130）
- 当前板块：橙色 (#FF7F72) 文字 + 实心圆点
- 非当前板块：灰色 (#AAAAAA) 文字 + 空心圆点
- 底部进度线：橙色填充 + 深灰底色，显示总体播放进度
- 字体：自动检测系统中文字体，44pt

**动态效果参数**：
- Ken Burns 缩放速率：每帧 +0.0008（约 3 秒内从 1.0 到 1.024）
- 缩放上限：1.1x
- 转场淡入淡出时长：0.3s（短于 0.6s 的分镜自动减半）

### 输出

最终输出：`output/{book_name}_三分钟精读书.mp4`

## 跨平台安装

### WorkBuddy

技能已安装在 `~/.workbuddy/skills/book-video-generator/`，直接使用。

### OpenClaw

```bash
# 复制到 OpenClaw 技能目录
cp -r ~/.workbuddy/skills/book-video-generator ~/.openclaw/skills/

# 或通过 ClawHub 安装（如果已发布）
openclaw skills install book-video-generator
```

如需在 frontmatter 中声明图像生成 tool，参考 OpenClaw 文档的 `tools` 字段定义。

### Codex CLI

```bash
# 1. 开启 Skills 功能（如未开启）
echo '[features]\nsskills = true' >> ~/.codex/config.toml

# 2. 复制技能目录
cp -r ~/.workbuddy/skills/book-video-generator ~/.codex/skills/

# 3. 重启 Codex CLI
# 4. 输入 /skills 确认技能已加载
```

Codex CLI 无内置图像生成，需在 `scripts/` 目录中添加 `generate_image.py` 脚本，调用外部 API（如 OpenAI DALL-E、Stability AI）。脚本需接受 `--prompt` 和 `--output` 参数。

### TRAE Work

```
1. 打开 TRAE Work → 规则和技能 → 技能 → 创建 → 导入文件
2. 上传 SKILL.md 文件
3. 确保 scripts/ 和 references/ 目录也复制到技能目录
```

TRAE Work 通过 MCP 接入图像生成服务。在 TRAE 的 MCP 配置中添加火山引擎或通义万相的图像生成 MCP，然后在执行阶段 4a 时通过 MCP 调用。

## 原工作流参考

原始扣子工作流文件位于 `references/workflow-original.yaml`，包含 30+ 节点的完整链路：
```
开始 → LLM(DeepSeek V3.2)生成书评 → 上标题总结 → 分镜画面描述
→ 代码拼接引言 → 批量图像生成+抠图 → TTS语音合成
→ 创建剪映草稿 → 批量添加图片/字幕/音频 → 保存草稿 → 结束
```

原始流程依赖**剪映小助手插件**（视频合成核心）、扣子内置**图像生成+抠图**和**TTS**插件。
本 Skill 使用 ffmpeg、edge-tts、平台图像生成工具替代。

## 快速使用示例

用户说："帮我生成《原子习惯》James Clear 的 3 分钟精读视频"

执行流程：
1. 搜索"原子习惯 James Clear 简介 书评"
2. 用阶段 1 prompt 生成书评文案
3. 用阶段 2 prompt 生成分镜脚本
4. 用阶段 3 prompt 生成标题进度条
5. 对每个分镜：图像生成工具生成插图 + TTS 生成配音（火山引擎默认 / edge-tts 备选）
6. compose_video.py 合成最终视频
7. 输出 `output/原子习惯_三分钟精读书.mp4`

## 资源文件

- `references/prompts.md` — 所有 LLM 提示词原文（平台无关，可直接复用）
- `references/workflow-original.yaml` — 原始扣子工作流（完整 YAML 备份）
- `scripts/compose_video.py` — 视频合成脚本（纯 Python + ffmpeg，跨平台，含 Ken Burns 缩放 + 淡入淡出转场 + 字体自动检测 + 封面图支持 + 逐句单行 ASS 字幕精确语音同步 + 关键词高亮 + 顶部进度条）
- `scripts/generate_audio.py` — TTS 语音生成脚本（纯 Python，双引擎：火山引擎 TTS V1 API + X-Api-Key 默认 / edge-tts 备选，含词级时间戳输出，自动检测凭证切换引擎）
- `scripts/generate_cover.py` — 封面图生成脚本（纯 Python + Pillow，自动换行 + 模糊背景 + 字体自动检测）
