"""Hidden acceptance tests for plans Hacivat writes from brief.md (kisalink).

Never visible to Hacivat or the agents executing its plan; the runner drops
them in afterwards. They test only what the brief fixes: the endpoints, the
JSON fields it names, the rules, and how the server is started. Status codes
the brief leaves open (invalid input) are checked as "a 4xx other than 429".
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path.cwd()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, db):
        self.port = free_port()
        env = {**os.environ, "KISALINK_DB": str(db), "KISALINK_PORT": str(self.port),
               "KISALINK_HOST": "127.0.0.1"}
        self.p = subprocess.Popen([sys.executable, "-m", "kisalink"], cwd=ROOT, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), 0.2).close()
                return
            except OSError:
                if self.p.poll() is not None:
                    raise RuntimeError("server exited")
                time.sleep(0.1)
        raise RuntimeError("server did not start")

    def req(self, method, path, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
                                   headers={"Content-Type": "application/json"})
        try:
            resp = OPENER.open(r, timeout=5)
            return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def shorten(self, url):
        st, _, b = self.req("POST", "/api/kisalt", {"url": url})
        return st, (json.loads(b) if b else {})

    def stop(self):
        self.p.terminate()
        try:
            self.p.wait(5)
        except subprocess.TimeoutExpired:
            self.p.kill()


@pytest.fixture
def db(tmp_path):
    return tmp_path / "sub" / "kisalink.db"


@pytest.fixture
def srv(tmp_path):
    (tmp_path / "d").mkdir()
    s = Server(tmp_path / "d" / "k.db")
    yield s
    s.stop()


def is_client_error(st):
    return 400 <= st < 500 and st != 429


def test_shorten_returns_7_char_base62_code(srv):
    st, d = srv.shorten("https://example.com/a?b=1")
    assert st in (200, 201)
    assert re.fullmatch(r"[0-9A-Za-z]{7}", d["kod"])
    assert d["kisa_url"].endswith("/" + d["kod"])


def test_same_url_same_code_and_different_url_different_code(srv):
    _, a = srv.shorten("http://example.com/x")
    _, b = srv.shorten("http://example.com/x")
    _, c = srv.shorten("http://example.com/y")
    assert a["kod"] == b["kod"]
    assert a["kod"] != c["kod"]


@pytest.mark.parametrize("url", ["ftp://example.com/f", "javascript:alert(1)", "example.com",
                                 "file:///etc/passwd", ""])
def test_rejects_non_http_urls(srv, url):
    st, _ = srv.shorten(url)
    assert is_client_error(st)


@pytest.mark.parametrize("raw", [b"not json", b"{}", b'{"url": 5}', b"[]"])
def test_rejects_bad_bodies(srv, raw):
    st, _, _ = srv.req("POST", "/api/kisalt", raw=raw)
    assert is_client_error(st)


def test_redirects_with_302_to_the_original(srv):
    _, d = srv.shorten("https://example.com/hedef?q=1")
    st, h, _ = srv.req("GET", "/" + d["kod"])
    assert st == 302
    assert {k.lower(): v for k, v in h.items()}["location"] == "https://example.com/hedef?q=1"


def test_clicks_are_counted_in_stats(srv):
    _, d = srv.shorten("https://example.com/sayac")
    st, _, b = srv.req("GET", "/api/istatistik/" + d["kod"])
    assert st == 200
    before = json.loads(b)
    for _ in range(3):
        srv.req("GET", "/" + d["kod"])
    _, _, b = srv.req("GET", "/api/istatistik/" + d["kod"])
    after = json.loads(b)
    ints_before = {k: v for k, v in before.items() if isinstance(v, int) and not isinstance(v, bool)}
    ints_after = {k: v for k, v in after.items() if isinstance(v, int) and not isinstance(v, bool)}
    assert any(ints_after.get(k) == v + 3 for k, v in ints_before.items()), (before, after)
    assert any(isinstance(v, (str, int, float)) and re.search(r"\d{4}-\d{2}-\d{2}|^\d{10}", str(v))
               for v in after.values()), after


def test_unknown_code_is_404(srv):
    assert srv.req("GET", "/ZZZZZZZ")[0] == 404
    assert srv.req("GET", "/api/istatistik/ZZZZZZZ")[0] == 404


def test_rate_limit_30_per_minute(srv):
    statuses = [srv.req("GET", "/api/istatistik/ZZZZZZZ")[0] for _ in range(30)]
    assert 429 not in statuses
    assert srv.req("GET", "/api/istatistik/ZZZZZZZ")[0] == 429


def test_db_path_from_env_and_survives_restart(db):
    db.parent.mkdir(parents=True)
    s = Server(db)
    try:
        _, d = s.shorten("https://example.com/kalici")
    finally:
        s.stop()
    assert db.exists()
    s = Server(db)
    try:
        st, h, _ = s.req("GET", "/" + d["kod"])
        assert st == 302
        _, again = s.shorten("https://example.com/kalici")
        assert again["kod"] == d["kod"]
    finally:
        s.stop()
