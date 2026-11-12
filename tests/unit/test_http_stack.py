"""Full-stack HTTP tests: the real ASGI app against mcp-app's test issuer.

An administrator grants a channel through the MCP layer and the user sends
through it; a non-administrator is refused the admin tools at call time.
"""

import json

import httpx
import pytest

from alerts import app
from mcp_app.testing.fixtures import OPERATOR, issuer, mcp_running, oauth_env  # noqa: F401

from tests.unit.sdk.conftest import SENT  # registers the capture:// plugin

USER = "user@example.com"
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def client(oauth_env, monkeypatch):
    monkeypatch.setenv("ALERTS_CHANNELS", "phone = capture://phone/\nwork = capture://work/\n")
    SENT.clear()
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _rpc(method, params=None, id=1):
    body = {"jsonrpc": "2.0", "method": method, "id": id}
    if params is not None:
        body["params"] = params
    return body


def _result(resp):
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "error" not in data, data
    return data["result"]


def _tool_result(resp) -> dict:
    result = _result(resp)
    return json.loads(result["content"][0]["text"])


async def _call(client, headers, name, args):
    return await client.post("/", json=_rpc("tools/call", {"name": name, "arguments": args}),
                             headers={**headers, **MCP_HEADERS})


async def test_admin_grants_then_user_sends(client, oauth_env):
    admin = oauth_env.headers(OPERATOR)
    await client.post("/admin/users", json={"email": USER}, headers=admin)
    user = oauth_env.headers(USER)
    async with mcp_running(app, client):
        before = _tool_result(await _call(client, user, "list_channels", {}))
        assert before == {"channels": [], "default": None}

        granted = _tool_result(await _call(client, admin, "grant_channel", {"email": USER, "channel": "phone"}))
        assert granted == {"email": USER, "channels": ["phone"], "default": "phone"}

        out = _tool_result(await _call(client, user, "notify",
                                       {"message": "Done.", "link": "https://example.com/c/1"}))
        assert out["sent"] is True and out["channel"] == "phone"
        assert SENT[-1]["host"] == "phone" and "https://example.com/c/1" in SENT[-1]["body"]


async def test_non_admin_cannot_grant(client, oauth_env):
    admin = oauth_env.headers(OPERATOR)
    await client.post("/admin/users", json={"email": USER}, headers=admin)
    user = oauth_env.headers(USER)
    async with mcp_running(app, client):
        out = _tool_result(await _call(client, user, "grant_channel", {"email": USER, "channel": "phone"}))
        assert "Administrators only" in out["error"]
        refused = _tool_result(await _call(client, user, "notify", {"message": "x"}))
        assert "grant_channel" in refused["error"]
        assert SENT == []


async def test_tools_are_listed(client, oauth_env):
    admin = oauth_env.headers(OPERATOR)
    async with mcp_running(app, client):
        result = _result(await client.post("/", json=_rpc("tools/list"), headers={**admin, **MCP_HEADERS}))
    names = {t["name"] for t in result["tools"]}
    assert {"notify", "list_channels", "list_channel_types", "grant_channel", "revoke_channel"} <= names
