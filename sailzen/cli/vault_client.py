# -*- coding: utf-8 -*-
# @file vault_client.py
# @brief VaultClient CLI - 通过 HTTP API 读写 Sail Vault 中的笔记
# @author sailing-innocent
# @date 2026-05-06
# @version 1.0
# ---------------------------------

"""
VaultClient CLI 工具

通过 Vault API Server（packages/api_server standalone 模式）与本地 Vault 交互，支持：
1. 查询/搜索笔记 (query)
2. 获取单条笔记完整内容 (get)
3. 查找笔记（按文件名/vault 过滤）(find)
4. 写入/更新笔记 (write)
5. 删除笔记 (delete)
6. 获取服务器/vault 状态 (status)

Vault API Server 的地址默认为 http://localhost:3005，
WS_ROOT 路径需要与 server 启动时保持一致。

API 端点（基于 api_server standalone 路由结构）：
- GET  /api/note/query?ws=<root>&q=<query>    → 查询笔记
- GET  /api/note/get?ws=<root>&id=<id>        → 获取单条笔记
- POST /api/note/find                          → 按条件查找笔记
- POST /api/note/write                         → 写入/更新笔记
- POST /api/note/delete                        → 删除笔记
- GET  /api/note/info                          → 获取 engine 信息

工作流程：
  # 查询所有笔记
  python vault_client.py query --q "*"

  # 搜索包含关键字的笔记
  python vault_client.py query --q "python"

  # 获取单条笔记
  python vault_client.py get --id <note-id>

  # 按文件名查找
  python vault_client.py find --fname "daily.2026"

  # 写入新笔记（从 JSON 文件）
  python vault_client.py write --file note.json

  # 删除笔记
  python vault_client.py delete --id <note-id>
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Optional

import requests


# ============================================================================
# Constants
# ============================================================================

DEFAULT_VAULT_SERVER = "http://localhost:3005"
API_TIMEOUT = 30  # HTTP 请求超时（秒）


# ============================================================================
# VaultClient
# ============================================================================


class VaultClient:
    """通过 HTTP API 与 Vault API Server 交互的客户端"""

    def __init__(self, server_url: str, ws_root: str):
        """
        Args:
            server_url: Vault API Server 地址，如 http://localhost:3005
            ws_root: vault 根目录路径（与 server 启动时的 WS_ROOT 一致）
        """
        self.server_url = server_url.rstrip("/")
        self.ws_root = ws_root
        self.base_api = f"{self.server_url}/api"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """检查服务器是否在线"""
        try:
            resp = self.session.get(
                f"{self.base_api}/note/info", timeout=5
            )
            return resp.status_code < 500
        except requests.ConnectionError:
            return False

    def info(self) -> dict:
        """获取 engine 信息"""
        resp = self.session.get(
            f"{self.base_api}/note/info", timeout=API_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Note 查询 API
    # ------------------------------------------------------------------

    def query(self, q: str = "*") -> list[dict]:
        """
        查询笔记。

        Args:
            q: 查询字符串，"*" 返回所有笔记，或指定笔记 fname 前缀

        Returns:
            笔记元数据列表
        """
        resp = self.session.get(
            f"{self.base_api}/note/query",
            params={"ws": self.ws_root, "q": q},
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
        # 兼容两种响应格式
        if isinstance(result, list):
            return result
        return result.get("data", result.get("notes", []))

    def get(self, note_id: str) -> Optional[dict]:
        """
        获取单条笔记完整内容（包含 body）。

        Args:
            note_id: 笔记 ID

        Returns:
            笔记完整数据，或 None（未找到）
        """
        resp = self.session.get(
            f"{self.base_api}/note/get",
            params={"ws": self.ws_root, "id": note_id},
            timeout=API_TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        result = resp.json()
        return result.get("data", result)

    def get_meta(self, note_id: str) -> Optional[dict]:
        """
        获取单条笔记元数据（不含 body，更快）。

        Args:
            note_id: 笔记 ID

        Returns:
            笔记元数据，或 None（未找到）
        """
        resp = self.session.get(
            f"{self.base_api}/note/getMeta",
            params={"ws": self.ws_root, "id": note_id},
            timeout=API_TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        result = resp.json()
        return result.get("data", result)

    def find(
        self,
        fname: Optional[str] = None,
        vault: Optional[str] = None,
        exclude_stub: bool = True,
    ) -> list[dict]:
        """
        按条件查找笔记。

        Args:
            fname: 按文件名过滤（支持前缀匹配）
            vault: 按 vault 名过滤
            exclude_stub: 是否排除 stub 笔记（默认 True）

        Returns:
            笔记完整数据列表
        """
        payload: dict[str, Any] = {
            "ws": self.ws_root,
            "excludeStub": exclude_stub,
        }
        if fname is not None:
            payload["fname"] = fname
        if vault is not None:
            payload["vault"] = vault

        resp = self.session.post(
            f"{self.base_api}/note/find",
            json=payload,
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
        return result.get("data", result.get("notes", []))

    def find_meta(
        self,
        fname: Optional[str] = None,
        vault: Optional[str] = None,
        exclude_stub: bool = True,
    ) -> list[dict]:
        """查找笔记元数据（不含 body）"""
        payload: dict[str, Any] = {
            "ws": self.ws_root,
            "excludeStub": exclude_stub,
        }
        if fname is not None:
            payload["fname"] = fname
        if vault is not None:
            payload["vault"] = vault

        resp = self.session.post(
            f"{self.base_api}/note/findMeta",
            json=payload,
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
        return result.get("data", result.get("notes", []))

    # ------------------------------------------------------------------
    # Note 写入 API
    # ------------------------------------------------------------------

    def write(self, note: dict, opts: Optional[dict] = None) -> dict:
        """
        写入/更新笔记。

        note 字段说明（最小集合）：
          - id: str           笔记唯一 ID（新建时可用 nanoid 生成）
          - fname: str        文件名，如 "daily.2026-05-06"
          - title: str        标题
          - body: str         正文内容（Markdown）
          - vault: dict       所在 vault，如 {"fsPath": "/path/to/vault"}

        Args:
            note: 笔记数据字典
            opts: 写入选项，如 {"updateExisting": True}

        Returns:
            写入结果
        """
        payload: dict[str, Any] = {
            "ws": self.ws_root,
            "node": note,
        }
        if opts:
            payload["opts"] = opts

        resp = self.session.post(
            f"{self.base_api}/note/write",
            json=payload,
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def delete(self, note_id: str, opts: Optional[dict] = None) -> dict:
        """
        删除笔记。

        Args:
            note_id: 笔记 ID
            opts: 删除选项

        Returns:
            删除结果
        """
        payload: dict[str, Any] = {
            "ws": self.ws_root,
            "id": note_id,
        }
        if opts:
            payload["opts"] = opts

        resp = self.session.post(
            f"{self.base_api}/note/delete",
            json=payload,
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()


# ============================================================================
# CLI 命令处理函数
# ============================================================================


def _make_client(args) -> VaultClient:
    """从 args 构造 VaultClient，并校验服务器连通性"""
    ws_root = args.ws_root or os.environ.get("VAULT_WS_ROOT", "")
    if not ws_root:
        print(
            "❌ 必须指定 --ws-root 或设置环境变量 VAULT_WS_ROOT",
            file=sys.stderr,
        )
        sys.exit(1)
    client = VaultClient(server_url=args.server, ws_root=ws_root)
    if not client.ping():
        print(
            f"❌ 无法连接到 Vault API Server: {args.server}",
            file=sys.stderr,
        )
        print("   请先启动服务器:", file=sys.stderr)
        print(
            f"   WS_ROOT={ws_root} pnpm --filter @saili/api-server vault-server:dev",
            file=sys.stderr,
        )
        sys.exit(1)
    return client


def cmd_status(args):
    """检查服务器状态"""
    ws_root = args.ws_root or os.environ.get("VAULT_WS_ROOT", "")
    client = VaultClient(server_url=args.server, ws_root=ws_root or "")
    if client.ping():
        print(f"✅ Vault API Server 在线: {args.server}")
        try:
            info = client.info()
            print(f"   Engine 信息: {json.dumps(info, ensure_ascii=False, indent=2)}")
        except Exception:
            pass
    else:
        print(f"❌ Vault API Server 离线: {args.server}")
        sys.exit(1)


def cmd_query(args):
    """查询笔记"""
    client = _make_client(args)
    q = args.q or "*"
    print(f"🔍 查询: {q!r}  (vault: {client.ws_root})")
    notes = client.query(q)
    if not notes:
        print("  (无结果)")
        return
    print(f"  找到 {len(notes)} 条笔记:\n")
    for note in notes:
        nid = note.get("id", "")[:8]
        fname = note.get("fname", "")
        title = note.get("title", "")
        updated = note.get("updated", "")
        print(f"  [{nid}]  {fname:<40}  {title:<30}  updated={updated}")


def cmd_get(args):
    """获取单条笔记"""
    client = _make_client(args)
    note = client.get(args.id)
    if note is None:
        print(f"❌ 笔记不存在: {args.id}", file=sys.stderr)
        sys.exit(1)
    if args.body_only:
        print(note.get("body", ""))
    elif args.json:
        print(json.dumps(note, ensure_ascii=False, indent=2))
    else:
        print(f"ID    : {note.get('id', '')}")
        print(f"fname : {note.get('fname', '')}")
        print(f"title : {note.get('title', '')}")
        print(f"vault : {note.get('vault', {})}")
        print(f"updated: {note.get('updated', '')}")
        print(f"tags  : {note.get('tags', [])}")
        print("")
        print("--- body ---")
        print(note.get("body", ""))


def cmd_find(args):
    """按条件查找笔记"""
    client = _make_client(args)
    notes = client.find_meta(
        fname=args.fname,
        vault=args.vault,
        exclude_stub=not args.include_stub,
    )
    if not notes:
        print("  (无结果)")
        return
    print(f"  找到 {len(notes)} 条笔记:\n")
    for note in notes:
        nid = note.get("id", "")[:8]
        fname = note.get("fname", "")
        title = note.get("title", "")
        print(f"  [{nid}]  {fname:<40}  {title}")


def cmd_write(args):
    """写入笔记（从 JSON 文件或 stdin）"""
    client = _make_client(args)
    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ 文件不存在: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            note = json.load(f)
    else:
        print("从 stdin 读取笔记 JSON（输入后按 Ctrl+D 结束）:")
        raw = sys.stdin.read()
        note = json.loads(raw)

    result = client.write(note)
    print(f"✅ 写入成功")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        changed = result.get("data", {}).get("changed", [])
        print(f"   变更笔记数: {len(changed)}")


def cmd_delete(args):
    """删除笔记"""
    client = _make_client(args)
    # 确认
    if not args.yes:
        confirm = input(f"确认删除笔记 {args.id}? [y/N] ").strip().lower()
        if confirm != "y":
            print("已取消")
            return
    result = client.delete(args.id)
    print(f"✅ 删除成功: {args.id}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))


# ============================================================================
# Main Entry
# ============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="VaultClient - SailZen Vault 笔记读写 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查询所有笔记
  python vault_client.py query

  # 搜索包含 "python" 的笔记
  python vault_client.py query --q python

  # 获取单条笔记（含正文）
  python vault_client.py get --id <note-id>

  # 只输出正文 Markdown
  python vault_client.py get --id <note-id> --body-only

  # 按文件名前缀查找
  python vault_client.py find --fname "daily.2026"

  # 写入笔记（从 JSON 文件）
  python vault_client.py write --file note.json

  # 删除笔记
  python vault_client.py delete --id <note-id> --yes
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---- 公共参数 ----
    def add_common_args(p):
        p.add_argument(
            "--server",
            default=os.environ.get("VAULT_SERVER_URL", DEFAULT_VAULT_SERVER),
            help=f"Vault API Server 地址 (默认: {DEFAULT_VAULT_SERVER}, 环境变量: VAULT_SERVER_URL)",
        )
        p.add_argument(
            "--ws-root",
            default=os.environ.get("VAULT_WS_ROOT", ""),
            help="vault 根目录路径 (环境变量: VAULT_WS_ROOT)",
        )

    def add_json_flag(p):
        p.add_argument(
            "--json",
            action="store_true",
            help="以 JSON 格式输出",
        )

    # ---- status ----
    p_status = subparsers.add_parser("status", aliases=["s"], help="检查服务器状态")
    add_common_args(p_status)
    p_status.set_defaults(func=cmd_status)

    # ---- query ----
    p_query = subparsers.add_parser("query", aliases=["q"], help="查询笔记列表")
    add_common_args(p_query)
    p_query.add_argument(
        "--q",
        default="*",
        help="查询字符串，支持 fname 前缀（默认: * 返回所有）",
    )
    p_query.set_defaults(func=cmd_query)

    # ---- get ----
    p_get = subparsers.add_parser("get", aliases=["g"], help="获取单条笔记完整内容")
    add_common_args(p_get)
    add_json_flag(p_get)
    p_get.add_argument("--id", required=True, help="笔记 ID")
    p_get.add_argument(
        "--body-only",
        action="store_true",
        help="只输出正文 Markdown",
    )
    p_get.set_defaults(func=cmd_get)

    # ---- find ----
    p_find = subparsers.add_parser("find", aliases=["f"], help="按条件查找笔记")
    add_common_args(p_find)
    p_find.add_argument("--fname", default=None, help="按文件名前缀过滤")
    p_find.add_argument("--vault", default=None, help="按 vault 名过滤")
    p_find.add_argument(
        "--include-stub",
        action="store_true",
        help="包含 stub 笔记（默认排除）",
    )
    p_find.set_defaults(func=cmd_find)

    # ---- write ----
    p_write = subparsers.add_parser("write", aliases=["w"], help="写入/更新笔记")
    add_common_args(p_write)
    add_json_flag(p_write)
    p_write.add_argument(
        "--file", "-f",
        default=None,
        help="笔记 JSON 文件路径（不指定则从 stdin 读取）",
    )
    p_write.set_defaults(func=cmd_write)

    # ---- delete ----
    p_delete = subparsers.add_parser("delete", aliases=["d"], help="删除笔记")
    add_common_args(p_delete)
    add_json_flag(p_delete)
    p_delete.add_argument("--id", required=True, help="笔记 ID")
    p_delete.add_argument(
        "--yes", "-y",
        action="store_true",
        help="跳过确认直接删除",
    )
    p_delete.set_defaults(func=cmd_delete)

    # ----
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except requests.HTTPError as e:
        print(
            f"❌ API 请求失败: HTTP {e.response.status_code}",
            file=sys.stderr,
        )
        print(f"   {e.response.text[:300]}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(0)


if __name__ == "__main__":
    main()
