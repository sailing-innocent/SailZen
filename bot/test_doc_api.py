#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file test_doc_api.py
# @brief 测试飞书文档API
# @brief Test Feishu Document API
# ---------------------------------
"""测试飞书文档API

Usage:
    uv run bot/test_doc_api.py
"""

import os
import sys
from pathlib import Path

# 加载环境变量
env_files = [".env", ".env.local", ".env.dev"]
for filename in env_files:
    env_path = Path(filename)
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"')
                        if key not in os.environ:
                            os.environ[key] = value
        except Exception:
            pass

import httpx
from datetime import datetime, timedelta


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """获取tenant_access_token."""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = httpx.post(
        url, json={"app_id": app_id, "app_secret": app_secret}, timeout=30
    )

    if resp.status_code != 200:
        raise Exception(f"Failed to get token: {resp.text}")

    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Token error: {data.get('msg')}")

    return data["tenant_access_token"]


def test_create_document(token: str, title: str = None):
    """测试创建文档."""
    if title is None:
        title = f"API测试_{datetime.now().strftime('%m%d_%H%M%S')}"

    url = "https://open.feishu.cn/open-apis/drive/v1/files"

    body = {
        "name": title,
        "type": "docx",
    }

    print(f"创建文档: {title}")
    print(f"请求URL: {url}")
    print(f"请求Body: {body}")

    resp = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json=body,
        timeout=30,
    )

    print(f"\n响应状态: {resp.status_code}")
    print(f"响应内容: {resp.text}")

    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 0:
            file_info = data["data"]["file"]
            print(f"\n✅ 文档创建成功!")
            print(f"   名称: {file_info['name']}")
            print(f"   Token: {file_info['token']}")
            print(f"   URL: {file_info['url']}")
            return file_info
        else:
            print(f"\n❌ API返回错误: {data.get('msg')}")
            return None
    else:
        print(f"\n❌ HTTP请求失败: {resp.status_code}")
        return None


def main():
    print("=" * 50)
    print("飞书文档API测试")
    print("=" * 50)

    # 从环境变量获取凭证
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        print("\n❌ 错误: 未设置飞书应用凭证")
        print("\n请设置以下环境变量:")
        print("  FEISHU_APP_ID")
        print("  FEISHU_APP_SECRET")
        print("\n或者在项目根目录创建 .env 文件:")
        print("  FEISHU_APP_ID=your_app_id")
        print("  FEISHU_APP_SECRET=your_app_secret")
        sys.exit(1)

    print(f"\nApp ID: {app_id[:10]}...")

    # 获取token
    print("\n1. 获取访问令牌...")
    try:
        token = get_tenant_access_token(app_id, app_secret)
        print(f"✅ Token获取成功: {token[:20]}...")
    except Exception as e:
        print(f"❌ 获取Token失败: {e}")
        sys.exit(1)

    # 创建文档
    print("\n2. 创建测试文档...")
    doc_info = test_create_document(token)

    if doc_info:
        print("\n" + "=" * 50)
        print("测试完成! 文档API工作正常。")
        print("=" * 50)
        print(f"\n文档链接: {doc_info['url']}")
    else:
        print("\n" + "=" * 50)
        print("测试失败，请检查权限配置。")
        print("=" * 50)
        print("\n需要的权限:")
        print("  - drive:drive (访问云文档)")
        print("  - drive:file:write (创建文件)")
        sys.exit(1)


if __name__ == "__main__":
    main()
