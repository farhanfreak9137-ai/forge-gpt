import os
import logging
from typing import Optional
from pathlib import Path
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page, Browser
from app.config.settings import settings

logger = logging.getLogger("forgeagent.browser.manager")


class BrowserManager:
    """Manages persistent Playwright browser profile, tabs, and connection recovery."""

    def __init__(self, profile_dir: Optional[Path] = None, headless: bool = True):
        self.profile_dir = profile_dir or settings.browser_profile_dir
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._is_running = False

    async def start(self) -> BrowserContext:
        if self._is_running and self._context:
            return self._context

        os.makedirs(self.profile_dir, exist_ok=True)
        try:
            self._playwright = await async_playwright().start()
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
                viewport={"width": 1280, "height": 800},
            )
            self._is_running = True
            logger.info("Persistent Playwright Chromium context started successfully.")
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
            logger.info("Playwright browser stopped cleanly.")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")


browser_manager = BrowserManager()
