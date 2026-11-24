"""The server hands out the game (index.html, game.js, style.css) and nothing else."""
import asyncio
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ["DATABASE_URL"] = ""
import app as server  # noqa: E402

GAME_DIR = os.path.dirname(ROOT)


def get(path):
    async def go():
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
                 "scheme": "https", "path": path, "raw_path": path.encode(), "query_string": b"",
                 "root_path": "", "headers": [], "client": ("10.0.0.1", 5000), "server": ("t", 443)}
        out = {"status": None, "headers": {}, "body": b""}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(m):
            if m["type"] == "http.response.start":
                out["status"] = m["status"]
                out["headers"] = {k.decode().lower(): v.decode() for k, v in m.get("headers", [])}
            elif m["type"] == "http.response.body":
                out["body"] += m.get("body", b"")
        await server.app(scope, receive, send)
        return out
    return asyncio.run(go())


def test_game_files_are_served():
    for path, kind in (("/", "text/html"), ("/index.html", "text/html"),
                       ("/game.js", "text/javascript"), ("/style.css", "text/css")):
        r = get(path)
        assert r["status"] == 200 and r["headers"]["content-type"].startswith(kind), path
        assert r["headers"]["x-content-type-options"] == "nosniff"
    assert get("/game.js")["body"] == open(os.path.join(GAME_DIR, "game.js"), "rb").read()


def test_nothing_else_is_served():
    for path in ("/.env", "/hive-breach-server/.env", "/app.py", "/hive-breach-server/app.py",
                 "/store.py", "/.git/config", "/.git/HEAD", "/README.md", "/players.db",
                 "/hive-breach-server/players.db", "/assets/ui/logo.png", "/.gitignore",
                 "/../.env", "/%2e%2e/.env", "/index.html/../.env", "/requirements.txt"):
        r = get(path)
        assert r["status"] in (404, 405), (path, r["status"])
        assert b"DATABASE_URL" not in r["body"] and b"import" not in r["body"], path


def test_health_still_works():
    r = get("/api/health")
    assert r["status"] == 200 and b'"ok"' in r["body"]
