from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

DEFAULT_PROFILE_DIR = Path("browser_profile")
WHATSAPP_WEB_URL = "https://web.whatsapp.com"
QR_SCAN_TIMEOUT_MS = 180_000
CHAT_LOAD_TIMEOUT_MS = 30_000

QR_CODE_SELECTOR = "canvas"
LOGGED_IN_SELECTOR = "#pane-side"
CHAT_PANEL_SELECTOR = "#main"
MENU_BUTTON_LABEL = re.compile(r"^(Menu|Mais opções)$")
LOGOUT_MENU_ITEM_TEXT = re.compile(r"^(Log out|Sair)$")
NEW_CHAT_BUTTON_LABEL = re.compile(r"New chat|Nova conversa")
SEARCH_PLACEHOLDER = re.compile(r"Search name, number or|Pesquisar nome, número ou|Pesquisar ou começar")
SEARCH_RESULT_ITEM_SELECTOR = "div[data-testid='cell-frame-container']"
MESSAGE_BOX_SELECTOR = "#main footer div[contenteditable='true']"
SEND_BUTTON_SELECTOR = "#main footer button[aria-label='Enviar'], #main footer button[aria-label='Send']"
ATTACH_BUTTON_SELECTOR = "#main footer button[aria-label='Anexar'], #main footer button[aria-label='Attach']"
ATTACH_DOCUMENT_OPTION_TEXT = re.compile(r"^(Document|Documento)$")
ATTACH_PHOTOS_OPTION_TEXT = re.compile(r"^(Photos & videos|Fotos e vídeos)$")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}
SEND_ATTACHMENTS_BUTTON_LABEL_PATTERN = re.compile(r"^(Send \d+ selected|Enviar \d+ (item|itens) selecionados?)$")
CHAT_HEADER_TITLE_SELECTOR = "header span[dir='auto']"
CONTACT_INFO_BUTTON_SELECTOR = "button[data-testid='conversation-info-header-button']"
DRAWER_SELECTOR = "div[data-testid='drawer-right']"
PHONE_NUMBER_PATTERN = re.compile(r"\+[\d\s-]{8,}")
# Outgoing message status ticks use stable internal icon names in their SVG
# <title>, unlike the localized aria-label text ("Sent"/"Enviada", etc.).
SENT_TICK_SELECTOR = (
    "#main title:text-is('wds-ic-check'), "
    "#main title:text-is('wds-ic-double-check'), "
    "#main title:text-is('wds-ic-read')"
)


