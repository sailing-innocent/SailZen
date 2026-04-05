#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file doc_demo_bot.py
# @brief Feishu Doc Demo Bot - 文档API验证Demo
# @author sailing-innocent
# @date 2026-04-05
# @version 1.0
# ---------------------------------
"""Feishu Document Demo Bot

功能：
1. 收到"置顶"消息时，创建一个飞书文档并发送链接
2. 在文档中被@时，在对话中回复

Usage:
    uv run bot/doc_demo_bot.py -c bot/doc_demo_bot.yaml
    uv run bot/doc_demo_bot.py --init
"""

import argparse
import json
import os
import re
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


# 加载环境变量
def _load_dotenv():
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


_load_dotenv()

# Feishu SDK
try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
        ReplyMessageRequest,
        ReplyMessageRequestBody,
    )
    from lark_oapi.api.drive.v1 import (
        CreateFileRequest,
        CreateFileRequestBody,
        CreateFileResp,
        GetDriveFileRequest,
        GetDriveFileResp,
    )

    HAS_LARK = True
except ImportError:
    HAS_LARK = False
    print("Error: lark-oapi not installed")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Error: httpx not installed")
    sys.exit(1)

import yaml


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class BotConfig:
    """Bot configuration."""

    def __init__(self):
        self.app_id = ""
        self.app_secret = ""
        self.admin_chat_id = None  # 管理员chat_id，用于接收通知
        self.folder_token = None  # 创建文档的目标文件夹token


# ---------------------------------------------------------------------------
# Document API Client
# ---------------------------------------------------------------------------


