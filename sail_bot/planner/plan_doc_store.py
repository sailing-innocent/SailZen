# -*- coding: utf-8 -*-
# @file plan_doc_store.py
# @brief Feishu document store abstraction for plan mode
# @author sailing-innocent
# @date 2026-06-16
# @version 1.0
# ---------------------------------
"""Plan document store backed by Feishu docs via lark-cli.

Provides async wrappers around `lark-cli docs +create/fetch/update`.  Falls
back to local markdown files when Feishu document operations are unavailable
or fail, ensuring the bot can still operate in limited environments.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from sail_bot.paths import DATA_DIR

logger = logging.getLogger(__name__)

_PLANS_DIR: Path = DATA_DIR / "plans"


def _ensure_plans_dir() -> None:
    _PLANS_DIR.mkdir(parents=True, exist_ok=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _escape_xml(text: str) -> str:
    """Escape text for XML content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _extract_doc_token(url_or_token: str) -> str:
    """Extract document token from URL or return as-is."""
    if not url_or_token:
        return ""
    # Match /docx/<token> or /wiki/<token> or /doc/<token>
    m = re.search(r"/(?:docx|wiki|doc)/([a-zA-Z0-9_\-]+)", url_or_token)
    if m:
        return m.group(1)
    return url_or_token.strip()


