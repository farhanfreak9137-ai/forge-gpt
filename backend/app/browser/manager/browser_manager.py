import os
import time
import shutil
import logging
import subprocess
import urllib.request
from typing import Optional, List, Dict, Any
from pathlib import Path
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page
from app.config.settings import settings

logger = logging.getLogger("forgeagent.browser.manager")


class BrowserManager:
    """Manages persistent Playwright browser profile, tabs, Edge/Chromium channels, and connection recovery."""

    def __init__(
        self,
        profile_dir: Optional[Path] = None,
        headless: Optional[bool] = None,
        browser_channel: str = "msedge",
    ):
        self.profile_dir = profile_dir or settings.browser_profile_dir
        self.headless = settings.browser_headless if headless is None else headless
        self.browser_channel = browser_channel
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._is_running = False

    def find_edge_path(self) -> Optional[str]:
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            shutil.which("msedge"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return None

    def focus_edge_window(self) -> None:
        """Brings the Microsoft Edge / ChatGPT window to the front of Windows desktop."""
        try:
            ps_script = (
                '$w = New-Object -ComObject WScript.Shell; '
                'if (-not $w.AppActivate("ChatGPT")) { $w.AppActivate("Edge") }'
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                timeout=3,
                capture_output=True,
            )
        except Exception:
            pass

    def ensure_edge_running(self) -> bool:
        """Verifies if Edge CDP is running; if not, launches visible Edge desktop process."""
        try:
            with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1):
                self.focus_edge_window()
                return True
        except Exception:
            pass

        edge_path = self.find_edge_path() or "msedge"
        profile_dir = self.profile_dir
        os.makedirs(profile_dir, exist_ok=True)
        cmd = [
            edge_path,
            "--remote-debugging-port=9222",
            f"--user-data-dir={profile_dir}",
            "--start-maximized",
            "--new-window",
            "https://chatgpt.com",
        ]
        try:
            logger.info(f"Launching visible Microsoft Edge on desktop: {cmd}")
            subprocess.Popen(cmd)
            for _ in range(20):
                time.sleep(0.5)
                try:
                    with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1):
                        logger.info("Microsoft Edge CDP port 9222 is active.")
                        self.focus_edge_window()
                        return True
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to launch Microsoft Edge desktop process: {e}")
        return False

    def _reset_state(self):
        """Force-reset internal browser state so next start() creates a fresh context."""
        self._context = None
        self._playwright = None
        self._is_running = False

    async def _is_context_alive(self) -> bool:
        """Return True only if self._context is still usable (has at least one accessible page)."""
        if not self._context:
            return False
        try:
            # Accessing .pages on a closed context raises an error
            _ = self._context.pages
            return True
        except Exception:
            return False

    async def start(self) -> BrowserContext:
        # If we think we're running, verify the context is still actually alive
        if self._is_running and self._context:
            if not await self._is_context_alive():
                logger.warning("Detected stale browser context; resetting and reconnecting.")
                self._reset_state()
            else:
                return self._context

        os.makedirs(self.profile_dir, exist_ok=True)
        self.ensure_edge_running()

        try:
            if not self._playwright:
                self._playwright = await async_playwright().start()

            # 1. First, connect over CDP to visible Edge
            try:
                cdp_browser = await self._playwright.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=5000)
                if cdp_browser.contexts:
                    self._context = cdp_browser.contexts[0]
                else:
                    self._context = await cdp_browser.new_context()
                self._is_running = True
                self.focus_edge_window()
                logger.info("Connected to visible Microsoft Edge via CDP port 9222.")
                return self._context
            except Exception as cdp_err:
                logger.warning(f"CDP connect failed, launching persistent context fallback: {cdp_err}")

            # 2. Launch persistent Edge context fallback
            launch_kwargs = {
                "user_data_dir": str(self.profile_dir),
                "headless": False,
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
                ),
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--start-maximized",
                    "--new-window",
                ],
                "viewport": None,
            }

            edge_path = self.find_edge_path()
            if self.browser_channel == "msedge" and edge_path:
                launch_kwargs["channel"] = "msedge"

            self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
            self._is_running = True
            self.focus_edge_window()
            logger.info("Persistent browser context started successfully.")
            return self._context
        except Exception as e:
            logger.error(f"Failed to start Playwright browser: {e}")
            self._reset_state()
            raise

    async def get_page(self) -> Page:
        """Retrieve a usable Page for ChatGPT interaction.
        Automatically restarts the browser if the context or page is found to be dead.
        """
        for attempt in range(2):  # try twice: once normally, once after a forced restart
            try:
                context = await self.start()
                self.focus_edge_window()
                # Prefer an existing ChatGPT page
                for p in context.pages:
                    if "chatgpt.com" in p.url:
                        await p.bring_to_front()
                        return p
                # Fall back to any existing page
                if context.pages:
                    p = context.pages[0]
                    await p.bring_to_front()
                    return p
                # No pages open — create one
                new_page = await context.new_page()
                await new_page.bring_to_front()
                return new_page
            except Exception as exc:
                if attempt == 0:
                    logger.warning(f"get_page() failed on attempt {attempt + 1} ({exc}); forcing browser restart.")
                    self._reset_state()
                    # Make sure CDP port is also reset so ensure_edge_running re-launches Edge
                    continue
                else:
                    logger.error(f"get_page() failed after browser restart: {exc}")
                    raise

    async def new_page(self) -> Page:
        return await self.get_page()

    async def navigate_to_chat(self, url: str) -> Page:
        """Navigates Edge to a specific ChatGPT conversation or new chat and brings it forward."""
        page = await self.get_page()
        self.focus_edge_window()
        await page.bring_to_front()
        if page.url != url:
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(1000)
        return page

    async def get_chatgpt_conversations(self) -> List[Dict[str, str]]:
        """Scrapes ChatGPT's sidebar conversation threads."""
        try:
            page = await self.get_page()
            if not page.url or "chatgpt.com" not in page.url:
                return []
            items = await page.evaluate("""() => {
                const list = [];
                const seen = new Set();
                document.querySelectorAll('a[href*="/c/"]').forEach(a => {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/\\/c\\/([a-zA-Z0-9-]+)/);
                    if (m) {
                        const id = m[1];
                        if (!seen.has(id)) {
                            seen.add(id);
                            const title = (a.innerText || '').trim().replace(/\\n+/g, ' ');
                            if (title) {
                                list.push({ id: id, title: title, href: href });
                            }
                        }
                    }
                });
                return list;
            }""")
            return items
        except Exception as e:
            logger.warning(f"Could not retrieve ChatGPT conversations from page: {e}")
            return []

    async def get_current_chat_messages(self) -> List[Dict[str, Any]]:
        """Extracts turn history from current ChatGPT page."""
        try:
            page = await self.get_page()
            turns = await page.evaluate("""() => {
                const results = [];
                const turnElements = document.querySelectorAll('[data-turn-key]');
                turnElements.forEach((t, idx) => {
                    let userText = '';
                    const userEl = t.querySelector('.whitespace-pre-wrap, [class*="user-bubble"], [data-message-author-role="user"]');
                    if (userEl) {
                        userText = userEl.innerText.trim();
                    } else {
                        const m = t.innerText.match(/You said:\\s*You([\\S\\s]*?)ChatGPT said:/);
                        if (m) userText = m[1].trim();
                    }
                    if (userText) {
                        results.push({
                            id: `u-${idx}`,
                            sender: 'user',
                            text: userText,
                            timestamp: new Date().toISOString()
                        });
                    }

                    let assistantText = '';
                    const assistantEl = t.querySelector('[class*="DilResponseRoot"], [class*="ResponseRoot"], [data-message-author-role="assistant"]');
                    if (assistantEl) {
                        assistantText = assistantEl.innerText.trim();
                    }
                    if (assistantText) {
                        results.push({
                            id: `a-${idx}`,
                            sender: 'assistant',
                            text: assistantText,
                            clean_message: assistantText,
                            timestamp: new Date().toISOString()
                        });
                    }
                });
                return results;
            }""")
            return turns
        except Exception as e:
            logger.warning(f"Could not extract messages from page: {e}")
            return []

    async def close(self) -> None:
        try:
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
        finally:
            self._reset_state()
            logger.info("Browser stopped cleanly.")


browser_manager = BrowserManager()
