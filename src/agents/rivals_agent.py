import logging
from typing import List, Dict, Any
from src.agents.base_agent import BaseTransferPortalAgent
from src.config.settings import RIVALS_TOP_PLAYERS_URL

logger = logging.getLogger(__name__)

class RivalsTransferPortalAgent(BaseTransferPortalAgent):
    def __init__(self):
        super().__init__()
        self.url = RIVALS_TOP_PLAYERS_URL

    async def scrape_players(self) -> List[Dict[str, Any]]:
        """Scrape player data from Rivals."""
        logger.info("Starting Rivals scraping...")
        browser, page = await self._setup_browser()
        
        try:
            logger.info(f"Navigating to {self.url}")
            response = await page.goto(self.url, wait_until="networkidle", timeout=self.scraping_timeout * 1000)
            if not response.ok:
                raise Exception(f"Failed to load Rivals page: {response.status} {response.status_text}")
            
            # Wait for the player table to load
            logger.info("Waiting for Rivals player table to load...")
            try:
                await page.wait_for_selector("table.transfer-tracker-table", timeout=self.selector_timeout)
            except Exception as e:
                logger.warning(f"Rivals selector wait failed: {str(e)}")
                raise Exception("No Rivals player table found")
            
            await self._take_debug_screenshot(page, "rivals")
            
            # Extract player data
            players = await page.query_selector_all("tr.transfer-tracker-row")
            if not players:
                raise Exception("No Rivals players found")
            
            player_data = []
            for idx, player in enumerate(players, 1):
                try:
                    # Extract data using the Rivals structure
                    rank = await player.query_selector("td.rank")
                    name = await player.query_selector("td.athlete")
                    position = await player.query_selector("td.pos")
                    origin = await player.query_selector("td.origin")
                    status = await player.query_selector("td.status")
                    
                    # Get text content safely
                    rank_text = await rank.text_content() if rank else "N/A"
                    name_text = await name.text_content() if name else "N/A"
                    position_text = await position.text_content() if position else "N/A"
                    origin_text = await origin.text_content() if origin else "N/A"
                    status_text = await status.text_content() if status else "N/A"
                    
                    # Get player profile URL
                    profile_url = None
                    name_link = await player.query_selector("a[href*='content/athletes']")
                    if name_link:
                        profile_url = await name_link.get_attribute("href")
                        if profile_url and not profile_url.startswith("http"):
                            profile_url = f"https://n.rivals.com{profile_url}"
                    
                    # Parse status to get last team and new team
                    last_team = origin_text.strip()
                    new_team = None
                    if "TRANSFERRED TO" in status_text:
                        new_team = status_text.replace("TRANSFERRED TO", "").strip()
                    
                    # Create player info dictionary
                    player_info = {
                        "source": "rivals",
                        "rank": self._parse_rank(rank_text, name_text),
                        "name": name_text.strip(),
                        "position": position_text.strip(),
                        "last_team": last_team,
                        "new_team": new_team,
                        "status": status_text.strip(),
                        "profile_url": profile_url
                    }
                    
                    player_data.append(player_info)
                    
                except Exception as e:
                    logger.error(f"Error processing Rivals player {idx}: {str(e)}")
                    continue
            
            return player_data
            
        finally:
            await browser.close() 