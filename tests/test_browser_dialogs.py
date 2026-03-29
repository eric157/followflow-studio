from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from followflow import browser as browser_module


LOGIN_FLOW_HTML = """<!doctype html>
<html>
<body>
  <div id="cookie-banner">
    <button type="button" id="cookie-dismiss">Only allow essential cookies</button>
  </div>

  <form id="login-form">
    <input name="username" />
    <input name="password" type="password" />
    <button type="submit">Log in</button>
  </form>

  <div id="save-dialog" role="dialog" hidden>
    <button type="button" id="save-not-now">Not now</button>
  </div>

  <div id="notifications-dialog" role="dialog" hidden>
    <button type="button" id="notifications-not-now">Not now</button>
  </div>

  <script>
    document.getElementById("cookie-dismiss").addEventListener("click", () => {
      document.getElementById("cookie-banner").remove();
    });

    document.getElementById("login-form").addEventListener("submit", (event) => {
      event.preventDefault();
      document.getElementById("login-form").remove();
      setTimeout(() => {
        document.getElementById("save-dialog").hidden = false;
      }, 120);
    });

    document.getElementById("save-not-now").addEventListener("click", () => {
      document.getElementById("save-dialog").remove();
      setTimeout(() => {
        document.getElementById("notifications-dialog").hidden = false;
      }, 140);
    });

    document.getElementById("notifications-not-now").addEventListener("click", () => {
      document.getElementById("notifications-dialog").remove();
    });
  </script>
</body>
</html>
"""


STACKED_DIALOG_HTML = """<!doctype html>
<html>
<body>
  <div id="cookie-banner">
    <button type="button" id="cookie-dismiss">Only allow essential cookies</button>
  </div>

  <div id="first-dialog" role="dialog" hidden>
    <button type="button" id="first-skip">Not now</button>
  </div>

  <div id="second-dialog" role="dialog" hidden>
    <button type="button" aria-label="Close" id="second-close">x</button>
  </div>

  <script>
    document.getElementById("cookie-dismiss").addEventListener("click", () => {
      document.getElementById("cookie-banner").remove();
      setTimeout(() => {
        document.getElementById("first-dialog").hidden = false;
      }, 120);
    });

    document.getElementById("first-skip").addEventListener("click", () => {
      document.getElementById("first-dialog").remove();
      setTimeout(() => {
        document.getElementById("second-dialog").hidden = false;
      }, 120);
    });

    document.getElementById("second-close").addEventListener("click", () => {
      document.getElementById("second-dialog").remove();
    });
  </script>
</body>
</html>
"""


BAD_LOGIN_HTML = """<!doctype html>
<html>
<body>
  <form id="login-form">
    <input name="username" />
    <input name="password" type="password" />
    <button type="submit">Log in</button>
  </form>
  <p id="error"></p>
  <script>
    document.getElementById("login-form").addEventListener("submit", (event) => {
      event.preventDefault();
      document.getElementById("error").textContent = "Incorrect password";
    });
  </script>
</body>
</html>
"""


class BrowserDialogTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.page.close()

    def test_dismiss_instagram_dialogs_clears_stacked_prompts(self) -> None:
        self.page.set_content(STACKED_DIALOG_HTML)
        dismissed = browser_module.dismiss_instagram_dialogs(self.page, timeout_seconds=4.0)

        self.assertGreaterEqual(len(dismissed), 3)
        self.assertEqual(self.page.locator("#cookie-banner").count(), 0)
        self.assertEqual(self.page.locator("#first-dialog").count(), 0)
        self.assertEqual(self.page.locator("#second-dialog").count(), 0)

    def test_attempt_login_raises_for_bad_credentials_feedback(self) -> None:
        self.page.set_content(BAD_LOGIN_HTML)

        with self.assertRaises(SystemExit):
            browser_module.attempt_login(
                self.page,
                login_username="demo",
                login_password="wrong-password",
            )

    def test_wait_for_login_handles_cookie_banner_and_post_login_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            html_path = Path(tempdir) / "login-flow.html"
            html_path.write_text(LOGIN_FLOW_HTML, encoding="utf-8")

            original_home_url = browser_module.INSTAGRAM_HOME_URL
            original_login_url = browser_module.INSTAGRAM_LOGIN_URL
            browser_module.INSTAGRAM_HOME_URL = html_path.as_uri()
            browser_module.INSTAGRAM_LOGIN_URL = html_path.as_uri()
            try:
                browser_module.wait_for_login(
                    self.page,
                    login_username="demo_user",
                    login_password="super-secret",
                    allow_terminal_input=False,
                    timeout_seconds=8.0,
                )
            finally:
                browser_module.INSTAGRAM_HOME_URL = original_home_url
                browser_module.INSTAGRAM_LOGIN_URL = original_login_url

        self.assertFalse(browser_module.login_form_visible(self.page))
        self.assertEqual(self.page.locator("#cookie-banner").count(), 0)
        self.assertEqual(self.page.locator("#save-dialog").count(), 0)
        self.assertEqual(self.page.locator("#notifications-dialog").count(), 0)


if __name__ == "__main__":
    unittest.main()
