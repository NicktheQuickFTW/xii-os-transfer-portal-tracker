import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.config.settings import (
    CACHE_EXPIRY,
    LOG_LEVEL,
    LOG_FORMAT,
    USE_247SPORTS,
    USE_ON3,
    USE_RIVALS
)
from src.agents.on3_agent import On3TransferPortalAgent
from src.agents.sports247_agent import Sports247TransferPortalAgent
from src.agents.rivals_agent import RivalsTransferPortalAgent

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Basketball Transfer Portal Tracker Agent")

# Cache for storing player data
player_cache = {
    "data": [],
    "last_updated": 0
}

class PlayerStats(BaseModel):
    ppg: Optional[float] = None
    rpg: Optional[float] = None
    apg: Optional[float] = None
    spg: Optional[float] = None
    bpg: Optional[float] = None
    fg_pct: Optional[float] = None
    three_pt_pct: Optional[float] = None
    ft_pct: Optional[float] = None

class Player(BaseModel):
    name: str
    position: str
    height: Optional[str] = None
    previous_school: str
    class_year: Optional[str] = None
    eligibility: Optional[str] = None
    transfer_date: Optional[datetime] = None
    status: str
    destination_school: Optional[str] = None
    stats: Optional[PlayerStats] = None
    ranking: Optional[float] = None
    profile_url: Optional[str] = None
    nil_valuation: Optional[float] = None

class TransferPortalTrackerAgent:
    def __init__(self):
        self.cache_expiry = CACHE_EXPIRY
        self.on3_agent = On3TransferPortalAgent()
        self.sports247_agent = Sports247TransferPortalAgent()
        self.rivals_agent = RivalsTransferPortalAgent()
        self.data = []
        self.last_refresh = None

    async def refresh_data(self):
        """Refresh the player data from the transfer portal tracker."""
        try:
            current_time = time.time()
            if current_time - player_cache["last_updated"] < self.cache_expiry:
                logger.info("Using cached data")
                return player_cache["data"]

            all_players = []
            
            if USE_ON3:
                try:
                    on3_players = await self.on3_agent.scrape_players()
                    all_players.extend(on3_players)
                except Exception as e:
                    logger.error(f"Error scraping On3: {str(e)}")
            
            if USE_247SPORTS:
                try:
                    sports247_players = await self.sports247_agent.scrape_players()
                    all_players.extend(sports247_players)
                except Exception as e:
                    logger.error(f"Error scraping 247Sports: {str(e)}")
            
            if USE_RIVALS:
                try:
                    rivals_players = await self.rivals_agent.scrape_players()
                    all_players.extend(rivals_players)
                except Exception as e:
                    logger.error(f"Error scraping Rivals: {str(e)}")
            
            if not all_players:
                raise HTTPException(status_code=500, detail="Failed to refresh transfer portal data from any source")
            
            # Update cache
            player_cache["data"] = all_players
            player_cache["last_updated"] = current_time
            
            logger.info(f"Successfully refreshed data for {len(all_players)} players")
            return all_players
        except Exception as e:
            logger.error(f"Failed to refresh data: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to refresh transfer portal tracker data from any source"
            )

    def _parse_stats(self, stats_text: str) -> Optional[Dict[str, float]]:
        """Parse player statistics from text."""
        try:
            stats = {}
            parts = stats_text.split("|")
            for part in parts:
                part = part.strip()
                if "PPG" in part:
                    stats["ppg"] = float(part.replace("PPG", "").strip())
                elif "RPG" in part:
                    stats["rpg"] = float(part.replace("RPG", "").strip())
                elif "APG" in part:
                    stats["apg"] = float(part.replace("APG", "").strip())
                elif "SPG" in part:
                    stats["spg"] = float(part.replace("SPG", "").strip())
                elif "BPG" in part:
                    stats["bpg"] = float(part.replace("BPG", "").strip())
                elif "FG" in part:
                    stats["fg_pct"] = float(part.replace("% FG", "").strip())
                elif "3PT" in part:
                    stats["three_pt_pct"] = float(part.replace("% 3PT", "").strip())
                elif "FT" in part:
                    stats["ft_pct"] = float(part.replace("% FT", "").strip())
            return stats if stats else None
        except Exception as e:
            logger.error(f"Error parsing stats: {str(e)}")
            return None

    async def get_players(self) -> List[Player]:
        """Get all transfer portal tracker players."""
        if not self.data:
            await self.refresh_data()
        return [Player(**player) for player in self.data]

    async def search_players(
        self,
        position: Optional[str] = None,
        min_ppg: Optional[float] = None,
        school: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = 20,
        **kwargs
    ) -> List[Player]:
        """Search players by various criteria."""
        data = await self.refresh_data()
        filtered_players = data
        
        if position:
            filtered_players = [p for p in filtered_players if position.lower() in p["position"].lower()]
        if min_ppg is not None:
            filtered_players = [
                p for p in filtered_players 
                if p.get("stats", {}).get("ppg", 0) >= min_ppg
            ]
        if school:
            filtered_players = [
                p for p in filtered_players 
                if school.lower() in p["previous_school"].lower() or
                   (p.get("destination_school") and school.lower() in p["destination_school"].lower())
            ]
        if status:
            filtered_players = [
                p for p in filtered_players 
                if status.lower() in p["status"].lower()
            ]
        
        if limit:
            filtered_players = filtered_players[:limit]
            
        return [Player(**player) for player in filtered_players]

# Initialize the agent
agent = TransferPortalTrackerAgent()

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Basketball Transfer Portal Tracker Agent on port 3000...")
    await agent.refresh_data()

# API endpoints
@app.get("/players", response_model=List[Player])
async def get_players():
    """Get all transfer portal tracker players."""
    logger.info("Received request for all players")
    try:
        players = await agent.get_players()
        logger.info(f"Successfully retrieved {len(players)} players")
        return players
    except Exception as e:
        logger.error(f"Error getting players: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/players/refresh")
async def refresh_data():
    """Force a refresh of the transfer portal data."""
    logger.info("Received request to refresh data")
    try:
        await agent.refresh_data()
        logger.info("Successfully refreshed data")
        return {"status": "success", "message": "Data refreshed successfully"}
    except Exception as e:
        logger.error(f"Error refreshing data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/players/search", response_model=List[Player])
async def search_players(
    position: Optional[str] = None,
    min_ppg: Optional[float] = None,
    school: Optional[str] = None,
    status: Optional[str] = None,
    limit: Optional[int] = 20
):
    """Search players by various criteria."""
    logger.info(f"Received search request with filters: position={position}, min_ppg={min_ppg}, school={school}, status={status}, limit={limit}")
    try:
        players = await agent.search_players(
            position=position,
            min_ppg=min_ppg,
            school=school,
            status=status,
            limit=limit
        )
        logger.info(f"Successfully found {len(players)} players matching criteria")
        return players
    except Exception as e:
        logger.error(f"Error searching players: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="127.0.0.1", port=3000, log_level="debug")
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise 