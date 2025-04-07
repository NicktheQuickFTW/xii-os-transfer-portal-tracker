import logging
from typing import List, Dict, Any
from src.agents.base_agent import BaseTransferPortalAgent
from src.config.settings import ON3_TOP_PLAYERS_URL

logger = logging.getLogger(__name__)

class On3TransferPortalAgent(BaseTransferPortalAgent):
    def __init__(self):
        super().__init__()
        self.url = ON3_TOP_PLAYERS_URL

    async def scrape_players(self) -> List[Dict[str, Any]]:
        """Scrape player data from On3."""
        logger.info("Starting On3 scraping...")
        browser, page = await self._setup_browser()
        
        try:
            logger.info(f"Navigating to {self.url}")
            response = await page.goto(self.url, wait_until="networkidle", timeout=self.scraping_timeout * 1000)
            if not response.ok:
                raise Exception(f"Failed to load On3 page: {response.status} {response.status_text}")
            
            # Wait for the player table to load
            logger.info("Waiting for On3 player table to load...")
            table_found = False
            for selector in [
                "table.transfer-portal-table",
                "table.player-table",
                "div.transfer-portal-list"
            ]:
                try:
                    await page.wait_for_selector(selector, timeout=self.selector_timeout)
                    table_found = True
                    break
                except Exception as e:
                    logger.warning(f"On3 selector {selector} not found: {str(e)}")
                    continue
            
            if not table_found:
                raise Exception("No On3 table found with any selector")
            
            await self._take_debug_screenshot(page, "on3")
            
            # Extract player data
            players = []
            for selector in [
                "tr.transfer-portal-row",
                "tr.player-row",
                "div.transfer-portal-item",
                "div.player-card"
            ]:
                players = await page.query_selector_all(selector)
                if players:
                    break
            
            if not players:
                raise Exception("No On3 player rows found")
            
            player_data = []
            for idx, player in enumerate(players, 1):
                try:
                    # Extract data using the exact column structure
                    rank = await player.query_selector("td.rank, div.rank")
                    name = await player.query_selector("td.player-name, div.player-name")
                    position = await player.query_selector("td.position, div.position")
                    rating = await player.query_selector("td.rating, div.rating")
                    nil_value = await player.query_selector("td.nil-value, div.nil-value")
                    status = await player.query_selector("td.status, div.status")
                    last_team = await player.query_selector("td.last-team, div.last-team")
                    new_team = await player.query_selector("td.new-team, div.new-team")
                    
                    # Get text content safely
                    rank_text = await rank.text_content() if rank else "N/A"
                    name_text = await name.text_content() if name else "N/A"
                    position_text = await position.text_content() if position else "N/A"
                    rating_text = await rating.text_content() if rating else "N/A"
                    nil_text = await nil_value.text_content() if nil_value else "N/A"
                    status_text = await status.text_content() if status else "N/A"
                    last_team_text = await last_team.text_content() if last_team else "N/A"
                    new_team_text = await new_team.text_content() if new_team else "N/A"
                    
                    # Get player profile URL
                    profile_url = None
                    name_link = await player.query_selector("a.player-link, a[href*='transfer-portal']")
                    if name_link:
                        profile_url = await name_link.get_attribute("href")
                        if profile_url and not profile_url.startswith("http"):
                            profile_url = f"https://www.on3.com{profile_url}"
                    
                    # Create player info dictionary
                    player_info = {
                        "source": "on3",
                        "rank": self._parse_rank(rank_text, name_text),
                        "name": name_text.strip(),
                        "position": position_text.strip(),
                        "rating": self._parse_numeric_value(rating_text, "rating", name_text),
                        "nil_value": self._parse_numeric_value(nil_text, "NIL value", name_text),
                        "status": status_text.strip(),
                        "last_team": last_team_text.strip(),
                        "new_team": new_team_text.strip(),
                        "profile_url": profile_url
                    }
                    
                    player_data.append(player_info)
                    
                except Exception as e:
                    logger.error(f"Error processing On3 player {idx}: {str(e)}")
                    continue
            
            return player_data
            
        finally:
            await browser.close() 