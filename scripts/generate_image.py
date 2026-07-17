#!/usr/bin/env python3
"""
跨平台 AI 图像生成脚本

供没有内置图像生成工具的平台使用（如 Codex CLI）。
支持多种图像生成 API，通过环境变量或命令行参数配置。

支持的 API：
1. OpenAI DALL-E（需要 OPENAI_API_KEY）
2. Stability AI（需要 STABILITY_API_KEY）
3. 火山引擎（需要 VOLCENGINE_AK 和 VOLCENCE_SK）
4. 本地 Stable Diffusion WebUI（需要 SD_WEBUI_URL）

使用方法：
  python3 generate_image.py --prompt "描述文本" --output "image.png"
  python3 generate_image.py --prompt "描述文本" --output "image.png" --api openai
  python3 generate_image.py --batch storyboard.json --output-dir images/

环境变量：
  OPENAI_API_KEY       - OpenAI API Key
  STABILITY_API_KEY    - Stability AI API Key
  VOLCENGINE_AK        - 火山引擎 Access Key
  VOLCENGINE_SK        - 火山引擎 Secret Key
  SD_WEBUI_URL         - 本地 SD WebUI 地址（默认 http://127.0.0.1:7860）
  IMAGE_API            - 默认使用的 API（openai/stability/volcengine/local）
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error


def generate_with_openai(prompt: str, output_path: str, size: str = "1024x1024"):
    """使用 OpenAI DALL-E 3 生成图像"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("未设置 OPENAI_API_KEY 环境变量")

    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = json.dumps({
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "b64_json",
    }).encode()

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    image_data = base64.b64decode(result["data"][0]["b64_json"])
    with open(output_path, "wb") as f:
        f.write(image_data)
    return output_path


def generate_with_stability(prompt: str, output_path: str, size: str = "1024x1024"):
    """使用 Stability AI 生成图像"""
    api_key = os.environ.get("STABILITY_API_KEY")
    if not api_key:
        raise RuntimeError("未设置 STABILITY_API_KEY 环境变量")

    # 解析尺寸
    w, h = size.split("x")
    url = "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    # 使用 multipart/form-data
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body_parts = []
    body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"prompt\"\r\n\r\n{prompt}\r\n")
    body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"width\"\r\n\r\n{w}\r\n")
    body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"height\"\r\n\r\n{h}\r\n")
    body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"samples\"\r\n\r\n1\r\n")
    body_parts.append(f"--{boundary}--\r\n")
    body = "".join(body_parts).encode()

    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    image_data = base64.b64decode(result["artifacts"][0]["base64"])
    with open(output_path, "wb") as f:
        f.write(image_data)
    return output_path


def generate_with_volcengine(prompt: str, output_path: str, size: str = "1024x1024"):
    """使用火山引擎即梦 AI 生成图像"""
    ak = os.environ.get("VOLCENGINE_AK")
    sk = os.environ.get("VOLCENGINE_SK")
    if not ak or not sk:
        raise RuntimeError("未设置 VOLCENGINE_AK / VOLCENGINE_SK 环境变量")

    # 火山引擎需要签名认证，这里简化处理
    # 实际使用时建议安装 volcengine-python-sdk
    try:
        import volcenginesdkcore
        import volcenginesdkvisualapi
    except ImportError:
        os.system(f"{sys.executable} -m pip install volcenginesdkcore volcenginesdkvisualapi -q")
        import volcenginesdkcore
        import volcenginesdkvisualapi

    api = volcenginesdkvisualapi.VisualApiService()
    response = api.text2image(
        volcenginesdkvisualapi.VisualApiText2ImageRequest(
            req_key="high_aes_general_v21",
            prompt=prompt,
            width=int(size.split("x")[0]),
            height=int(size.split("x")[1]),
        ),
    )

    image_data = base64.b64decode(response.data.binary_data[0])
    with open(output_path, "wb") as f:
        f.write(image_data)
    return output_path


def generate_with_local_sd(prompt: str, output_path: str, size: str = "1024x1024"):
    """使用本地 Stable Diffusion WebUI 生成图像"""
    base_url = os.environ.get("SD_WEBUI_URL", "http://127.0.0.1:7860")
    w, h = size.split("x")

    url = f"{base_url}/sdapi/v1/txt2img"
    data = json.dumps({
        "prompt": prompt,
        "width": int(w),
        "height": int(h),
        "steps": 30,
        "batch_size": 1,
    }).encode()

    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    image_data = base64.b64decode(result["images"][0])
    with open(output_path, "wb") as f:
        f.write(image_data)
    return output_path


# API 注册表
API_PROVIDERS = {
    "openai": generate_with_openai,
    "stability": generate_with_stability,
    "volcengine": generate_with_volcengine,
    "local": generate_with_local_sd,
}


def generate_image(prompt: str, output_path: str, api: str = None, size: str = "1024x768"):
    """根据指定 API 生成图像"""
    if api is None:
        api = os.environ.get("IMAGE_API", "openai")

    if api not in API_PROVIDERS:
        raise ValueError(f"不支持的 API: {api}，可选: {list(API_PROVIDERS.keys())}")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    return API_PROVIDERS[api](prompt, output_path, size)


def batch_generate(storyboard_path: str, output_dir: str, api: str = None, size: str = "1024x768"):
    """批量生成分镜图像"""
    with open(storyboard_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenes = data.get("list", data if isinstance(data, list) else [])
    results = []

    for i, scene in enumerate(scenes):
        prompt = scene.get("desc_promopt", scene.get("desc", ""))
        output = os.path.join(output_dir, f"scene_{i:03d}.png")
        try:
            generate_image(prompt, output, api, size)
            results.append(output)
            print(f"[{i+1}/{len(scenes)}] {output}")
        except Exception as e:
            print(f"[{i+1}/{len(scenes)}] FAILED: {e}")
            results.append(None)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="跨平台 AI 图像生成")
    parser.add_argument("--prompt", type=str, help="图像生成提示词")
    parser.add_argument("--output", type=str, default="output.png", help="输出路径")
    parser.add_argument("--api", type=str, help="API 提供商: openai/stability/volcengine/local")
    parser.add_argument("--size", type=str, default="1024x768", help="图像尺寸")
    parser.add_argument("--batch", type=str, help="批量模式: storyboard.json 路径")
    parser.add_argument("--output-dir", type=str, default="images", help="批量输出目录")

    args = parser.parse_args()

    if args.batch:
        batch_generate(args.batch, args.output_dir, args.api, args.size)
    elif args.prompt:
        generate_image(args.prompt, args.output, args.api, args.size)
        print(f"Image saved: {args.output}")
    else:
        print("请提供 --prompt 或 --batch 参数")
        print("可用 API:", list(API_PROVIDERS.keys()))
        print("环境变量 IMAGE_API 可设置默认 API")
        sys.exit(1)
