import os
import shutil
import logging
from typing import Optional
from pathlib import Path
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page, Browser
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

    async def start(self) -> BrowserContext:
        if self._is_running and self._context:
            return self._context

        os.makedirs(self.profile_dir, exist_ok=True)
        try:
            self._playwright = await async_playwright().start()

            # Determine whether to launch Edge or fallback to Chromium
            launch_kwargs = {
                "user_data_dir": str(self.profile_dir),
                "headless": self.headless,
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
                ),
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
                "viewport": {"width": 1280, "height": 800},
            }

            edge_path = self.find_edge_path()
            if self.browser_channel == "msedge" and edge_path:
                launch_kwargs["channel"] = "msedge"
                logger.info(f"Launching Microsoft Edge browser via channel 'msedge' ({edge_path})")
            else:
                logger.info("Launching standard Chromium browser context")

            self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
            self._is_running = True
            logger.info("Persistent browser context started successfully.")
            return self._context
        except Exception as e:
            logger.error(f"Failed to start Playwright browser: {e}")
            self._is_running = False
            raise

    async def new_page(self) -> Page:
        context = await self.start()
        return await context.new_page()

    async def close(self) -> None:
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self._is_running = False
            logger.info("Browser stopped cleanly.")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")


browser_manager = BrowserManager()
