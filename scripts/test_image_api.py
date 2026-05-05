#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file test_image_api.py
# @brief Debug image generation API to find working request format
# @author sailing-innocent
# @date 2026-05-02
# @version 1.0
# ---------------------------------
"""Test script to debug dogapi.cc image generation API 500 errors.

Tries various payload combinations to find the right request format.
Usage:
    uv run scripts/test_image_api.py
"""

import os
import sys
import json
import requests
import time
from pathlib import Path

# Load env
sys.path.insert(0, str(Path(__file__).parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[1] / ".env.prod", override=True)

API_KEY = os.getenv("DOGAPI_KEY", "")
BASE_URL = os.getenv("DOGAPI_BASE", "https://www.dogapi.cc/v1").rstrip("/")
MODEL = "gpt-image-2"
PROMPT = "a cute anime girl with blue hair"

if not API_KEY:
    print("ERROR: DOGAPI_KEY not found in .env.prod")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def try_request(name: str, payload: dict, timeout: int = 15) -> bool:
    url = f"{BASE_URL}/images/generations"
    print(f"\n[TEST] {name} (timeout={timeout}s)", flush=True)
    start = time.time()
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=timeout)
        elapsed = time.time() - start
        print(f"Status: {resp.status_code} (took {elapsed:.1f}s)", flush=True)
        if resp.status_code == 200:
            body = resp.json()
            print(f"SUCCESS! Response keys: {list(body.keys())}", flush=True)
            return True
        else:
            text = resp.text[:500]
            print(f"FAILED: {text}", flush=True)
            return False
    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"TIMEOUT after {elapsed:.1f}s", flush=True)
        return False
    except Exception as exc:
        elapsed = time.time() - start
        print(f"EXCEPTION after {elapsed:.1f}s: {exc}", flush=True)
        return False

print(f"API Base: {BASE_URL}")
print(f"API Key prefix: {API_KEY[:8]}...")

# Run multiple times to check consistency
tests = [
    ("Run 1 - 90s timeout", 90),
    ("Run 2 - 90s timeout", 90),
]

success_count = 0
for name, timeout in tests:
    if try_request(name, {
        "model": MODEL,
        "prompt": PROMPT,
        "n": 1,
        "size": "1024x1024",
    }, timeout=timeout):
        success_count += 1

print(f"\n{'='*60}")
print(f"Results: {success_count}/{len(tests)} tests succeeded")
