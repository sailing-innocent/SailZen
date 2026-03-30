# -*- coding: utf-8 -*-
# @file opencode_client.py
# @brief OpenCode Web API Client
# @author sailing-innocent
# @date 2026-03-29
# @version 1.2
# ---------------------------------
"""HTTP client for the OpenCode web/serve API.

OpenCode exposes a local Hono-based server with these key endpoints:
  GET  /global/health              - health check
  POST /session                    - create new session
  GET  /session/:id                - get session details
  POST /session/:id/message        - send task (SSE stream response)

This client handles session lifecycle and message streaming.
"""

import json
import time
from typing import Any, Dict, List, Optional

import httpx


class OpenCodeWebClient:
    """HTTP client for the OpenCode web/serve API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4096, timeout: int = 120):
        """Initialize client.

        Args:
            host: OpenCode server host
            port: OpenCode server port
            timeout: Default timeout for requests
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self._base_url = f"http://{host}:{port}"

    @property
    def base_url(self) -> str:
        """Get base URL for OpenCode server."""
        return self._base_url

    def is_healthy(self) -> bool:
        """Check if opencode server is up.

        Returns:
            True if server responds to health check
        """
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

        Args:
            title: Optional session title

        Returns:
            Session ID or None on failure
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
        """List all sessions on this server.

        Returns:
            List of session dictionaries
        """
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

        Handles SSE stream edge cases: session.idle vs session.completed event names
        may vary across opencode versions. Uses robust event-name matching and
        timeout fallback.

        Args:
            session_id: OpenCode session ID
            text: Message text to send
            collect_timeout: Maximum time to wait for response

        Returns:
            Assistant reply text
        """
        url = f"{self._base_url}/session/{session_id}/message"
        body = {"parts": [{"type": "text", "text": text}]}

        start_time = time.time()
        collected_texts: List[str] = []
        session_completed = False

        try:
            with httpx.Client(timeout=collect_timeout) as client:
                resp = client.post(url, json=body)
                if resp.status_code not in (200, 201):
                    return f"OpenCode API error: HTTP {resp.status_code}: {resp.text[:300]}"

                # Check if response is SSE stream
                content_type = resp.headers.get("content-type", "")
                if (
                    "text/event-stream" in content_type
                    or resp.headers.get("transfer-encoding") == "chunked"
                ):
                    # Handle SSE stream
                    for line in resp.iter_lines():
                        if time.time() - start_time > collect_timeout:
                            break

                        line = line.strip()
                        if not line:
                            continue

                        # Parse SSE event
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix
                            try:
                                event_data = json.loads(data)
                            except json.JSONDecodeError:
                                continue

                            # Handle different event types with robust matching
                            event_type = event_data.get("type", "")

                            # Collect text from content events (various formats)
                            if event_type in ("content", "text", "chunk", "delta"):
                                content = (
                                    event_data.get("content", "")
                                    or event_data.get("text", "")
                                    or event_data.get("delta", "")
                                )
                                if content:
                                    collected_texts.append(content)

                            # Check for completion events (various names across versions)
                            elif event_type in (
                                "completed",
                                "done",
                                "finished",
                                "end",
                                "session.completed",
                            ):
                                session_completed = True
                                break

                            # Check for idle/stop events (alternative completion signals)
                            elif event_type in (
                                "idle",
                                "stopped",
                                "session.idle",
                                "halt",
                            ):
                                session_completed = True
                                break

                            # Check for error events
                            elif event_type in ("error", "failed"):
                                error_msg = event_data.get(
                                    "message", event_data.get("error", "Unknown error")
                                )
                                return f"OpenCode error: {error_msg}"

                    # Fallback: if we collected text but didn't get completion event,
                    # return what we have (with a note if incomplete)
                    reply = "".join(collected_texts).strip()
                    if reply and not session_completed:
                        return (
                            reply
                            + "\n\n[Response may be incomplete - timeout or stream interruption]"
                        )
                    return reply or "(OpenCode returned an empty response)"
                else:
                    # Handle regular JSON response
                    data = resp.json()
                    parts = data.get("parts", [])
                    text_parts = [
                        p.get("text", "")
                        for p in parts
                        if isinstance(p, dict)
                        and p.get("type") == "text"
                        and p.get("text")
                    ]
                    reply = "".join(text_parts).strip()
                    return reply or "(OpenCode returned an empty response)"

        except httpx.TimeoutException:
            # Return collected text even on timeout
            if collected_texts:
                reply = "".join(collected_texts).strip()
                return (
                    reply
                    + f"\n\n[Response truncated - timed out after {collect_timeout}s]"
                )
            return f"OpenCode timed out after {collect_timeout}s. The task may still be running."
        except Exception as exc:
            # Return collected text even on error
            if collected_texts:
                reply = "".join(collected_texts).strip()
                return reply + f"\n\n[Response may be incomplete - error: {exc}]"
            return f"OpenCode communication error: {exc}"
