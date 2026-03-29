from __future__ import annotations

import functools
import http.server
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from followflow import browser as browser_module
from followflow import scrape as scrape_module


LOGIN_HTML = """<!doctype html>
<html>
<body>
  <form id="login-form">
    <input name="username" />
    <input name="password" type="password" />
    <button type="submit">Log in</button>
  </form>
  <script>
    document.getElementById("login-form").addEventListener("submit", (event) => {
      event.preventDefault();
      localStorage.setItem("loggedIn", "1");
      document.body.innerHTML = "<button type='button' id='save-not-now'>Not now</button>";
      document.getElementById("save-not-now").addEventListener("click", () => {
        document.body.innerHTML = "<button type='button' id='notif-not-now'>Not now</button>";
        document.getElementById("notif-not-now").addEventListener("click", () => {
          window.location.href = "/demo/";
        });
      });
    });
  </script>
</body>
</html>
"""


LOGIN_WITH_VERIFICATION_HTML = """<!doctype html>
<html>
<body>
  <form id="login-form">
    <input name="username" />
    <input name="password" type="password" />
    <button type="submit">Log in</button>
  </form>
  <script>
    document.getElementById("login-form").addEventListener("submit", (event) => {
      event.preventDefault();
      window.location.href = "/checkpoint/";
    });
  </script>
</body>
</html>
"""


CHECKPOINT_HTML = """<!doctype html>
<html>
<body>
  <h1>Enter the security code</h1>
  <p>Two-factor authentication is still in progress.</p>
  <script>
    setTimeout(() => {
      localStorage.setItem("loggedIn", "1");
      window.location.href = "/accounts/edit/";
    }, 3200);
  </script>
</body>
</html>
"""


PROFILE_HTML = """<!doctype html>
<html>
<body>
  <a id="followers-link" href="/demo/followers/">12 followers</a>
  <a id="following-link" href="/demo/following/">14 following</a>

  <div id="auth-dialog" role="dialog" hidden>
    <button type="button" id="prompt-login">Log in</button>
    <button type="button" id="prompt-signup">Sign up</button>
  </div>

  <div id="followers-dialog" role="dialog" hidden>
    <a href="/alpha/">alpha</a>
    <a href="/beta/">beta</a>
  </div>

  <div id="following-dialog" role="dialog" hidden>
    <a href="/gamma/">gamma</a>
    <a href="/delta/">delta</a>
  </div>

  <script>
    function loggedIn() {
      return localStorage.getItem("loggedIn") === "1";
    }

    function showDialog(id) {
      document.getElementById(id).hidden = false;
    }

    function hideDialog(id) {
      document.getElementById(id).hidden = true;
    }

    document.getElementById("followers-link").addEventListener("click", (event) => {
      event.preventDefault();
      if (loggedIn()) {
        showDialog("followers-dialog");
      } else {
        showDialog("auth-dialog");
      }
    });

    document.getElementById("following-link").addEventListener("click", (event) => {
      event.preventDefault();
      if (loggedIn()) {
        showDialog("following-dialog");
      } else {
        showDialog("auth-dialog");
      }
    });

    document.getElementById("prompt-login").addEventListener("click", () => {
      window.location.href = "/login.html";
    });

    document.getElementById("prompt-signup").addEventListener("click", () => {
      hideDialog("auth-dialog");
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hideDialog("followers-dialog");
        hideDialog("following-dialog");
        hideDialog("auth-dialog");
      }
    });
  </script>
</body>
</html>
"""


EDIT_HTML = """<!doctype html>
<html>
<body>
  <input name="username" value="demo" />
</body>
</html>
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        return


class ScrapeAuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self) -> None:
        self.page = self.browser.new_page()
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        (root / "demo").mkdir(parents=True, exist_ok=True)
        (root / "checkpoint").mkdir(parents=True, exist_ok=True)
        (root / "accounts" / "edit").mkdir(parents=True, exist_ok=True)
        (root / "login.html").write_text(LOGIN_HTML, encoding="utf-8")
        (root / "login-with-verification.html").write_text(LOGIN_WITH_VERIFICATION_HTML, encoding="utf-8")
        (root / "checkpoint" / "index.html").write_text(CHECKPOINT_HTML, encoding="utf-8")
        (root / "demo" / "index.html").write_text(PROFILE_HTML, encoding="utf-8")
        (root / "accounts" / "edit" / "index.html").write_text(EDIT_HTML, encoding="utf-8")

        handler = functools.partial(QuietHandler, directory=str(root))
        self.server = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

        self.original_home = browser_module.INSTAGRAM_HOME_URL
        self.original_login = browser_module.INSTAGRAM_LOGIN_URL
        self.original_base = scrape_module.INSTAGRAM_BASE
        browser_module.INSTAGRAM_HOME_URL = f"{self.base_url}/login.html"
        browser_module.INSTAGRAM_LOGIN_URL = f"{self.base_url}/login.html"
        scrape_module.INSTAGRAM_BASE = f"{self.base_url}/"

    def tearDown(self) -> None:
        browser_module.INSTAGRAM_HOME_URL = self.original_home
        browser_module.INSTAGRAM_LOGIN_URL = self.original_login
        scrape_module.INSTAGRAM_BASE = self.original_base
        self.page.close()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)
        self.tempdir.cleanup()

    def test_scrape_list_recovers_from_profile_login_prompt(self) -> None:
        usernames = scrape_module.scrape_list(
            self.page,
            "demo",
            "followers",
            login_username="demo_login",
            login_password="super-secret",
            allow_terminal_input=False,
        )

        self.assertEqual(usernames, ["alpha", "beta"])
        self.assertEqual(self.page.evaluate("() => localStorage.getItem('loggedIn')"), "1")
        self.assertIn("/demo/", self.page.url)

    def test_resolve_account_username_still_works_after_auth_recovery(self) -> None:
        browser_module.wait_for_login(
            self.page,
            login_username="demo_login",
            login_password="super-secret",
            allow_terminal_input=False,
            timeout_seconds=8.0,
        )

        username = scrape_module.resolve_account_username(
            self.page,
            explicit_username=None,
            login_username="demo_login",
            login_password="super-secret",
            allow_terminal_input=False,
        )

        self.assertEqual(username, "demo")

    def test_wait_for_login_waits_until_checkpoint_finishes(self) -> None:
        browser_module.INSTAGRAM_HOME_URL = f"{self.base_url}/login-with-verification.html"
        browser_module.INSTAGRAM_LOGIN_URL = f"{self.base_url}/login-with-verification.html"

        import time

        start = time.monotonic()
        browser_module.wait_for_login(
            self.page,
            login_username="demo_login",
            login_password="super-secret",
            allow_terminal_input=False,
            timeout_seconds=10.0,
            resume_url=f"{self.base_url}/demo/",
        )
        elapsed = time.monotonic() - start

        self.assertGreaterEqual(elapsed, 3.0)
        self.assertEqual(self.page.evaluate("() => localStorage.getItem('loggedIn')"), "1")
        self.assertIn("/demo/", self.page.url)


if __name__ == "__main__":
    unittest.main()
