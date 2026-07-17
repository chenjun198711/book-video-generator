# 跨平台适配指南

本文件详细说明 `book-video-generator` 技能在各 AI Agent 平台上的安装和适配方法。

技能遵循 [Agent Skills 开放标准](https://agentskills.io)，核心组件（SKILL.md 格式、LLM 提示词、Python 脚本）跨平台通用，仅需适配平台专有工具。

---

## 平台兼容性总览

| 组件 | WorkBuddy | OpenClaw | Codex CLI | TRAE Work |
|------|-----------|----------|-----------|-----------|
| SKILL.md 格式 | 原生 | 兼容 | 兼容 | 兼容 |
| LLM 提示词 | 直接用 | 直接用 | 直接用 | 直接用 |
| Python 脚本 | 直接用 | 直接用 | 直接用 | 直接用 |
| 联网搜索 | WebSearch | 内置 | Shell/MCP | 内置 |
| 图像生成 | ImageGen | 插件 | generate_image.py | MCP |
| 技能目录 | ~/.workbuddy/skills/ | ~/.openclaw/skills/ | ~/.codex/skills/ | ~/.trae/skills/ |

---

## 1. WorkBuddy（当前平台）

无需额外配置，技能已安装。

- 联网搜索：内置 `WebSearch` 工具
- 图像生成：内置 `ImageGen` 延迟工具（通过 ToolSearch + DeferExecuteTool 调用）
- Python 运行：使用托管 Python `C:/Users/chenjun/.workbuddy/binaries/python/versions/3.13.12/python.exe`

---

## 2. OpenClaw

### 安装

```bash
# 方式一：直接复制
cp -r ~/.workbuddy/skills/book-video-generator ~/.openclaw/skills/

# 方式二：通过 ClawHub 安装（需先发布）
openclaw skills install book-video-generator

# 方式三：从 Git 仓库安装
openclaw skills install git:yourname/book-video-generator
```

### 工具适配

OpenClaw 支持在 SKILL.md frontmatter 中声明 `tools`。如需原生图像生成，可在 frontmatter 中添加：

```yaml
tools:
  - name: generate_image
    description: "根据提示词生成插图"
    handler: ./scripts/generate_image.py
    parameters:
      prompt:
        type: string
        required: true
        description: "图像生成提示词"
      output:
        type: string
        required: true
        description: "输出文件路径"
```

联网搜索：OpenClaw 内置 web search 能力，无需额外配置。

### 验证

```bash
openclaw skills verify book-video-generator
```

---

## 3. Codex CLI（OpenAI）

### 安装

```bash
# 1. 开启 Skills 功能（config.toml）
cat >> ~/.codex/config.toml << 'EOF'
[features]
skills = true
EOF

# 2. 复制技能目录
cp -r ~/.workbuddy/skills/book-video-generator ~/.codex/skills/

# 3. 重启 Codex CLI

# 4. 验证
# 在 Codex CLI 中输入 /skills，确认 book-video-generator 出现
```

### 工具适配

**联网搜索**：Codex CLI 无内置搜索，两种方案：

方案 A — Shell 命令搜索（免安装）：
```bash
curl -s "https://www.google.com/search?q=书名+作者+简介" | python3 -c "..."
```

方案 B — 安装搜索 MCP 插件：
```bash
# 在 Codex 配置中添加搜索 MCP
```

**图像生成**：Codex CLI 无内置图像生成，使用 `scripts/generate_image.py`：

```bash
# 设置 API Key（任选其一）
export OPENAI_API_KEY="sk-..."
# 或
export STABILITY_API_KEY="sk-..."
# 或
export IMAGE_API="local" SD_WEBUI_URL="http://127.0.0.1:7860"

# 生成单张
python3 scripts/generate_image.py --prompt "描述" --output "scene_001.png"

# 批量生成（从 storyboard.json）
python3 scripts/generate_image.py --batch output/书名/02_storyboard.json --output-dir output/书名/images/
```

### 注意事项

- Codex CLI 的 SKILL.md frontmatter 支持 `metadata.short-description` 字段
- 技能存放路径也可在项目级 `.codex/skills/` 或 repo 根 `.agents/skills/`
- Codex 的渐进式披露机制会在启动时仅加载 name + description

---

## 4. TRAE Work（字节跳动）

### 安装

```
1. 打开 TRAE Work IDE
2. 进入「规则和技能 → 技能 → 创建」
3. 选择「导入文件」，上传 SKILL.md
4. 将 scripts/ 和 references/ 目录复制到技能目录下
```

技能目录结构（TRAE 只扫描一级子目录）：
```
~/.trae/skills/
  book-video-generator/
    SKILL.md
    scripts/
      compose_video.py
      generate_audio.py
      generate_image.py
    references/
      prompts.md
      workflow-original.yaml
```

### 工具适配

**联网搜索**：TRAE Work 内置联网搜索能力，直接可用。

**图像生成**：通过 MCP 接入图像生成服务：

1. 在 TRAE 的 MCP 配置中添加火山引擎图像生成 MCP（或通义万相、其他图像 MCP）
2. 执行阶段 4a 时，通过 MCP 调用图像生成服务
3. 或使用 `scripts/generate_image.py` + 环境变量方式

### 注意事项

- TRAE 只扫描一级子目录，不要嵌套太深
- TRAE 支持自定义智能体，可创建专门的读书视频生成 Agent
- TRAE 的 MCP 生态有 1.1 万+ 插件可用

---

## 5. 其他兼容平台

Agent Skills 开放标准还被以下平台支持，本技能同样适用：

- **Claude Code** — `~/.claude/skills/`，与 WorkBuddy 格式几乎完全一致
- **Cursor** — 支持 Agent Skills 标准
- **GitHub Copilot** — 支持 Agent Skills 标准
- **VS Code** — 通过 Agent Skills 扩展
- **Letta** — 支持 Agent Skills 标准

安装方式统一为：将技能目录复制到对应平台的 skills 目录下。

---

## 通用注意事项

### Python 环境

所有平台执行脚本时使用 `python3`（或 Windows 上的 `python`）。确保以下依赖已安装：

```bash
pip install edge-tts imageio-ffmpeg pillow
```

如使用 `generate_image.py`，还需根据选择的 API 安装对应依赖：
```bash
# 火山引擎
pip install volcenginesdkcore volcenginesdkvisualapi

# OpenAI / Stability / Local SD 无需额外安装（使用标准库 urllib）
```

### 字体

视频字幕烧录需要中文字体支持：

| 系统 | 字体路径 | FontName |
|------|----------|----------|
| Windows | C:/Windows/Fonts/msyh.ttc | Microsoft YaHei |
| macOS | /System/Library/Fonts/PingFang.ttc | PingFang SC |
| Linux | /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc | Noto Sans CJK SC |

在 `compose_video.py` 中修改 `style` 变量的 `FontName` 字段。

### 路径分隔符

Python 脚本中使用 `os.path.join()` 和 `pathlib.Path`，自动适配不同操作系统的路径分隔符。ffmpeg 的 subtitles 滤镜需要特殊处理 Windows 路径（已在 compose_video.py 中处理）。

---

## 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-17 | 1.0 | 从扣子工作流移植到 WorkBuddy |
| 2026-07-17 | 1.1 | 修复 ffmpeg 检测、改用两步法合成 |
| 2026-07-17 | 2.0 | 跨平台适配，支持 OpenClaw / Codex / TRAE Work |