class PlanDocStore:
    """Store for plan documents backed by Feishu docs with local fallback."""

    def __init__(self, fallback_to_local: bool = True):
        self.fallback_to_local = fallback_to_local
        self._local_fallback_path: Optional[Path] = None

    async def create(
        self,
        title: str,
        initial_content: str,
        chat_id: str = "",
        folder_token: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Create a plan document.

        Returns:
            Tuple of (doc_token_or_path, doc_url_or_path)
        """
        try:
            token, url = await self._create_feishu_doc(title, initial_content, folder_token)
            logger.info("Created Feishu plan doc: %s", url)
            return token, url
        except Exception as exc:
            logger.warning("Feishu doc create failed (%s), using local fallback", exc)
            if self.fallback_to_local:
                return self._create_local_fallback(title, initial_content, chat_id)
            raise

    async def fetch(self, doc_token: str, scope: str = "simple") -> str:
        """Fetch document content as text/markdown."""
        if not doc_token:
            return ""

        # Local fallback path detection
        if _is_local_path(doc_token):
            return self._read_local_fallback(Path(doc_token))

        try:
            return await self._fetch_feishu_doc(doc_token, scope=scope)
        except Exception as exc:
            logger.warning("Feishu doc fetch failed (%s), trying local fallback", exc)
            if self.fallback_to_local and self._local_fallback_path:
                return self._read_local_fallback(self._local_fallback_path)
            raise

    async def update(
        self,
        doc_token: str,
        command: str,
        content: str = "",
        pattern: str = "",
        block_id: str = "",
    ) -> bool:
        """Update a document.  Commands mirror lark-cli docs +update."""
        if not doc_token:
            return False

        if _is_local_path(doc_token):
            return self._update_local_fallback(
                Path(doc_token), command, content, pattern
            )

        try:
            return await self._update_feishu_doc(
                doc_token, command, content, pattern, block_id
            )
        except Exception as exc:
            logger.warning("Feishu doc update failed (%s), trying local fallback", exc)
            if self.fallback_to_local and self._local_fallback_path:
                return self._update_local_fallback(
                    self._local_fallback_path, command, content, pattern
                )
            return False

    def url_for(self, doc_token: str) -> str:
        """Return a human-readable URL or path for the document."""
        if not doc_token:
            return ""
        if _is_local_path(doc_token):
            return doc_token
        # Assume docx token
        return f"https://www.feishu.cn/docx/{doc_token}"

    # ------------------------------------------------------------------
    # Feishu implementations
    # ------------------------------------------------------------------

    async def _create_feishu_doc(
        self,
        title: str,
        initial_content: str,
        folder_token: Optional[str] = None,
    ) -> Tuple[str, str]:
        xml_content = self._build_xml_content(title, initial_content)
        cmd = [
            "lark-cli",
            "docs",
            "+create",
            "--api-version",
            "v2",
            "--content",
            "-",
            "--doc-format",
            "xml",
        ]
        if folder_token:
            cmd += ["--parent-token", folder_token]

        stdout = await _run_lark_cli(cmd, stdin=xml_content)
        data = _parse_cli_json(stdout)
        doc = data.get("data", {}).get("document", {})
        token = doc.get("document_id", "")
        url = doc.get("url", "")
        if not token:
            raise RuntimeError(f"Failed to create Feishu doc: {stdout}")
        return token, url

    async def _fetch_feishu_doc(self, doc_token: str, scope: str = "") -> str:
        token = _extract_doc_token(doc_token)
        cmd = [
            "lark-cli",
            "docs",
            "+fetch",
            "--api-version",
            "v2",
            "--doc",
            token,
            "--doc-format",
            "markdown",
        ]
        valid_scopes = {"full", "outline", "range", "keyword", "section"}
        if scope in valid_scopes:
            cmd += ["--scope", scope]

        stdout = await _run_lark_cli(cmd)
        data = _parse_cli_json(stdout)
        doc = data.get("data", {}).get("document", {})
        return doc.get("content", "")

    async def _update_feishu_doc(
        self,
        doc_token: str,
        command: str,
        content: str,
        pattern: str,
        block_id: str,
    ) -> bool:
        token = _extract_doc_token(doc_token)
        cmd = [
            "lark-cli",
            "docs",
            "+update",
            "--api-version",
            "v2",
            "--doc",
            token,
            "--command",
            command,
            "--doc-format",
            "markdown",
        ]
        stdin = None
        if content:
            cmd += ["--content", "-"]
            stdin = content
        if pattern:
            cmd += ["--pattern", pattern]
        if block_id:
            cmd += ["--block-id", block_id]

        await _run_lark_cli(cmd, stdin=stdin)
        return True

    # ------------------------------------------------------------------
    # Local fallback implementations
    # ------------------------------------------------------------------

    def _create_local_fallback(
        self, title: str, initial_content: str, chat_id: str
    ) -> Tuple[str, str]:
        _ensure_plans_dir()
        suffix = f"_{chat_id}" if chat_id else ""
        filename = f"plan{suffix}_{_sha256(title)}.md"
        path = _PLANS_DIR / filename
        path.write_text(
            f"# {title}\n\n{initial_content}\n", encoding="utf-8"
        )
        self._local_fallback_path = path
        logger.info("Created local fallback plan doc: %s", path)
        return str(path), str(path)

    def _read_local_fallback(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _update_local_fallback(
        self,
        path: Path,
        command: str,
        content: str,
        pattern: str,
    ) -> bool:
        if not path.exists():
            return False
        text = path.read_text(encoding="utf-8")
        if command in ("overwrite",):
            text = content
        elif command in ("append",):
            text = text + "\n\n" + content
        elif command in ("str_replace",):
            if pattern not in text:
                return False
            text = text.replace(pattern, content, 1)
        else:
            # Fallback: append
            text = text + "\n\n" + content
        path.write_text(text, encoding="utf-8")
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_xml_content(self, title: str, initial_content: str) -> str:
        """Build XML content for creating a Feishu doc."""
        lines = [f"<title>{_escape_xml(title)}</title>"]
        lines.append("<h1>需求</h1>")
        for para in initial_content.split("\n"):
            para = para.strip()
            if not para:
                continue
            if para.startswith("#"):
                level = min(len(para) - len(para.lstrip("#")), 6)
                text = para.lstrip("#").strip()
                lines.append(f"<h{level}>{_escape_xml(text)}</h{level}>")
            else:
                lines.append(f"<p>{_escape_xml(para)}</p>")
        return "".join(lines)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _is_local_path(doc_token: str) -> bool:
    return doc_token.endswith(".md") or "/" in doc_token or "\\" in doc_token


async def _run_lark_cli(cmd: list, stdin: Optional[str] = None) -> str:
    """Run a lark-cli command and return stdout.

    Args:
        cmd: Command list.
        stdin: Optional text to send via stdin.  Used to avoid shell escaping
            issues with XML/Markdown content on Windows.
    """
    # Resolve full executable path for Windows compatibility (.cmd shims)
    executable = shutil.which(cmd[0])
    if executable:
        cmd[0] = executable
    logger.debug("Running lark-cli: %s", " ".join(cmd))

    stdin_bytes = stdin.encode("utf-8") if stdin is not None else None
    proc = await asyncio.create_subprocess_exec(
        cmd[0],
        *cmd[1:],
        stdin=asyncio.subprocess.PIPE if stdin_bytes else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=stdin_bytes)
    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"lark-cli failed ({proc.returncode}): {err or out}")
    return out


def _parse_cli_json(stdout: str) -> dict:
    """Parse JSON output from lark-cli, tolerating leading/trailing text."""
    stdout = stdout.strip()
    if not stdout:
        return {}
    # Find first JSON object
    start = stdout.find("{")
    if start == -1:
        return {}
    # Try parsing from start; if fails, try to find balanced brace
    try:
        return json.loads(stdout[start:])
    except json.JSONDecodeError:
        pass
    # Heuristic: find the last '}' that balances braces
    depth = 0
    end = -1
    for i, ch in enumerate(stdout[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return {}
    try:
        return json.loads(stdout[start : end + 1])
    except json.JSONDecodeError:
        return {}
