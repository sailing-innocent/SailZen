#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file test_image_download.py
# @brief Test image download from dogapi.cc and validate format
# @author sailing-innocent
# @date 2026-05-02
# @version 1.0
# ---------------------------------
"""Test image download from dogapi.cc URL response.

Usage:
    uv run scripts/test_image_download.py
"""

import os
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[1] / ".env.prod", override=True)

API_KEY = os.getenv("DOGAPI_KEY", "")
BASE_URL = os.getenv("DOGAPI_BASE", "https://www.dogapi.cc/v1").rstrip("/")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def test_generation():
    url = f"{BASE_URL}/images/generations"
    payload = {
        "model": "gpt-image-2",
        "prompt": "a cute anime girl with blue hair",
        "n": 1,
        "size": "1024x1024",
    }
    print("[1] Generating image...")
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=120)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Failed: {resp.text[:500]}")
        return

    body = resp.json()
    print(f"Response keys: {list(body.keys())}")
    data = body.get("data", [])
    if not data:
        print("No data in response")
        return

    first = data[0]
    print(f"First item keys: {list(first.keys())}")

    # Check b64_json
    b64 = first.get("b64_json")
    if b64:
        print(f"b64_json present: {len(b64)} chars")
    else:
        print("b64_json: NOT present")

    # Check URL
    image_url = first.get("url")
    if image_url:
        print(f"URL present: {image_url}")
        print("[2] Downloading image from URL...")
        r = requests.get(image_url, timeout=60)
        print(f"Download status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('Content-Type', 'N/A')}")
        print(f"Content-Length: {len(r.content)} bytes")

        # Save to file for inspection
        tmp_path = Path("test_image.png")
        tmp_path.write_bytes(r.content)
        print(f"Saved to: {tmp_path.absolute()}")

        # Check magic bytes
        magic = r.content[:8]
        print(f"Magic bytes: {magic.hex()}")
        if magic[:4] == b'\x89PNG':
            print("Format: PNG (valid)")
        elif magic[:2] == b'\xff\xd8':
            print("Format: JPEG (valid)")
        elif magic[:4] == b'RIFF' and magic[8:12] == b'WEBP':
            print("Format: WEBP (valid)")
        else:
            print("Format: UNKNOWN (may be invalid)")
            # Print first 200 chars as text
            try:
                print(f"Text preview: {r.content[:200].decode('utf-8', errors='replace')}")
            except Exception:
                pass
    else:
        print("URL: NOT present")

if __name__ == "__main__":
    test_generation()