@dataclass
class ChatResult:
    found: bool
    displayed_name: str | None
    displayed_phone: str | None = None
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
        self._wait_for_login()

    def _wait_for_login(self) -> None:
        assert self._page is not None
        self._page.wait_for_selector(
            f"{QR_CODE_SELECTOR}, {LOGGED_IN_SELECTOR}", timeout=QR_SCAN_TIMEOUT_MS
        )
        if self._page.locator(LOGGED_IN_SELECTOR).count() > 0:
            return
        # QR code is showing: the user must scan it manually with their phone.
        print("Escaneie o QR code com o WhatsApp do celular para continuar...")
        self._page.wait_for_selector(LOGGED_IN_SELECTOR, timeout=QR_SCAN_TIMEOUT_MS)

    def logout(self) -> bool:
        """Log out of the linked WhatsApp account via the app menu.

        Lets the next run link a different phone number (new QR scan)
        without manually clearing browser_profile/.
        """
        assert self._page is not None, "call start() first"
        try:
            self._page.get_by_label(MENU_BUTTON_LABEL).first.click()
            self._page.get_by_text(LOGOUT_MENU_ITEM_TEXT).click()
            self._page.get_by_role("button", name=LOGOUT_MENU_ITEM_TEXT).click()
            self._page.wait_for_selector(QR_CODE_SELECTOR, timeout=CHAT_LOAD_TIMEOUT_MS)
            return True
        except PlaywrightError:
            # Covers both a timed-out UI step and the page/context already
            # having crashed or closed (e.g. after an earlier navigation
            # error) — either way, logout cannot be confirmed.
            return False

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        except PlaywrightError:
            pass
        if self._playwright is not None:
            self._playwright.stop()

    def open_chat(self, phone: str) -> ChatResult:
        """Open a chat by phone number via the "New chat" search panel.

        WhatsApp Web's /send?phone= deep link hangs indefinitely for
        automated (Playwright-controlled) browsers, so the chat is found the
        same way a human would: through the in-app contact search.
        """
        assert self._page is not None, "call start() first"
        try:
            self._page.get_by_label(NEW_CHAT_BUTTON_LABEL).first.click()
            search = self._page.get_by_placeholder(SEARCH_PLACEHOLDER).first
            search.click()
            search.type(phone)
            self._page.wait_for_timeout(1500)

            results = self._page.locator(SEARCH_RESULT_ITEM_SELECTOR)
            if results.count() == 0:
                self._page.keyboard.press("Escape")
                return ChatResult(found=False, displayed_name=None, error="invalid or unregistered phone number")

            results.first.click()
            self._page.wait_for_selector(CHAT_PANEL_SELECTOR, timeout=CHAT_LOAD_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            return ChatResult(found=False, displayed_name=None, error="timed out opening chat")

        displayed_name = None
        header_locator = self._page.locator(CHAT_HEADER_TITLE_SELECTOR).first
        if header_locator.count() > 0:
            displayed_name = header_locator.inner_text().strip() or None

        displayed_phone = self._read_contact_phone()

        return ChatResult(found=True, displayed_name=displayed_name, displayed_phone=displayed_phone)

    def _read_contact_phone(self) -> str | None:
        """Open the contact info drawer and extract the phone number it shows.

        This is the authoritative, deterministic check that the opened chat
        really belongs to the expected phone number (search results can match
        by name too, not just number).
        """
        assert self._page is not None
        try:
            self._page.locator(CONTACT_INFO_BUTTON_SELECTOR).click(timeout=CHAT_LOAD_TIMEOUT_MS)
            drawer = self._page.locator(DRAWER_SELECTOR)
            drawer.wait_for(state="visible", timeout=CHAT_LOAD_TIMEOUT_MS)
            texts = drawer.locator("span[dir='auto']").all_inner_texts()
            phone = None
            for text in texts:
                match = PHONE_NUMBER_PATTERN.search(text)
                if match:
                    phone = re.sub(r"\D", "", match.group())
                    break
            self._page.keyboard.press("Escape")
            return phone
        except PlaywrightTimeoutError:
            return None

    def type_message(self, text: str) -> None:
        assert self._page is not None, "call start() first"
        box = self._page.locator(MESSAGE_BOX_SELECTOR).first
        box.click()
        for line in text.split("\n"):
            box.type(line)
            box.press("Shift+Enter")
        box.press("Backspace")  # remove the trailing extra newline from the loop above

    def send_attachments(self, paths: list[Path]) -> bool:
        """Send attachments, grouped by type so each uses the right WhatsApp option.

        Images go through "Photos & videos" so they render as inline image
        bubbles (with preview/editing), like a human sending a photo. Everything
        else goes through "Document", which sends the file as-is without
        WhatsApp's image re-compression.
        """
        images = [p for p in paths if p.suffix.lower() in IMAGE_EXTENSIONS]
        documents = [p for p in paths if p.suffix.lower() not in IMAGE_EXTENSIONS]

        for group, option_text in ((images, ATTACH_PHOTOS_OPTION_TEXT), (documents, ATTACH_DOCUMENT_OPTION_TEXT)):
            if group and not self._send_attachment_group(group, option_text):
                return False
        return True

    def _send_attachment_group(self, paths: list[Path], option_text: str) -> bool:
        assert self._page is not None, "call start() first"
        before = self._page.locator(SENT_TICK_SELECTOR).count()

        self._page.locator(ATTACH_BUTTON_SELECTOR).first.click()
        with self._page.expect_file_chooser() as chooser_info:
            self._page.get_by_text(option_text).click()
        chooser_info.value.set_files([str(p) for p in paths])

        send_button = self._page.get_by_label(SEND_ATTACHMENTS_BUTTON_LABEL_PATTERN)
        try:
            send_button.click(timeout=CHAT_LOAD_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            return False

        deadline = time.monotonic() + (CHAT_LOAD_TIMEOUT_MS / 1000)
        while time.monotonic() < deadline:
            if self._page.locator(SENT_TICK_SELECTOR).count() > before:
                return True
            self._page.wait_for_timeout(300)
        return False

    def send_message(self) -> bool:
        """Click send and poll for a new outgoing bubble.

        WhatsApp Web's CSP blocks 'unsafe-eval', so Playwright's
        wait_for_function (which injects a JS string) cannot be used here;
        polling via locator.count() goes through Playwright's own protocol
        instead of page-side eval.
        """
        assert self._page is not None, "call start() first"
        before = self._page.locator(SENT_TICK_SELECTOR).count()
        self._page.locator(SEND_BUTTON_SELECTOR).first.click()

        deadline = time.monotonic() + (CHAT_LOAD_TIMEOUT_MS / 1000)
        while time.monotonic() < deadline:
            if self._page.locator(SENT_TICK_SELECTOR).count() > before:
                return True
            self._page.wait_for_timeout(300)
        return False
