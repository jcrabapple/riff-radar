"""Local web UI: report grid, scan button, seed artist management.

Stdlib only (http.server). No authentication — it is a local tool, so the
default bind is 127.0.0.1. Use --host 0.0.0.0 only on a trusted LAN or
inside a container with a published port.
"""

from __future__ import annotations

import html
import json
import threading
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from .config import Config, load, save, add_seeds, remove_seeds
from .deezer import DeezerClient
from .report import CSS as REPORT_CSS, JS as REPORT_JS, body_html
from .scanner import scan, result_to_dict
from .store import Store

EXTRA_CSS = """
.toolbar { display:flex; gap:0.75rem; align-items:center; margin-top:1rem;
           flex-wrap:wrap; }
button.scan { background:#ff4d2e; color:#0d0d10; border:none; border-radius:6px;
              padding:0.5rem 1.2rem; font-weight:650; font-size:0.9rem;
              cursor:pointer; }
button.scan:hover { background:#ff6a4f; }
button.scan:disabled { background:#26262e; color:#8b8b96; cursor:wait; }
.scanstatus { color:#8b8b96; font-size:0.85rem; }
.seeds { display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center;
         padding:1rem 2rem 0; }
.seeds .label { color:#55555e; font-size:0.75rem; text-transform:uppercase;
                letter-spacing:0.06em; margin-right:0.25rem; }
.chip { display:inline-flex; align-items:center; gap:0.45rem;
        background:#16161c; border:1px solid #26262e; border-radius:999px;
        padding:0.3rem 0.5rem 0.3rem 0.85rem; font-size:0.82rem; color:#c9c9d4; }
.chip button { background:none; border:none; color:#8b8b96; cursor:pointer;
               font-size:0.95rem; line-height:1; padding:0.1rem 0.3rem;
               border-radius:50%; }
.chip button:hover { color:#ff4d2e; }
.seeds form.add { display:inline-flex; gap:0.4rem; }
.seeds input { background:#16161c; border:1px solid #26262e; border-radius:6px;
               color:#e8e6e3; padding:0.35rem 0.6rem; font-size:0.82rem;
               width:11rem; }
.seeds input:focus { outline:none; border-color:#ff4d2e; }
.seeds form.add button { background:#26262e; color:#c9c9d4; border:none;
                         border-radius:6px; padding:0.35rem 0.8rem;
                         font-size:0.82rem; cursor:pointer; }
.seeds form.add button:hover { background:#ff4d2e; color:#0d0d10; }
"""

PAGE_JS = """
const btn = document.getElementById('scanbtn');
const status = document.getElementById('scanstatus');
let poll = null;
function fmtLast(last) {
  if (!last) return '';
  return 'last scan: ' + last.artists_scanned + ' artists, '
    + last.new_releases.length + ' new release(s)';
}
function setState(s) {
  if (s.state === 'running') {
    btn.disabled = true;
    status.textContent = 'scanning...';
    if (!poll) poll = setInterval(check, 2000);
  } else {
    btn.disabled = false;
    status.textContent = fmtLast(s.last);
    if (poll) { clearInterval(poll); poll = null; }
  }
}
function check() {
  fetch('/api/status').then(r => r.json()).then(s => {
    const wasRunning = btn.disabled;
    setState(s);
    if (wasRunning && s.state !== 'running') location.reload();
  }).catch(() => {});
}
btn.addEventListener('click', () => {
  btn.disabled = true;
  status.textContent = 'starting scan...';
  fetch('/api/scan', {method: 'POST'}).then(r => {
    if (r.status === 409) { status.textContent = 'scan already running'; }
    if (!poll) poll = setInterval(check, 2000);
  }).catch(() => { setState({state: 'idle'}); });
});
check();
"""


class WebApp:
    """State shared across request handlers."""

    def __init__(self, config_path: Path | None = None,
                 client_factory: Callable[[], object] | None = None):
        self.config_path = config_path
        self.client_factory = client_factory or (lambda: DeezerClient(delay=0.15))
        self._scan_lock = threading.Lock()
        self._scan_state: dict = {"state": "idle", "last": None}

    def config(self) -> Config:
        return load(self.config_path)

    def store(self, cfg: Config) -> Store:
        return Store(cfg.data_path / "riff-radar.db")

    def scan_status(self) -> dict:
        with self._scan_lock:
            return dict(self._scan_state)

    def start_scan(self) -> bool:
        """Kick off a background scan. False if one is already running."""
        with self._scan_lock:
            if self._scan_state["state"] == "running":
                return False
            self._scan_state = {"state": "running", "last": self._scan_state["last"]}
        threading.Thread(target=self._run_scan, daemon=True).start()
        return True

    def _run_scan(self) -> None:
        try:
            cfg = self.config()
            store = self.store(cfg)
            result = scan(self.client_factory(), store, cfg)
            store.close()
            summary = result_to_dict(result, cfg)
        except Exception as e:  # surface failures in the UI instead of dying
            summary = {"error": str(e), "artists_scanned": 0, "new_releases": []}
        with self._scan_lock:
            self._scan_state = {"state": "idle", "last": summary}

    def track(self, names: list[str]) -> None:
        cfg = self.config()
        added, _ = add_seeds(cfg, names)
        if added:
            save(cfg, self.config_path)

    def untrack(self, names: list[str]) -> None:
        cfg = self.config()
        removed, _ = remove_seeds(cfg, names)
        if removed:
            save(cfg, self.config_path)


def _page(app: WebApp) -> str:
    cfg = app.config()
    store = app.store(cfg)
    stats = store.stats()
    grid = body_html(store)
    store.close()
    chips = "".join(
        f'''<span class="chip">{html.escape(name)}<form method="post"
action="/api/untrack" style="display:inline"><input type="hidden" name="name"
value="{html.escape(name, quote=True)}"><button title="untrack">&times;</button></form></span>'''
        for name in cfg.seed_artists)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>riff-radar</title>
<style>{REPORT_CSS}{EXTRA_CSS}</style>
</head><body>
<header>
  <h1>riff<span class="accent">-radar</span></h1>
  <div class="sub">{stats['releases']} releases tracked · {stats['artists']} artists ·
    {stats['scans']} scans · {date.today().isoformat()}</div>
  <div class="toolbar">
    <button class="scan" id="scanbtn">Scan now</button>
    <span class="scanstatus" id="scanstatus"></span>
  </div>
</header>
<div class="seeds">
  <span class="label">seed artists</span>
  {chips}
  <form class="add" method="post" action="/api/track">
    <input name="name" placeholder="add artist..." required>
    <button type="submit">Track</button>
  </form>
</div>
{grid}
<footer>Scores are explainable: recency (0-40) + artist proximity (0-35) + scene keywords (0-25).
Unauthenticated local UI — do not expose to the internet.</footer>
<script>{REPORT_JS}{PAGE_JS}</script>
</body></html>"""


def make_handler(app: WebApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "riff-radar"

        def log_message(self, fmt, *args):  # keep stdout quiet
            pass

        def _send(self, code: int, body: str | bytes,
                  ctype: str = "text/html; charset=utf-8",
                  headers: dict | None = None) -> None:
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code: int, obj: dict) -> None:
            self._send(code, json.dumps(obj), "application/json")

        def _form_fields(self) -> dict[str, list[str]]:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode(errors="replace")
            return urllib.parse.parse_qs(raw)

        def _redirect_home(self) -> None:
            self._send(303, b"", headers={"Location": "/"})

        def do_GET(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/":
                self._send(200, _page(app))
            elif path == "/api/status":
                self._json(200, app.scan_status())
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/scan":
                if app.start_scan():
                    self._json(202, {"state": "running"})
                else:
                    self._json(409, {"state": "running",
                                     "error": "scan already in progress"})
            elif path == "/api/track":
                names = [n.strip()
                         for field in self._form_fields().get("name", [])
                         for n in field.split(",") if n.strip()]
                if names:
                    app.track(names)
                self._redirect_home()
            elif path == "/api/untrack":
                names = [field.strip()
                         for field in self._form_fields().get("name", [])
                         if field.strip()]
                if names:
                    app.untrack(names)
                self._redirect_home()
            else:
                self._send(404, "not found", "text/plain")

    return Handler


def serve(config_path: Path | None = None, host: str = "127.0.0.1",
          port: int = 8777, client_factory=None) -> int:
    app = WebApp(config_path, client_factory)
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    httpd.daemon_threads = True
    print(f"riff-radar listening on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
