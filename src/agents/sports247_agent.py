import logging
from typing import List, Dict, Any
from src.agents.base_agent import BaseTransferPortalAgent
from src.config.settings import SPORTS247_TOP_PLAYERS_URL

logger = logging.getLogger(__name__)

class Sports247TransferPortalAgent(BaseTransferPortalAgent):
    def __init__(self):
        super().__init__()
        self.url = SPORTS247_TOP_PLAYERS_URL

    async def scrape_players(self) -> List[Dict[str, Any]]:
        """Scrape player data from 247Sports."""
        logger.info("Starting 247Sports scraping...")
        browser, page = await self._setup_browser()
        
        try:
            logger.info(f"Navigating to {self.url}")
            response = await page.goto(self.url, wait_until="networkidle", timeout=self.scraping_timeout * 1000)
            if not response.ok:
                raise Exception(f"Failed to load 247Sports page: {response.status} {response.status_text}")
            
            # Wait for the player list to load
            logger.info("Waiting for 247Sports player list to load...")
            try:
                await page.wait_for_selector("div.player-card", timeout=self.selector_timeout)
            except Exception as e:
                logger.warning(f"247Sports selector wait failed: {str(e)}")
                raise Exception("No 247Sports player cards found")
            
            await self._take_debug_screenshot(page, "247")
            
            # Extract player data
            players = await page.query_selector_all("div.player-card")
            if not players:
                raise Exception("No 247Sports players found")
            
            player_data = []
            for idx, player in enumerate(players, 1):
                try:
                    # Extract data using the 247Sports structure
                    rank = await player.query_selector("div.rank")
                    name = await player.query_selector("div.player-name")
                    position = await player.query_selector("div.position")
                    rating = await player.query_selector("div.rating")
                    status = await player.query_selector("div.status")
                    last_team = await player.query_selector("div.last-team")
                    new_team = await player.query_selector("div.new-team")
                    
                    # Get text content safely
                    rank_text = await rank.text_content() if rank else "N/A"
                    name_text = await name.text_content() if name else "N/A"
                    position_text = await position.text_content() if position else "N/A"
                    rating_text = await rating.text_content() if rating else "N/A"
                    status_text = await status.text_content() if status else "N/A"
                    last_team_text = await last_team.text_content() if last_team else "N/A"
                    new_team_text = await new_team.text_content() if new_team else "N/A"
                    
                    # Get player profile URL
                    profile_url = None
                    name_link = await player.query_selector("a.player-link")
                    if name_link:
                        profile_url = await name_link.get_attribute("href")
                        if profile_url and not profile_url.startswith("http"):
                            profile_url = f"https://247sports.com{profile_url}"
                    
                    # Create player info dictionary
                    player_info = {
                        "source": "247sports",
                        "rank": self._parse_rank(rank_text, name_text),
                        "name": name_text.strip(),
                        "position": position_text.strip(),
                        "rating": self._parse_numeric_value(rating_text, "rating", name_text),
                        "status": status_text.strip(),
                        "last_team": last_team_text.strip(),
                        "new_team": new_team_text.strip(),
                        "profile_url": profile_url
                    }
                    
                    player_data.append(player_info)
                    
                except Exception as e:
                    logger.error(f"Error processing 247Sports player {idx}: {str(e)}")
                    continue
            
            return player_data
            
        finally:
            await browser.close() 