class FeishuDocClient:
    """飞书文档API客户端."""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    def _get_tenant_access_token(self) -> str:
        """获取tenant_access_token."""
        if (
            self._access_token
            and self._token_expires
            and datetime.now() < self._token_expires
        ):
            return self._access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = httpx.post(
            url, json={"app_id": self.app_id, "app_secret": self.app_secret}, timeout=30
        )

        if resp.status_code != 200:
            raise Exception(f"Failed to get token: {resp.text}")

        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"Token error: {data.get('msg')}")

        self._access_token = data["tenant_access_token"]
        # token有效期通常2小时，提前5分钟过期
        expires_in = data.get("expire", 7200) - 300
        self._token_expires = datetime.now() + timedelta(seconds=expires_in)

        return self._access_token

    def create_document(
        self, title: str, folder_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建飞书文档.

        Args:
            title: 文档标题
            folder_token: 目标文件夹token，None则创建到"我的空间"

        Returns:
            {"token": "...", "url": "...", "name": "..."}
        """
        token = self._get_tenant_access_token()

        url = "https://open.feishu.cn/open-apis/drive/v1/files"

        body = {
            "name": title,
            "type": "docx",  # 创建新版文档
        }

        if folder_token:
            body["folder_token"] = folder_token

        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=body,
            timeout=30,
        )

        if resp.status_code != 200:
            raise Exception(f"Create doc failed: {resp.text}")

        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"Create doc error: {data.get('msg')}")

        file_info = data["data"]["file"]
        return {
            "token": file_info["token"],
            "url": file_info["url"],
            "name": file_info["name"],
            "type": file_info["type"],
        }

    def get_file_info(self, file_token: str) -> Dict[str, Any]:
        """获取文件信息."""
        token = self._get_tenant_access_token()

        url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}"

        resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)

        if resp.status_code != 200:
            raise Exception(f"Get file failed: {resp.text}")

        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"Get file error: {data.get('msg')}")

        return data["data"]


# ---------------------------------------------------------------------------
# Demo Bot
# ---------------------------------------------------------------------------


class DocDemoBot:
    """文档Demo Bot."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.lark_client: Optional[lark.Client] = None
        self.doc_client: Optional[FeishuDocClient] = None

    def run(self):
        """启动Bot."""
        print("=" * 50)
        print("🤖 Feishu Doc Demo Bot")
        print("=" * 50)

        if not self.config.app_id or not self.config.app_secret:
            print("❌ 错误: 未配置飞书应用凭证")
            print("   请编辑配置文件设置 app_id 和 app_secret")
            return

        print(f"✅ App ID: {self.config.app_id[:10]}...")
        if self.config.folder_token:
            print(f"📁 目标文件夹: {self.config.folder_token}")
        else:
            print("📁 目标位置: 我的空间")

        # 初始化客户端
        self.lark_client = (
            lark.Client.builder()
            .app_id(self.config.app_id)
            .app_secret(self.config.app_secret)
            .build()
        )

        self.doc_client = FeishuDocClient(self.config.app_id, self.config.app_secret)

        # 测试文档API
        print("\n🧪 测试文档API连接...")
        try:
            test_doc = self.doc_client.create_document(
                f"API测试文档_{datetime.now().strftime('%m%d_%H%M%S')}",
                self.config.folder_token,
            )
            print(f"✅ 文档API测试成功")
            print(f"   文档: {test_doc['name']}")
            print(f"   URL: {test_doc['url']}")
        except Exception as e:
            print(f"⚠️  文档API测试失败: {e}")
            print("   继续启动Bot，但创建文档功能可能不可用")

        # 设置事件处理器
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_message)
            .register_p2_drive_file_comment_created_v1(self._handle_doc_comment)
            .build()
        )

        ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        print("\n📡 连接到飞书...")
        print("💡 可用指令：")
        print("   • 发送'置顶' - 创建测试文档")
        print("   • 在文档中@机器人 - 测试文档评论回复")
        print("\n(Ctrl+C 停止)\n")

        try:
            ws_client.start()
        except KeyboardInterrupt:
            print("\n👋 已停止")
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback

            traceback.print_exc()

    def _handle_message(self, data) -> None:
        """处理消息事件."""
        try:
            if not data or not data.event or not data.event.message:
                return

            message = data.event.message
            if message.message_type != "text":
                return

            # 解析消息内容
            try:
                content = json.loads(message.content or "{}")
            except json.JSONDecodeError:
                return

            text = content.get("text", "").strip()
            chat_id = message.chat_id
            message_id = message.message_id

            print(f"\n📨 收到消息: {text[:50]}")

            # 检查是否是"置顶"消息
            if "置顶" in text or "pin" in text.lower():
                self._handle_pin_message(chat_id, message_id, text)
            else:
                # 普通消息，回复帮助信息
                self._send_text_reply(
                    chat_id, "🤖 Doc Demo Bot\n\n发送'置顶'来创建测试文档。"
                )

        except Exception as e:
            print(f"❌ 处理消息错误: {e}")

    def _handle_pin_message(self, chat_id: str, message_id: str, text: str):
        """处理置顶消息 - 创建文档."""
        print("📌 处理置顶消息，创建文档...")

        try:
            # 创建文档
            title = f"Demo文档_{datetime.now().strftime('%m月%d日_%H:%M')}"
            doc_info = self.doc_client.create_document(title, self.config.folder_token)

            print(f"✅ 文档创建成功: {doc_info['name']}")
            print(f"   URL: {doc_info['url']}")

            # 发送回复，包含文档链接
            reply_text = (
                f"✅ **文档已创建**\n\n"
                f"📄 **{doc_info['name']}**\n"
                f"🔗 [点击打开文档]({doc_info['url']})\n\n"
                f"💡 小提示：\n"
                f"在文档中@机器人，可以在对话中收到回复。"
            )

            self._send_text_reply(chat_id, reply_text)

        except Exception as e:
            print(f"❌ 创建文档失败: {e}")
            self._send_text_reply(chat_id, f"❌ 创建文档失败\n\n错误: {str(e)[:200]}")

    def _handle_doc_comment(self, data) -> None:
        """处理文档评论事件."""
        try:
            print(f"\n📝 收到文档评论事件")
            print(f"   事件数据: {data}")

            # 解析评论事件
            event_data = data.event if hasattr(data, "event") else data

            # 获取评论内容
            comment = event_data.comment if hasattr(event_data, "comment") else {}
            content = comment.content if hasattr(comment, "content") else ""

            # 检查是否@了机器人
            # 注意：实际事件中mentions的结构可能不同，这里只是一个示例
            mentions = comment.mentions if hasattr(comment, "mentions") else []

            print(f"   评论内容: {content[:100]}")
            print(f"   提及数: {len(mentions)}")

            # 获取文档和用户信息
            file_token = (
                event_data.file.token
                if hasattr(event_data, "file") and hasattr(event_data.file, "token")
                else ""
            )
            user_id = event_data.user_id if hasattr(event_data, "user_id") else ""

            # 如果@了机器人，在对话中回复
            if mentions:
                # 查找用户的chat_id（这里简化处理，实际可能需要从其他地方获取）
                # 暂时发送给管理员
                if self.config.admin_chat_id:
                    reply_text = (
                        f"📣 **文档中被@**\n\n"
                        f"👤 用户在文档中提到了你\n"
                        f"💬 评论: {content[:200]}\n\n"
                        f"📄 文档Token: `{file_token}`"
                    )

                    self._send_text_reply(self.config.admin_chat_id, reply_text)
                    print(f"   已发送回复到 chat_id")

        except Exception as e:
            print(f"❌ 处理文档评论错误: {e}")
            import traceback

            traceback.print_exc()

    def _send_text_reply(self, chat_id: str, text: str) -> None:
        """发送文本消息."""
        if not self.lark_client:
            print(f"[无客户端] 将发送: {text[:100]}")
            return

        try:
            content = json.dumps({"text": text}, ensure_ascii=False)
            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                )
                .build()
            )

            resp = self.lark_client.im.v1.message.create(request)
            if not resp.success():
                print(f"❌ 发送失败: {resp.msg}")
            else:
                print(f"✅ 消息已发送")

        except Exception as e:
            print(f"❌ 发送消息错误: {e}")


