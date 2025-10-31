import os, importlib, pytest, httpx

pytestmark = pytest.mark.asyncio

def _base_env():
    os.environ["QUARANTINE_ENABLED"] = "false"
    os.environ["QUARANTINE_EXCLUDE_PATHS"] = "/_debug/whoami"
    os.environ["IP_SALT"] = "test_salt"

@pytest.mark.asyncio
async def test_xff_respected_when_remote_trusted():
    _base_env()
    os.environ["TRUSTED_PROXY_CIDRS"] = "127.0.0.1/32"
    import app.main as main
    importlib.reload(main)
    app = main.app
    headers = {"X-Forwarded-For": "198.51.100.23"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/_debug/whoami", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["ip"] == "198.51.100.23"
        assert len(body["hash"]) >= 16

@pytest.mark.asyncio
async def test_xff_ignored_when_remote_untrusted():
    _base_env()
    os.environ["TRUSTED_PROXY_CIDRS"] = ""  # boş: untrusted
    import app.main as main
    importlib.reload(main)
    app = main.app
    headers = {"X-Forwarded-For": "203.0.113.9"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/_debug/whoami", headers=headers)
        assert r.status_code == 200
        body = r.json()
        # ASGITransport tipik olarak 127.0.0.1
        assert body["ip"] in ("127.0.0.1", "::1")
