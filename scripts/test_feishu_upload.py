#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file test_feishu_upload.py
# @brief Test Feishu image upload with various methods
# @author sailing-innocent
# @date 2026-05-02
# @version 1.0
# ---------------------------------
"""Test Feishu image upload.

Usage:
    uv run python scripts/test_feishu_upload.py
"""

import os
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from sail_bot.config import load_config

config = load_config("kimix.bot.yaml")

import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody

# Create client
client = lark.Client.builder() \
    .app_id(config.app_id) \
    .app_secret(config.app_secret) \
    .log_level(lark.LogLevel.INFO) \
    .build()

# Read the test image
test_image = Path("test_image.png")
if not test_image.exists():
    print("ERROR: test_image.png not found. Run test_image_download.py first.")
    sys.exit(1)

image_bytes = test_image.read_bytes()
print(f"Image size: {len(image_bytes)} bytes")

# Test 1: raw bytes
print("\n[TEST 1] Upload via Lark SDK (raw bytes)...")
try:
    body = (
        CreateImageRequestBody.builder()
        .image(image_bytes)
        .image_type("message")
        .build()
    )
    req = CreateImageRequest.builder().request_body(body).build()
    resp = client.im.v1.image.create(req)
    print(f"Success: {resp.success()}")
    if not resp.success():
        print(f"Error: {resp.code} {resp.msg}")
    else:
        print(f"image_key: {resp.data.image_key}")
except Exception as exc:
    print(f"Exception: {exc}")

# Test 2: BytesIO
print("\n[TEST 2] Upload via Lark SDK (BytesIO)...")
try:
    body = (
        CreateImageRequestBody.builder()
        .image(io.BytesIO(image_bytes))
        .image_type("message")
        .build()
    )
    req = CreateImageRequest.builder().request_body(body).build()
    resp = client.im.v1.image.create(req)
    print(f"Success: {resp.success()}")
    if not resp.success():
        print(f"Error: {resp.code} {resp.msg}")
    else:
        print(f"image_key: {resp.data.image_key}")
except Exception as exc:
    print(f"Exception: {exc}")

# Test 3: file path
print("\n[TEST 3] Upload via Lark SDK (file path string)...")
try:
    body = (
        CreateImageRequestBody.builder()
        .image(str(test_image.absolute()))
        .image_type("message")
        .build()
    )
    req = CreateImageRequest.builder().request_body(body).build()
    resp = client.im.v1.image.create(req)
    print(f"Success: {resp.success()}")
    if not resp.success():
        print(f"Error: {resp.code} {resp.msg}")
    else:
        print(f"image_key: {resp.data.image_key}")
except Exception as exc:
    print(f"Exception: {exc}")

# Test 4: open file object
print("\n[TEST 4] Upload via Lark SDK (open file object)...")
try:
    with open(test_image, "rb") as f:
        body = (
            CreateImageRequestBody.builder()
            .image(f)
            .image_type("message")
            .build()
        )
        req = CreateImageRequest.builder().request_body(body).build()
        resp = client.im.v1.image.create(req)
    print(f"Success: {resp.success()}")
    if not resp.success():
        print(f"Error: {resp.code} {resp.msg}")
    else:
        print(f"image_key: {resp.data.image_key}")
except Exception as exc:
    print(f"Exception: {exc}")
