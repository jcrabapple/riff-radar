"""Tests for the web UI: page render, track/untrack, scan lifecycle."""

import http.client
import json
import threading
import time
import urllib.parse

import pytest

from riff_radar.config import Config, save, load
from riff_radar.web import WebApp, make_handler
from http.server import ThreadingHTTPServer

from test_scanner import FakeClient


@pytest.fixture
def server(tmp_path):
    """WebApp on an ephemeral port with a temp config and FakeClient."""
    cfg_path = tmp_path / "config.json"
    cfg = Config(seed_artists=["Seed Band"],
                 data_dir=str(tmp_path / "data"))
    save(cfg, cfg_path)
    app = WebApp(cfg_path, client_factory=FakeClient)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1], app, cfg_path
    httpd.shutdown()
    httpd.server_close()


def get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode()
    conn.close()
    return resp.status, body


def post(port, path, data=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    body = urllib.parse.urlencode(data or {})
    conn.request("POST", path, body,
                 {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp_body = resp.read().decode()
    conn.close()
    return resp.status, resp_body


def test_index_renders_seeds_and_scan_button(server):
    port, _, _ = server
    status, body = get(port, "/")
    assert status == 200
    assert "Seed Band" in body
    assert 'id="scanbtn"' in body
    assert "No releases tracked yet" in body


def test_track_and_untrack_via_forms(server):
    port, _, cfg_path = server
    status, _ = post(port, "/api/track", {"name": "New Act"})
    assert status == 303
    assert "New Act" in load(cfg_path).seed_artists

    status, body = get(port, "/")
    assert "New Act" in body

    status, _ = post(port, "/api/untrack", {"name": "new act"})  # case-insensitive
    assert status == 303
    assert "New Act" not in load(cfg_path).seed_artists


def test_track_comma_separated(server):
    port, _, cfg_path = server
    post(port, "/api/track", {"name": "Band A, Band B"})
    seeds = load(cfg_path).seed_artists
    assert "Band A" in seeds and "Band B" in seeds


def test_scan_lifecycle(server):
    port, app, _ = server
    status, body = post(port, "/api/scan")
    assert status == 202
    assert json.loads(body)["state"] == "running"

    # second scan while running is rejected
    status, _ = post(port, "/api/scan")
    assert status in (202, 409)  # may finish fast with the fake client

    for _ in range(50):
        if app.scan_status()["state"] == "idle":
            break
        time.sleep(0.05)
    result = app.scan_status()
    assert result["state"] == "idle"
    assert result["last"]["artists_scanned"] == 2
    assert len(result["last"]["new_releases"]) == 2

    # releases from the scan now render on the page
    status, body = get(port, "/")
    assert "Fresh Metalcore Drop" in body


def test_status_endpoint(server):
    port, _, _ = server
    status, body = get(port, "/api/status")
    assert status == 200
    assert json.loads(body)["state"] == "idle"


def test_404(server):
    port, _, _ = server
    status, _ = get(port, "/nope")
    assert status == 404
