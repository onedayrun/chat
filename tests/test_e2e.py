import os

import pytest
import aiohttp
from aiohttp import WSMsgType
import json


def _get_base_url() -> str:
    base_url = os.environ.get("E2E_BASE_URL")
    if not base_url:
        pytest.skip("E2E_BASE_URL is required for e2e tests")

    return base_url.rstrip("/")


async def _ws_receive_json_text(ws: aiohttp.ClientWebSocketResponse, *, timeout: int):
    while True:
        msg = await ws.receive(timeout=timeout)

        if msg.type == WSMsgType.TEXT:
            return json.loads(msg.data)

        if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
            raise AssertionError(f"WebSocket closed (type={msg.type}, data={msg.data})")

        if msg.type == WSMsgType.ERROR:
            raise AssertionError(f"WebSocket error: {ws.exception()}")

        if msg.type in (WSMsgType.PING, WSMsgType.PONG):
            continue


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_http_and_websocket_flow():
    base_url = _get_base_url()

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/health") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data.get("status") == "healthy"

        async with session.post(
            f"{base_url}/projects",
            json={
                "client_name": "E2E",
                "tier": "8h",
                "initial_message": "Hello",
            },
        ) as resp:
            assert resp.status == 200
            project = await resp.json()
            project_id = project["project_id"]

        async with session.get(f"{base_url}/chat/{project_id}") as resp:
            assert resp.status == 200
            html = await resp.text()
            assert "<!DOCTYPE html>" in html
            assert f"OneDay.run Chat - {project_id}" in html
            assert f"const projectId = \"{project_id}\"" in html

        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/{project_id}"

        async with session.ws_connect(ws_url, heartbeat=30) as ws:
            first = await _ws_receive_json_text(ws, timeout=10)
            assert first.get("type") == "system"

            await ws.send_json({"type": "message", "content": "Say hello"})

            saw_start = False
            saw_end = False
            saw_any_chunk = False

            for _ in range(200):
                msg = await _ws_receive_json_text(ws, timeout=60)
                if msg.get("type") == "response_start":
                    saw_start = True
                elif msg.get("type") == "response_chunk":
                    saw_any_chunk = True
                elif msg.get("type") == "response_end":
                    saw_end = True
                    break
                elif msg.get("type") == "error":
                    raise AssertionError(f"Server error: {msg.get('content')}")

            assert saw_start is True
            assert saw_end is True
            assert saw_any_chunk is True
