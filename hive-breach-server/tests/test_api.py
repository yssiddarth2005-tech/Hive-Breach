"""HTTP and WebSocket layer, driven through ASGI directly (no network needed)."""
import asyncio
import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = ""          # these tests always use a throwaway SQLite file, never .env
os.environ["MAX_PLAYERS"] = "50"
import app as server  # noqa: E402

ORIGIN = "https://yssiddarth2005-tech.github.io"


class FakeTime:
    def __init__(self):
        self.now = 5_000_000.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.now

    def sleep(self, s):
        self.now += s


@pytest.fixture(autouse=True)
def fake_time(monkeypatch):
    ft = FakeTime()
    monkeypatch.setattr(server, "time", ft)
    server.new_per_ip.hits.clear()
    server.new_global.hits.clear()
    server.http_per_player.hits.clear()
    server.hub.slots.clear()
    server.hub.ip_conns.clear()
    return ft


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


_ip = [0]


def fresh_ip():
    _ip[0] += 1
    return "34.120.%d.%d" % (_ip[0] // 250, _ip[0] % 250 + 1)


async def http(method, path, token=None, body=None, ip="34.200.1.7", raw=None):
    headers = [(b"origin", ORIGIN.encode()), (b"x-forwarded-for", ip.encode())]
    if token:
        headers.append((b"authorization", ("Bearer " + token).encode()))
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
    if data:
        headers += [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
             "scheme": "https", "path": path, "raw_path": path.encode(), "query_string": b"",
             "root_path": "", "headers": headers, "client": ("10.0.0.1", 5000), "server": ("t", 443)}
    done = False

    async def receive():
        nonlocal done
        if not done:
            done = True
            return {"type": "http.request", "body": data, "more_body": False}
        await asyncio.sleep(3600)

    out = {"status": None, "body": b""}

    async def send(m):
        if m["type"] == "http.response.start":
            out["status"] = m["status"]
        elif m["type"] == "http.response.body":
            out["body"] += m.get("body", b"")

    await server.app(scope, receive, send)
    return out["status"], (json.loads(out["body"]) if out["body"] else None)


class WS:
    def __init__(self, ip="34.200.1.7", origin=ORIGIN):
        headers = [(b"x-forwarded-for", ip.encode())]
        if origin:
            headers.append((b"origin", origin.encode()))
        scope = {"type": "websocket", "asgi": {"version": "3.0"}, "scheme": "wss", "path": "/ws",
                 "raw_path": b"/ws", "query_string": b"", "root_path": "", "headers": headers,
                 "client": ("10.0.0.1", 5000), "server": ("t", 443), "subprotocols": []}
        self.inq, self.outq = asyncio.Queue(), asyncio.Queue()
        self.task = asyncio.ensure_future(server.app(scope, self.inq.get, self.outq.put))
        self.inq.put_nowait({"type": "websocket.connect"})

    async def opened(self):
        m = await asyncio.wait_for(self.outq.get(), 1)
        return m["type"] == "websocket.accept"

    def send(self, obj):
        self.inq.put_nowait({"type": "websocket.receive", "text": obj if isinstance(obj, str) else json.dumps(obj)})

    async def settle(self):
        """Let the server read everything queued before the fake clock moves on."""
        for _ in range(20):
            await asyncio.sleep(0)

    async def recv(self):
        m = await asyncio.wait_for(self.outq.get(), 1)
        if m["type"] == "websocket.close":
            return {"closed": m.get("code")}
        return json.loads(m["text"])

    async def quiet(self):
        try:
            return await asyncio.wait_for(self.outq.get(), 0.01)
        except asyncio.TimeoutError:
            return None

    async def close(self):
        self.inq.put_nowait({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(self.task, 1)


async def new_player(ip=None):
    status, body = await http("POST", "/api/players", ip=ip or fresh_ip())
    assert status == 201
    return body["token"]


async def connect(token, ip="34.200.1.7"):
    ws = WS(ip=ip)
    assert await ws.opened()
    ws.send({"t": "auth", "token": token})
    ready = await ws.recv()
    assert ready["t"] == "ready"
    return ws, ready


# ---- HTTP ------------------------------------------------------------------------------------

def test_new_player_starts_with_only_the_standard_skin():
    async def go():
        status, body = await http("POST", "/api/players", ip=fresh_ip())
        assert status == 201
        assert body["progress"] == {"chapters": [], "skins": ["standard"], "codex": [], "skin": "standard", "best": 0}
        status, me = await http("GET", "/api/me", token=body["token"])
        assert status == 200 and me["progress"]["skins"] == ["standard"]
    run(go())


def test_token_is_stored_hashed():
    async def go():
        token = await new_player()
        raw = open(os.environ["DB_PATH"], "rb").read()
        assert token.encode() not in raw
    run(go())


def test_unknown_token_is_refused():
    async def go():
        assert (await http("GET", "/api/me", token="x" * 43))[0] == 401
        assert (await http("GET", "/api/me"))[0] == 401
    run(go())


def test_cannot_equip_a_skin_you_do_not_own():
    async def go():
        token = await new_player()
        status, body = await http("PUT", "/api/me/skin", token=token, body={"skin": "void"})
        assert status == 403
        assert (await http("PUT", "/api/me/skin", token=token, body={"skin": "godmode"}))[0] == 400
        assert (await http("PUT", "/api/me/skin", token=token, body={"skin": "standard"}))[0] == 200
    run(go())


def test_oversized_body_is_refused():
    async def go():
        token = await new_player()
        status, _ = await http("PUT", "/api/me/skin", token=token, raw=b'{"skin":"' + b"a" * 5000 + b'"}')
        assert status == 400
    run(go())


def test_player_creation_is_rate_limited_per_ip():
    async def go():
        ip = fresh_ip()
        codes = [(await http("POST", "/api/players", ip=ip))[0] for _ in range(server.NEW_PER_IP_HOUR + 2)]
        assert codes[:server.NEW_PER_IP_HOUR] == [201] * server.NEW_PER_IP_HOUR
        assert codes[-1] == 429
    run(go())


def test_spoofed_forwarded_for_does_not_dodge_the_limit():
    async def go():
        real = fresh_ip()
        codes = []
        for i in range(server.NEW_PER_IP_HOUR + 2):
            codes.append((await http("POST", "/api/players", ip="1.2.3.%d, %s" % (i + 1, real)))[0])
        assert codes[-1] == 429
    run(go())


def test_database_has_a_hard_cap():
    async def go():
        server.store.max_players = server.store.count() + 2
        try:
            await new_player()
            await new_player()
            assert (await http("POST", "/api/players", ip=fresh_ip()))[0] == 503
        finally:
            server.store.max_players = 50
    run(go())


def test_delete_my_save():
    async def go():
        token = await new_player()
        assert (await http("DELETE", "/api/me", token=token))[0] == 200
        assert (await http("GET", "/api/me", token=token))[0] == 401
    run(go())


# ---- WebSocket --------------------------------------------------------------------------------

def test_socket_needs_a_valid_token():
    async def go():
        ws = WS()
        assert await ws.opened()
        ws.send({"t": "auth", "token": "not-a-real-token-at-all-1234"})
        assert (await ws.recv())["t"] == "error"
        assert "closed" in await ws.recv()
    run(go())


def test_socket_from_another_website_is_refused():
    async def go():
        ws = WS(origin="https://evil.example")
        assert not await ws.opened()
    run(go())


def test_honest_story_run_over_the_socket(fake_time):
    async def go():
        token = await new_player()
        ws, ready = await connect(token)
        assert ready["progress"]["skins"] == ["standard"]
        ws.send({"t": "start", "mode": "story", "ch": 1, "diff": 1})
        assert (await ws.recv())["t"] == "run"
        unlocked = set()
        for i in range(5):
            ws.send({"t": "room", "i": i})
            await ws.settle()
            for _ in range(30):
                fake_time.sleep(1)
                ws.send({"t": "k", "c": {"crawler": 2, "brute": 1}})
                m = await ws.quiet()
                if m:
                    unlocked.update(json.loads(m["text"])["new"]["codex"])
            ws.send({"t": "clear", "i": i})
            await ws.settle()
        ws.send({"t": "room", "i": 5})
        await ws.settle()
        fake_time.sleep(4)
        ws.send({"t": "boss", "b": "queen"})
        await ws.settle()
        fake_time.sleep(8)
        ws.send({"t": "evolve", "b": "queen"})
        m = await ws.recv()
        assert m.get("new", {}).get("codex") == ["queen"], m
        fake_time.sleep(10)
        ws.send({"t": "bosskill", "b": "queen"})
        await ws.settle()
        g = await ws.recv()
        assert g["new"]["skins"] == ["crimson"] and g["new"]["codex"] == ["queen2"]
        fake_time.sleep(6)
        ws.send({"t": "chdone", "ch": 1})
        g = await ws.recv()
        assert g["new"]["chapters"] == [1] and g["new"]["skins"] == ["hazmat"]
        ws.send({"t": "score", "s": 50000})
        assert (await ws.recv())["new"]["best"] == 50000
        await ws.close()
        assert unlocked == {"crawler", "brute"}
        status, me = await http("GET", "/api/me", token=token)
        p = me["progress"]
        assert p["chapters"] == [1] and set(p["skins"]) == {"standard", "crimson", "hazmat"} and p["best"] == 50000
        assert (await http("PUT", "/api/me/skin", token=token, body={"skin": "crimson"}))[0] == 200
    run(go())


def test_forged_socket_reports_unlock_nothing(fake_time):
    """What a cheater would type into the console with the player's own token."""
    async def go():
        token = await new_player()
        ws, _ = await connect(token)
        ws.send({"t": "start", "mode": "story", "ch": 1, "diff": 2})
        await ws.recv()
        for msg in ({"t": "room", "i": 5}, {"t": "bosskill", "b": "zero"}, {"t": "chdone", "ch": 1},
                    {"t": "k", "c": {"amalgam": 1}}, {"t": "score", "s": 10 ** 9}):
            ws.send(msg)
        assert (await ws.recv())["t"] == "void"
        assert await ws.quiet() is None                # the run is dead, no more replies
        await ws.close()
        _, me = await http("GET", "/api/me", token=token)
        assert me["progress"] == {"chapters": [], "skins": ["standard"], "codex": [], "skin": "standard", "best": 0}
    run(go())


def test_oversized_and_flooding_messages_close_the_socket(fake_time):
    async def go():
        token = await new_player()
        ws, _ = await connect(token)
        ws.send({"t": "ping", "pad": "x" * 2000})
        assert (await ws.recv()) == {"closed": 1009}
        await ws.close()

        ws, _ = await connect(token)
        for _ in range(server.MSG_PER_10S + 5):
            ws.send({"t": "ping"})
        got = [await ws.recv() for _ in range(server.MSG_PER_10S + 1)]
        assert got[-1] == {"closed": 1008}
        await ws.close()
    run(go())


def test_second_tab_takes_over_the_first():
    async def go():
        token = await new_player()
        first, _ = await connect(token)
        second, _ = await connect(token)
        assert (await first.recv()) == {"closed": 4000}
        second.send({"t": "ping"})
        assert (await second.recv())["t"] == "pong"
        await second.close()
        await first.close()
    run(go())


def test_dropped_run_can_be_resumed(fake_time):
    async def go():
        token = await new_player()
        ws, _ = await connect(token)
        ws.send({"t": "start", "mode": "endless", "diff": 1})
        run_id = (await ws.recv())["id"]
        ws.send({"t": "wave", "n": 1})
        await ws.settle()
        await ws.close()
        fake_time.sleep(30)
        ws, ready = await connect(token)
        assert ready["resumable"] == run_id
        ws.send({"t": "resume", "run": run_id})
        assert (await ws.recv())["resumed"] is True
        ws.send({"t": "k", "c": {"crawler": 16}})
        assert (await ws.recv())["new"]["codex"] == ["crawler"]
        await ws.close()
    run(go())


def test_too_many_sockets_from_one_ip():
    async def go():
        token = await new_player()
        ip = fresh_ip()
        socks = [WS(ip=ip) for _ in range(server.WS_PER_IP)]
        for s in socks:
            assert await s.opened()
        extra = WS(ip=ip)
        assert not await extra.opened()
        for s in socks:
            s.send({"t": "auth", "token": token})
        for s in socks:
            await s.close()
    run(go())


def test_binary_frame_closes_cleanly():
    async def go():
        token = await new_player()
        ws, _ = await connect(token)
        ws.inq.put_nowait({"type": "websocket.receive", "bytes": b"\x00\x01"})
        assert (await ws.recv()) == {"closed": 1003}
        await ws.close()
    run(go())


def test_garbage_content_length_is_a_400_not_a_crash():
    async def go():
        token = await new_player()
        scope_headers = [(b"authorization", ("Bearer " + token).encode()), (b"content-length", b"lots"),
                         (b"x-forwarded-for", b"34.200.1.7")]
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "PUT",
                 "scheme": "https", "path": "/api/me/skin", "raw_path": b"/api/me/skin", "query_string": b"",
                 "root_path": "", "headers": scope_headers, "client": ("10.0.0.1", 1), "server": ("t", 443)}
        out = {}

        async def receive():
            return {"type": "http.request", "body": b'{"skin":"standard"}', "more_body": False}

        async def send(m):
            if m["type"] == "http.response.start":
                out["status"] = m["status"]

        await server.app(scope, receive, send)
        assert out["status"] == 400
    run(go())
