# -*- coding: utf-8 -*-
# @file test_opencode_server_client.py
# @brief E2E test for sail.opencode_server + sail.opencode client.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import asyncio
import pytest
import pytest_asyncio

from aiohttp import web

from sail.opencode import (
    OpencodeAsyncClient,
    EventType,
    ParsedEvent,
    parse_event,
    RunResult,
    SessionRunner,
    run_prompt,
    run_task,
    TaskResult,
    TaskRunConfig,
)
from sail.opencode_server.app import OpencodeServerApp
from sail.opencode_server.llm_backend import MockBackend


@pytest_asyncio.fixture
async def server_client():
    """Yield a running dummy server and an async client connected to it."""
    backend = MockBackend(
        response_text=(
            "Mock LLM says hello! "
            "This response is streamed through the opencode-compatible dummy server."
        )
    )
    app = OpencodeServerApp(backend=backend).get_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()

    port = site._server.sockets[0].getsockname()[1]  # type: ignore[attr-defined]
    client = OpencodeAsyncClient(host="127.0.0.1", port=port, name="test")

    try:
        yield client
    finally:
        await client.close()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_health_check(server_client: OpencodeAsyncClient) -> None:
    ok = await server_client.health_check()
    assert ok is True


@pytest.mark.asyncio
async def test_session_crud(server_client: OpencodeAsyncClient) -> None:
    sess = await server_client.create_session(title="E2E Test")
    assert sess.id
    assert sess.title == "E2E Test"

    fetched = await server_client.get_session(sess.id)
    assert fetched.id == sess.id

    sessions = await server_client.list_sessions()
    assert any(s.id == sess.id for s in sessions)

    ok = await server_client.delete_session(sess.id)
    assert ok is True


@pytest.mark.asyncio
async def test_prompt_async_and_sse_stream(server_client: OpencodeAsyncClient) -> None:
    """Send prompt_async and consume SSE events until session.idle."""
    sess = await server_client.create_session(title="Stream Test")
    prompt = "Say something nice"

    ok = await server_client.send_prompt_async(sess.id, prompt)
    assert ok is True

    collected_text = ""
    terminal = False
    async for raw in server_client.stream_events_robust(sess.id, timeout=30.0):
        parsed = parse_event(raw, sess.id)
        if parsed.type == EventType.SKIP:
            continue
        if parsed.type in (EventType.TEXT, EventType.TEXT_DELTA):
            collected_text += parsed.delta or parsed.text or ""
        if parsed.type == EventType.SESSION_IDLE:
            terminal = True
            break
        if parsed.is_terminal():
            terminal = True
            break

    assert terminal, "Expected a terminal event (session_idle or step-finish)"
    assert "Mock LLM says hello!" in collected_text


@pytest.mark.asyncio
async def test_send_message_blocking(server_client: OpencodeAsyncClient) -> None:
    """Use the blocking /session/{id}/message endpoint."""
    sess = await server_client.create_session(title="Blocking Test")
    msg = await server_client.send_message(sess.id, "Hello blocking")
    assert msg.role == "assistant"
    assert "Mock LLM says hello!" in msg.text_content


@pytest.mark.asyncio
async def test_session_runner(server_client: OpencodeAsyncClient) -> None:
    """Use the legacy SessionRunner high-level API."""
    port = server_client.port
    sess = await server_client.create_session(title="Runner Test")
    runner = SessionRunner(port=port, verbose=False)
    try:
        result: RunResult = await runner.run(
            prompt="Test prompt", session_id=sess.id, timeout=30.0
        )
    finally:
        await runner.close()

    assert result.success is True
    assert "Mock LLM says hello!" in result.full_text


@pytest.mark.asyncio
async def test_run_prompt_shortcut(server_client: OpencodeAsyncClient) -> None:
    """Use the legacy run_prompt shortcut."""
    port = server_client.port
    sess = await server_client.create_session(title="Shortcut Test")
    result: RunResult = await run_prompt(
        port=port,
        session_id=sess.id,
        prompt="Shortcut test",
        timeout=30.0,
        verbose=False,
    )
    assert result.success is True
    assert "Mock LLM says hello!" in result.full_text


@pytest.mark.asyncio
async def test_run_task_di(server_client: OpencodeAsyncClient) -> None:
    """Use the DI-based run_task with the dummy server."""
    port = server_client.port
    result: TaskResult = await run_task(
        prompt="DI test",
        port=port,
        host="127.0.0.1",
        config=TaskRunConfig(
            host="127.0.0.1",
            port=port,
            sse_timeout=30.0,
            max_reconnects=2,
        ),
        label="e2e_di",
    )
    assert result.success is True
    assert "Mock LLM says hello!" in result.text
    assert result.finish_reason in ("session_idle", "stream_ended", "step-finish", "stop")
