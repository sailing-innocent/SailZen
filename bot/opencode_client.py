# -*- coding: utf-8 -*-
# @file opencode_client.py
# @brief OpenCode Web API 客户端
# @author sailing-innocent
# @date 2026-03-25
# @version 1.1
# ---------------------------------
"""HTTP client for the OpenCode web/serve API.

OpenCode exposes a local Hono-based server with these key endpoints:
  GET  /global/health              - health check
  POST /session                    - create new session
  GET  /session/:id                - get session details
  POST /session/:id/message        - send task (JSON response)
"""

import json
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    raise ImportError("httpx not installed. Install: pip install httpx")


class OpenCodeWebClient:
    """HTTP client for the OpenCode web/serve API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4096, timeout: int = 120):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._base_url = f"http://{host}:{port}"

    @property
    def base_url(self) -> str:
        return self._base_url

    def is_healthy(self) -> bool:
        """Check if opencode server is up."""
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self._base_url}/global/health")
                return resp.status_code == 200
        except Exception:
            return False

    def create_session(self, title: Optional[str] = None) -> Optional[str]:
        """Create a new OpenCode session and return its ID.

        POST /session
        Body: { "title": "..." }
        Returns: Session object with "id" field
        """
        body: Dict[str, Any] = {}
        if title:
            body["title"] = title

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{self._base_url}/session", json=body)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return data.get("id")
                print(
                    f"[OpenCode] create_session failed: {resp.status_code} {resp.text[:200]}"
                )
                return None
        except Exception as exc:
            print(f"[OpenCode] create_session error: {exc}")
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions on this server."""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"{self._base_url}/session")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as exc:
            print(f"[OpenCode] list_sessions error: {exc}")
        return []

    def send_message(
        self,
        session_id: str,
        text: str,
        collect_timeout: int = 300,
    ) -> str:
        """Send a task message to a session and return the assistant reply.

        POST /session/:id/message
        Body: { parts: [{ type: "text", text: "..." }] }
        Response: { info: Message, parts: Part[] }

        This call blocks until the model finishes. For long tasks set a larger
        collect_timeout (default 300s).
        """
        url = f"{self._base_url}/session/{session_id}/message"
        body = {"parts": [{"type": "text", "text": text}]}

        try:
            with httpx.Client(timeout=collect_timeout) as client:
                resp = client.post(url, json=body)
                if resp.status_code not in (200, 201):
                    return f"OpenCode API error: HTTP {resp.status_code}: {resp.text[:300]}"

                # Parse JSON response
                data = resp.json()
                parts = data.get("parts", [])
                text_parts = [
                    p.get("text", "")
                    for p in parts
                    if isinstance(p, dict) and p.get("type") == "text" and p.get("text")
                ]
                reply = "".join(text_parts).strip()
                return reply or "(OpenCode returned an empty response)"

        except httpx.TimeoutException:
            return f"OpenCode timed out after {collect_timeout}s. The task may still be running."
        except Exception as exc:
            return f"OpenCode communication error: {exc}"
