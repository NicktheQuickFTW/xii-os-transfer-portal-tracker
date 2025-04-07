"""
FastAPI Transfer Portal Orchestrator

A simplified version of the orchestrator that focuses on core functionality.
"""
import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from src.agents.on3_agent import On3TransferPortalAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Transfer Portal API")

# Global cache for player data
player_cache = {
    "data": [],
    "last_updated": None
}


class TransferPortalStats(BaseModel):
    """Statistics for the transfer portal data"""
    player_count: int = 0
    last_updated: Optional[datetime] = None
    agent_status: str = "idle"


# Create global agent instance
portal_agent = On3TransferPortalAgent()


async def refresh_data():
    """Background task to refresh the transfer portal data"""
    logger.info("Starting data refresh task")
    try:
        # Update status
        portal_stats.agent_status = "running"
        
        # Scrape players
        start_time = time.time()
        players = await portal_agent.scrape_players()
        end_time = time.time()
        
        # Update cache
        player_cache["data"] = players
        player_cache["last_updated"] = datetime.now()
        
        # Update stats
        portal_stats.player_count = len(players)
        portal_stats.last_updated = datetime.now()
        portal_stats.agent_status = "ready"
        
        logger.info(f"Data refresh complete. Found {len(players)} players in {end_time - start_time:.2f} seconds")
        
    except Exception as e:
        portal_stats.agent_status = "error"
        logger.error(f"Error refreshing data: {str(e)}")


# Initialize statistics
portal_stats = TransferPortalStats()


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Transfer Portal API",
        "time": datetime.now().isoformat(),
        "agent_status": portal_stats.agent_status
    }


@app.get("/stats")
async def stats():
    """Get transfer portal statistics"""
    return portal_stats


@app.get("/players")
async def get_players(
    limit: int = 20,
    position: Optional[str] = None,
    school: Optional[str] = None
):
    """Get players from the transfer portal with optional filtering"""
    # If no data, return empty list
    if not player_cache["data"]:
        return {"players": []}
    
    # Get data from cache
    players = player_cache["data"]
    
    # Apply filters
    if position:
        players = [p for p in players if position.lower() in p.get("position", "").lower()]
    
    if school:
        players = [
            p for p in players 
            if (school.lower() in p.get("previous_school", "").lower() or 
                school.lower() in p.get("destination_school", "").lower())
        ]
    
    # Apply limit
    players = players[:limit]
    
    return {
        "count": len(players),
        "total": len(player_cache["data"]),
        "last_updated": player_cache["last_updated"],
        "players": players
    }


@app.post("/refresh")
async def trigger_refresh(background_tasks: BackgroundTasks):
    """Trigger a manual refresh of the transfer portal data"""
    if portal_stats.agent_status == "running":
        return {"status": "already_running"}
    
    background_tasks.add_task(refresh_data)
    return {"status": "refresh_started"}


@app.on_event("startup")
async def startup_event():
    """Initialize the orchestrator when the API starts"""
    logger.info("Starting Transfer Portal API")
    # Trigger initial data refresh in the background
    asyncio.create_task(refresh_data())


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Transfer Portal API on port 9000...")
    try:
        uvicorn.run(
            "src.agents.fastapi_orchestrator:app", 
            host="0.0.0.0", 
            port=9000, 
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise 