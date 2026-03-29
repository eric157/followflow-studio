from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ALLOWED_COMMANDS = {"u", "f", "s", "r", "q"}

UI_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FollowFlow Review</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5efe7;
      --surface: rgba(255, 252, 246, 0.88);
      --surface-strong: #fffdfa;
      --ink: #1d1b18;
      --muted: #6e6558;
      --line: rgba(89, 74, 54, 0.14);
      --emerald: #1f6f64;
      --ember: #d66f46;
      --gold: #c6a45a;
      --danger: #b64747;
      --shadow: 0 24px 60px rgba(51, 40, 28, 0.12);
      --radius: 28px;
      --radius-small: 18px;
      --font-ui: "Trebuchet MS", "Segoe UI", sans-serif;
      --font-display: Georgia, "Times New Roman", serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: var(--font-ui);
      background:
        radial-gradient(circle at 12% 18%, rgba(214, 111, 70, 0.24), transparent 20rem),
        radial-gradient(circle at 85% 15%, rgba(31, 111, 100, 0.18), transparent 24rem),
        radial-gradient(circle at 78% 88%, rgba(198, 164, 90, 0.18), transparent 18rem),
        linear-gradient(180deg, #f8f4ee 0%, #efe6d9 100%);
    }

    .page {
      width: min(1180px, calc(100vw - 2rem));
      margin: 1.5rem auto 2rem;
      display: grid;
      gap: 1rem;
    }

    .hero,
    .panel {
      border: 1px solid var(--line);
      background: var(--surface);
      backdrop-filter: blur(18px);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }

    .hero {
      padding: 1.3rem 1.4rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      overflow: hidden;
      position: relative;
    }

    .hero::after {
      content: "";
      position: absolute;
      inset: auto -10% -45% auto;
      width: 20rem;
      height: 20rem;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(31, 111, 100, 0.14), transparent 68%);
      pointer-events: none;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 1rem;
      position: relative;
      z-index: 1;
    }

    .mark {
      width: 64px;
      height: 64px;
      border-radius: 22px;
      background:
        linear-gradient(145deg, rgba(31, 111, 100, 0.14), rgba(214, 111, 70, 0.22)),
        var(--surface-strong);
      border: 1px solid rgba(31, 111, 100, 0.16);
      display: grid;
      place-items: center;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
    }

    .mark svg { width: 40px; height: 40px; }

    .hero-copy h1 {
      margin: 0;
      font-family: var(--font-display);
      font-size: clamp(2rem, 3vw, 2.65rem);
      line-height: 1;
      letter-spacing: -0.03em;
    }

    .hero-copy p {
      margin: 0.4rem 0 0;
      color: var(--muted);
      font-size: 1rem;
      max-width: 38rem;
      line-height: 1.45;
    }

    .hero-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 0.65rem;
      justify-content: flex-end;
      position: relative;
      z-index: 1;
    }

    .badge {
      padding: 0.65rem 0.9rem;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.64);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.92rem;
      white-space: nowrap;
    }

    .main {
      display: grid;
      grid-template-columns: minmax(300px, 360px) 1fr;
      gap: 1rem;
    }

    .profile-card {
      padding: 1.35rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
      align-items: center;
      text-align: center;
    }

    .avatar-shell {
      width: min(100%, 260px);
      aspect-ratio: 1;
      border-radius: 32px;
      padding: 10px;
      background: linear-gradient(145deg, rgba(31, 111, 100, 0.14), rgba(214, 111, 70, 0.22));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
    }

    .avatar,
    .fallback {
      width: 100%;
      height: 100%;
      border-radius: 24px;
      object-fit: cover;
      border: 1px solid rgba(31, 111, 100, 0.1);
      background: linear-gradient(180deg, #f3eadf 0%, #fdf8f1 100%);
    }

    .fallback {
      display: grid;
      place-items: center;
      font-size: 4.4rem;
      font-family: var(--font-display);
      color: var(--emerald);
    }

    .identity {
      display: grid;
      gap: 0.35rem;
    }

    .identity h2 {
      margin: 0;
      font-size: 1.9rem;
      line-height: 1.05;
      font-family: var(--font-display);
    }

    .identity p {
      margin: 0;
      color: var(--muted);
      font-size: 1rem;
    }

    .status-card {
      display: grid;
      gap: 1rem;
      padding: 1.35rem;
    }

    .status-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }

    .eyebrow {
      color: var(--muted);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }

    .status-top h3 {
      margin: 0.35rem 0 0;
      font-size: 1.55rem;
      font-family: var(--font-display);
    }

    .phase {
      padding: 0.7rem 0.95rem;
      border-radius: 999px;
      border: 1px solid rgba(31, 111, 100, 0.18);
      background: rgba(31, 111, 100, 0.08);
      color: var(--emerald);
      font-weight: 700;
      text-transform: capitalize;
      white-space: nowrap;
    }

    .metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0.8rem;
    }

    .metric {
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.64);
      padding: 1rem;
      display: grid;
      gap: 0.35rem;
    }

    .metric span {
      color: var(--muted);
      font-size: 0.86rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .metric strong {
      font-size: 1.35rem;
      line-height: 1;
    }

    .progress-track {
      width: 100%;
      height: 14px;
      border-radius: 999px;
      background: rgba(31, 111, 100, 0.08);
      overflow: hidden;
      border: 1px solid rgba(31, 111, 100, 0.08);
    }

    .progress-bar {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--emerald), var(--gold), var(--ember));
      border-radius: inherit;
      transition: width 0.35s ease;
    }

    .message,
    .last-action,
    .shortcut-card {
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.64);
      padding: 1rem 1.1rem;
      line-height: 1.5;
    }

    .last-action strong {
      display: block;
      font-size: 0.85rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 0.3rem;
    }

    .actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.85rem;
    }

    button {
      border: none;
      border-radius: 18px;
      padding: 1rem 1.05rem;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.12s ease, opacity 0.12s ease, box-shadow 0.12s ease;
      box-shadow: 0 12px 22px rgba(42, 34, 24, 0.08);
    }

    button:hover { transform: translateY(-1px); }
    button:disabled { cursor: default; opacity: 0.55; transform: none; box-shadow: none; }

    .primary { background: linear-gradient(135deg, var(--emerald), #2d8878); color: white; }
    .secondary { background: linear-gradient(135deg, #f3e3cb, #f7efe3); color: var(--ink); }
    .accent { background: linear-gradient(135deg, var(--ember), #db8a64); color: white; }
    .danger { background: linear-gradient(135deg, var(--danger), #cf6a64); color: white; }

    .shortcuts {
      display: flex;
      flex-wrap: wrap;
      gap: 0.55rem;
      margin-top: 0.75rem;
    }

    .keycap {
      padding: 0.45rem 0.7rem;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fffdfa;
      font-size: 0.9rem;
      color: var(--muted);
    }

    @media (max-width: 920px) {
      .main {
        grid-template-columns: 1fr;
      }

      .hero {
        flex-direction: column;
        align-items: flex-start;
      }

      .hero-badges {
        justify-content: flex-start;
      }
    }

    @media (max-width: 640px) {
      .page {
        width: min(100vw - 1rem, 100%);
      }

      .hero,
      .profile-card,
      .status-card {
        padding: 1rem;
      }

      .metrics,
      .actions {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="brand">
        <div class="mark" aria-hidden="true">
          <svg viewBox="0 0 48 48" fill="none">
            <path d="M10 16.5C10 12.358 13.358 9 17.5 9H30.5C34.642 9 38 12.358 38 16.5V29.5C38 33.642 34.642 37 30.5 37H17.5C13.358 37 10 33.642 10 29.5V16.5Z" stroke="#1F6F64" stroke-width="2.4"/>
            <path d="M17 25.5C19.3 28.4 22.1 29.8 25.3 29.8C29.1 29.8 31.8 27.5 34 22.8" stroke="#D66F46" stroke-width="2.4" stroke-linecap="round"/>
            <circle cx="18.5" cy="19" r="2.2" fill="#1F6F64"/>
            <circle cx="30.5" cy="19" r="2.2" fill="#D66F46"/>
          </svg>
        </div>
        <div class="hero-copy">
          <h1>FollowFlow</h1>
          <p>Polished review control for follower cleanup, session tracking, and profile-by-profile decision making.</p>
        </div>
      </div>
      <div class="hero-badges">
        <div class="badge" id="badgeProgress">0 / 0 queued</div>
        <div class="badge" id="badgeState">Idle</div>
        <div class="badge">Local panel</div>
      </div>
    </section>

    <section class="main">
      <aside class="panel profile-card">
        <div class="avatar-shell">
          <img id="avatar" class="avatar" alt="Profile photo" hidden />
          <div id="fallback" class="fallback">@</div>
        </div>
        <div class="identity">
          <h2 id="displayName">Waiting for profile...</h2>
          <p id="username">@username</p>
        </div>
      </aside>

      <section class="panel status-card">
        <div class="status-top">
          <div>
            <div class="eyebrow">Current Review</div>
            <h3 id="headline">Ready to start</h3>
          </div>
          <div class="phase" id="state">idle</div>
        </div>

        <div class="metrics">
          <div class="metric">
            <span>Progress</span>
            <strong id="progress">0 / 0</strong>
          </div>
          <div class="metric">
            <span>Remaining</span>
            <strong id="remaining">0</strong>
          </div>
          <div class="metric">
            <span>Panel Mode</span>
            <strong>Control</strong>
          </div>
        </div>

        <div class="progress-track" aria-hidden="true">
          <div class="progress-bar" id="progressBar"></div>
        </div>

        <div class="message" id="message">
          The review session will show the current profile here once the Instagram browser is ready.
        </div>

        <div class="last-action">
          <strong>Latest Update</strong>
          <div id="lastAction">Waiting for the session to begin.</div>
        </div>

        <div class="actions">
          <button class="primary" data-command="u">Mark Unfollowed</button>
          <button class="secondary" data-command="f">Toggle Follow</button>
          <button class="secondary" data-command="s">Skip</button>
          <button class="accent" data-command="r">Reload</button>
          <button class="danger" data-command="q">Quit Session</button>
        </div>

        <div class="shortcut-card">
          Keep the Instagram browser visible while this panel stays nearby for fast decisions.
          <div class="shortcuts">
            <div class="keycap">U = mark unfollowed</div>
            <div class="keycap">F = toggle follow</div>
            <div class="keycap">S = skip</div>
            <div class="keycap">R = reload</div>
            <div class="keycap">Q = quit</div>
          </div>
        </div>
      </section>
    </section>
  </main>

  <script>
    const avatar = document.getElementById("avatar");
    const fallback = document.getElementById("fallback");
    const displayName = document.getElementById("displayName");
    const username = document.getElementById("username");
    const progress = document.getElementById("progress");
    const remaining = document.getElementById("remaining");
    const state = document.getElementById("state");
    const headline = document.getElementById("headline");
    const message = document.getElementById("message");
    const lastAction = document.getElementById("lastAction");
    const badgeProgress = document.getElementById("badgeProgress");
    const badgeState = document.getElementById("badgeState");
    const progressBar = document.getElementById("progressBar");
    const buttons = Array.from(document.querySelectorAll("button[data-command]"));

    async function sendCommand(command) {
      await fetch("/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command })
      });
    }

    buttons.forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await sendCommand(button.dataset.command);
        } finally {
          setTimeout(() => { button.disabled = false; }, 320);
        }
      });
    });

    function render(data) {
      const current = Number(data.current_index || 0);
      const total = Number(data.total || 0);
      const currentDisplay = total === 0 ? 0 : Math.min(current, total);
      const remainingCount = Math.max(total - currentDisplay, 0);
      const percent = total > 0 ? Math.min((currentDisplay / total) * 100, 100) : 0;

      displayName.textContent = data.display_name || "Waiting for profile...";
      username.textContent = data.username ? `@${data.username}` : "@username";
      progress.textContent = `${currentDisplay} / ${total}`;
      remaining.textContent = `${remainingCount}`;
      state.textContent = data.state || "idle";
      headline.textContent = data.username ? `Reviewing @${data.username}` : "Ready to start";
      message.textContent = data.message || "Waiting for review activity.";
      lastAction.textContent = data.last_action || data.message || "Waiting for review activity.";
      badgeProgress.textContent = `${currentDisplay} / ${total} queued`;
      badgeState.textContent = (data.state || "idle").replaceAll("_", " ");
      progressBar.style.width = `${percent}%`;

      if (data.profile_image_url) {
        avatar.src = data.profile_image_url;
        avatar.hidden = false;
        fallback.hidden = true;
      } else {
        avatar.hidden = true;
        fallback.hidden = false;
        fallback.textContent = data.username ? data.username[0].toUpperCase() : "@";
      }
    }

    async function refresh() {
      try {
        const response = await fetch("/state", { cache: "no-store" });
        const data = await response.json();
        render(data);
      } catch (error) {
        message.textContent = "The local review UI lost contact with the review process.";
      }
    }

    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


class ReviewUiState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload = {
            "username": "",
            "display_name": "",
            "profile_image_url": "",
            "current_index": 0,
            "total": 0,
            "state": "idle",
            "message": "Waiting for the review session to begin.",
            "last_action": "Waiting for the review session to begin.",
        }

    def update(self, **kwargs) -> None:
        with self._lock:
            self._payload.update(kwargs)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._payload)


class ReviewUiServer:
    def __init__(self, state: ReviewUiState, command_sink) -> None:
        self._state = state
        self._command_sink = command_sink
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.url: str | None = None

    def start(self) -> None:
        state = self._state
        command_sink = self._command_sink

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path in {"/", "/index.html"}:
                    body = UI_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if self.path == "/state":
                    payload = json.dumps(state.snapshot()).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                self.send_error(404)

            def do_POST(self) -> None:
                if self.path != "/action":
                    self.send_error(404)
                    return

                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length)
                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                except json.JSONDecodeError:
                    self.send_error(400)
                    return

                command = str(payload.get("command", "")).strip().lower()
                if command not in ALLOWED_COMMANDS:
                    self.send_error(400)
                    return

                command_sink.put(command)
                response = b'{"ok": true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, format: str, *args) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def open_browser(self) -> None:
        if self.url:
            webbrowser.open(self.url, new=2)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self._thread = None
