import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from playwright.async_api import async_playwright, Browser, Page
from src.config.settings import (
    BROWSER_ARGS,
    VIEWPORT_WIDTH,
    VIEWPORT_HEIGHT,
    USER_AGENT,
    SCRAPING_TIMEOUT,
    WAIT_FOR_SELECTOR_TIMEOUT
)

logger = logging.getLogger(__name__)

class BaseTransferPortalAgent(ABC):
    def __init__(self):
        self.scraping_timeout = SCRAPING_TIMEOUT
        self.selector_timeout = WAIT_FOR_SELECTOR_TIMEOUT

    async def _setup_browser(self) -> tuple[Browser, Page]:
        """Set up browser and page with common configuration."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=BROWSER_ARGS
        )
        
        context = await browser.new_context(
            viewport={'width': VIEWPORT_WIDTH, 'height': VIEWPORT_HEIGHT},
            user_agent=USER_AGENT,
            ignore_https_errors=True
        )
        
        page = await context.new_page()
        await page.route("**/*", lambda route: route.continue_())
        
        return browser, page

    async def _take_debug_screenshot(self, page: Page, source: str):
        """Take a debug screenshot of the page."""
        try:
            await page.screenshot(path=f"debug-screenshot-{source}.png")
            logger.info(f"Debug screenshot saved for {source}")
        except Exception as e:
            logger.warning(f"Failed to save debug screenshot for {source}: {str(e)}")

    @abstractmethod
    async def scrape_players(self) -> List[Dict[str, Any]]:
        """Scrape player data from the source."""
        pass

    def _parse_numeric_value(self, text: str, field_name: str, player_name: str) -> float:
        """Parse numeric values from text with error handling."""
        try:
            if text and text != "N/A":
                return float(text.strip().replace("$", "").replace(",", ""))
            return 0.0
        except ValueError:
            logger.warning(f"Invalid {field_name} value for player {player_name}: {text}")
            return 0.0

    def _parse_rank(self, text: str, player_name: str) -> int:
        """Parse rank values from text with error handling."""
        try:
            if text and text != "N/A":
                return int(text.strip())
            return 0
        except ValueError:
            logger.warning(f"Invalid rank value for player {player_name}: {text}")
            return 0 