# ---------------------------------------------------------------------------
# Config Utils
# ---------------------------------------------------------------------------


def get_default_config_path() -> str:
    """获取默认配置文件路径."""
    if sys.platform == "win32":
        return str(Path(__file__).parent / "doc_demo_bot.yaml")
    return str(Path.home() / ".config" / "doc-demo-bot" / "config.yaml")


def load_config(config_path: str) -> BotConfig:
    """加载配置文件."""
    config = BotConfig()
    p = Path(config_path)

    if not p.exists():
        return config

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        config.app_id = data.get("app_id", "")
        config.app_secret = data.get("app_secret", "")
        config.admin_chat_id = data.get("admin_chat_id")
        config.folder_token = data.get("folder_token")

    except Exception as e:
        print(f"⚠️  加载配置失败: {e}")

    return config


def create_default_config(config_path: str):
    """创建默认配置文件."""
    p = Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    content = """\
# Feishu Doc Demo Bot 配置文件

# 飞书应用凭证 (必填)
# 从 https://open.feishu.cn/app 获取
app_id: ""
app_secret: ""

# 管理员chat_id (可选)
# 用于接收文档@通知
# 可以先跟机器人单聊，然后查看消息的chat_id
admin_chat_id: ""

# 目标文件夹Token (可选)
# 如果不设置，文档将创建到"我的空间"
# 可以通过飞书API获取文件夹token
folder_token: ""

# 需要的权限：
# - drive:drive (访问云文档)
# - im:message (发送消息)
# - drive:file:read (读取文件)
# - drive:file:write (创建文件)
"""

    with open(p, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ 已创建配置文件: {config_path}")
    print("请编辑配置文件，添加飞书应用凭证")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main():
    """主入口."""
    parser = argparse.ArgumentParser(description="Feishu Doc Demo Bot")
    parser.add_argument(
        "--config", "-c", default=get_default_config_path(), help="配置文件路径"
    )
    parser.add_argument("--init", action="store_true", help="创建默认配置文件并退出")

    args = parser.parse_args()

    if args.init:
        create_default_config(args.config)
        return

    if not Path(args.config).exists():
        print(f"❌ 配置文件不存在: {args.config}")
        create_default_config(args.config)
        print(f"\n请编辑配置文件: {args.config}")
        return

    # 加载配置并启动
    config = load_config(args.config)

    # 从环境变量补充
    config.app_id = config.app_id or os.getenv("FEISHU_APP_ID", "")
    config.app_secret = config.app_secret or os.getenv("FEISHU_APP_SECRET", "")
    config.admin_chat_id = config.admin_chat_id or os.getenv("FEISHU_ADMIN_CHAT_ID")
    config.folder_token = config.folder_token or os.getenv("FEISHU_FOLDER_TOKEN")

    bot = DocDemoBot(config)
    bot.run()


if __name__ == "__main__":
    main()
