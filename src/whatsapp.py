from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

DEFAULT_PROFILE_DIR = Path("browser_profile")
WHATSAPP_WEB_URL = "https://web.whatsapp.com"
LOGIN_TIMEOUT_MS = 120_000
CHAT_LOAD_TIMEOUT_MS = 30_000

CHAT_PANEL_SELECTOR = "#main"
INVALID_PHONE_SELECTOR = "div[data-animate-modal-popup='true']"
MESSAGE_BOX_SELECTOR = "#main footer div[contenteditable='true']"
SEND_BUTTON_SELECTOR = "#main footer button[aria-label='Enviar'], #main footer button[aria-label='Send']"
CHAT_HEADER_TITLE_SELECTOR = "header span[dir='auto']"
LAST_MESSAGE_OUT_SELECTOR = "div.message-out"


@dataclass
class ChatResult:
    found: bool
    displayed_name: str | None
    error: str | None = None


class WhatsAppClient:
    """Thin wrapper around WhatsApp Web driven via Playwright.

    Opens a chat by phone number through the wa.me-style deep link so contacts
    do not need to be saved in advance; the phone number stays the authoritative
    identifier, matching the project's validation rules.
    """

    def __init__(self, profile_dir: Path = DEFAULT_PROFILE_DIR, headless: bool = False):
        self.profile_dir = Path(profile_dir)
        self.headless = headless
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def start(self) -> None:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            str(self.profile_dir), headless=self.headless
        )
        self._page = self._context.new_page()
        self._page.goto(WHATSAPP_WEB_URL)
        # If this is the first run, the user must scan the QR code manually.
        self._page.wait_for_selector("div[role='textbox']", timeout=LOGIN_TIMEOUT_MS)

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()

    def open_chat(self, phone: str) -> ChatResult:
        assert self._page is not None, "call start() first"
        self._page.goto(f"{WHATSAPP_WEB_URL}/send?phone={phone}")
        try:
            self._page.wait_for_selector(
                f"{CHAT_PANEL_SELECTOR}, {INVALID_PHONE_SELECTOR}", timeout=CHAT_LOAD_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            return ChatResult(found=False, displayed_name=None, error="timed out opening chat")

        if self._page.locator(INVALID_PHONE_SELECTOR).count() > 0:
            return ChatResult(found=False, displayed_name=None, error="invalid or unregistered phone number")

        displayed_name = None
        header_locator = self._page.locator(CHAT_HEADER_TITLE_SELECTOR).first
        if header_locator.count() > 0:
            displayed_name = header_locator.inner_text().strip() or None

        return ChatResult(found=True, displayed_name=displayed_name)

    def type_message(self, text: str) -> None:
        assert self._page is not None, "call start() first"
        box = self._page.locator(MESSAGE_BOX_SELECTOR).first
        box.click()
        for line in text.split("\n"):
            box.type(line)
            box.press("Shift+Enter")
        box.press("Backspace")  # remove the trailing extra newline from the loop above

    def send_message(self) -> bool:
        assert self._page is not None, "call start() first"
        before = self._page.locator(LAST_MESSAGE_OUT_SELECTOR).count()
        self._page.locator(SEND_BUTTON_SELECTOR).first.click()
        try:
            self._page.wait_for_function(
                f"document.querySelectorAll('{LAST_MESSAGE_OUT_SELECTOR}').length > {before}",
                timeout=CHAT_LOAD_TIMEOUT_MS,
            )
            return True
        except PlaywrightTimeoutError:
            return False
