# -*- coding: utf-8 -*-
# @file generate_gpt_image2.py
# @brief 使用 OpenAI /v1/chat/completions 端点生成图片 (gpt-image-2)
# @author sailing-innocent
# @date 2026-04-27
# @version 1.0
# ---------------------------------
#
# 用法:
#   uv run scripts/generate_gpt_image2.py --prompt "A futuristic city" --output output.png
#   uv run scripts/generate_gpt_image2.py --prompt prompt.txt --output output.png
#
# 环境变量 (.env.dev):
#   OPENAI_IMAGE_ENDPOINT=https://api.openai.com  (base URL，不含 /v1/chat/completions)
#   OPENAI_IMAGE_API_KEY=sk-xxxxxxxx
# ---------------------------------

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate images via OpenAI /v1/chat/completions (gpt-image-2)"
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Image generation prompt text, or path to a .txt file containing the prompt",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output file path for the generated image (e.g. output.png)",
    )
    parser.add_argument(
        "--size",
        default="1024x1024",
        choices=["1024x1024", "1536x1024", "1024x1536"],
        help="Image size (default: 1024x1024)",
    )
    parser.add_argument(
        "--quality",
        default="auto",
        choices=["low", "medium", "high", "auto"],
        help="Image quality (default: auto)",
    )
    return parser.parse_args()


def load_prompt(prompt_arg: str) -> str:
    """Load prompt from a file if it's a valid path, otherwise use as-is."""
    prompt_path = Path(prompt_arg)
    if prompt_path.is_file() and prompt_path.suffix in (".txt", ".md"):
        print(f"📄 Reading prompt from file: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8").strip()
    return prompt_arg


def main():
    args = parse_args()

    # Load environment variables from .env.dev
    env_path = Path(__file__).resolve().parent.parent / ".env.dev"
    if not env_path.exists():
        print(f"❌ Environment file not found: {env_path}")
        sys.exit(1)
    load_dotenv(env_path)

    endpoint = os.getenv("OPENAI_IMAGE_ENDPOINT")
    api_key = os.getenv("OPENAI_IMAGE_API_KEY")

    if not endpoint:
        print("❌ OPENAI_IMAGE_ENDPOINT is not set in .env.dev")
        sys.exit(1)
    if not api_key:
        print("❌ OPENAI_IMAGE_API_KEY is not set in .env.dev")
        sys.exit(1)

    # Normalize base_url: ensure it ends with /v1 (but not /v1/v1)
    base_url = endpoint.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = base_url + "/v1"

    prompt = load_prompt(args.prompt)
    print(f"🎨 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print(f"📐 Size: {args.size}, Quality: {args.quality}")
    print(f"🔗 Base URL: {base_url}")
    print(f"🔑 API Key: {api_key[:8]}...{api_key[-4:]}")

    # -----------------------------------------------------------
    # Use raw httpx with OpenAI SDK-style headers (x-stainless-*)
    # -----------------------------------------------------------
    import platform
    import sys as _sys

    request_body = {
        "model": "gpt-image-2",
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image"],
        "image": {"size": args.size, "quality": args.quality},
    }

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print(f"🚀 POST {url}")
    print(f"📦 Request body (preview): {json.dumps({k: v for k, v in request_body.items() if k != 'messages'}, ensure_ascii=False)}")

    try:
        with httpx.Client(timeout=300.0) as http:
            resp = http.post(url, json=request_body, headers=headers)
    except httpx.ConnectError as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    print(f"📬 Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"❌ Server rejected the request ({resp.status_code})")
        print(f"Response headers: {dict(resp.headers)}")
        print(f"Response body: {resp.text[:2000]}")
        sys.exit(1)

    data = resp.json()

    # -----------------------------------------------------------
    # Extract image from response
    # The chat completions image response has choices[].message.content
    # which is a list of content parts. Each image part looks like:
    #   {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    # -----------------------------------------------------------
    image_b64 = None

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        content = None

    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                url_str = part.get("image_url", {}).get("url", "")
                if url_str.startswith("data:"):
                    image_b64 = url_str.split(",", 1)[1]
                else:
                    image_b64 = url_str
                break
    elif isinstance(content, str):
        # Some endpoints return base64 directly as string content
        # Heuristic: if it's long and has no spaces, treat as base64
        if len(content) > 1000 and " " not in content[:200]:
            image_b64 = content

    if not image_b64:
        print("❌ No image data found in response")
        print(f"Response (preview): {json.dumps(data, ensure_ascii=False)[:2000]}")
        sys.exit(1)

    # Decode and save the image
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image_bytes = base64.b64decode(image_b64)
    output_path.write_bytes(image_bytes)

    print(f"✅ Image saved to: {output_path.resolve()}")
    print(f"📊 File size: {len(image_bytes) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
