"""
Transfer Portal Orchestrator Agent

This module implements the orchestrator component for managing multiple site-specific
transfer portal data collection agents and providing a unified interface.

Key responsibilities:
1. Coordinating the execution of site-specific agents
2. Monitoring agent health and performance
3. Consolidating and reconciling data from multiple sources
4. Providing a unified API interface
"""

import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Import site-specific agents
from src.agents.on3_agent import On3TransferPortalAgent
from src.agents.rivals_agent import RivalsTransferPortalAgent
from src.agents.sports247_agent import Sports247TransferPortalAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Basketball Transfer Portal Orchestrator")


class DataSource(str, Enum):
    """Enumeration of data sources"""
    ON3 = "on3"
    RIVALS = "rivals"
    TWO47 = "247sports"
    ALL = "all"


class AgentStatus(str, Enum):
    """Enumeration of agent statuses"""
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    INACTIVE = "inactive"


class PlayerStats(BaseModel):
    """Player statistics model"""
    ppg: Optional[float] = None
    rpg: Optional[float] = None
    apg: Optional[float] = None
    spg: Optional[float] = None
    bpg: Optional[float] = None
    fg_pct: Optional[float] = None
    three_pt_pct: Optional[float] = None
    ft_pct: Optional[float] = None
    games: Optional[int] = None
    source: Optional[DataSource] = None


class TransferPlayer(BaseModel):
    """Transfer player model with multi-source support"""
    player_id: str  # Unique identifier created by orchestrator
    name: str
    position: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[int] = None
    previous_school: Optional[str] = None
    class_year: Optional[str] = None
    eligibility: Optional[str] = None
    transfer_date: Optional[str] = None
    status: Optional[str] = None
    destination_school: Optional[str] = None
    stats: Dict[DataSource, PlayerStats] = Field(default_factory=dict)
    rankings: Dict[DataSource, int] = Field(default_factory=dict)
    composite_ranking: Optional[int] = None
    profile_urls: Dict[DataSource, str] = Field(default_factory=dict)
    nil_valuation: Dict[DataSource, str] = Field(default_factory=dict)
    sources: List[DataSource] = Field(default_factory=list)
    last_updated: Dict[DataSource, str] = Field(default_factory=dict)
    
    @property
    def best_stats(self) -> Optional[PlayerStats]:
        """Return the best available stats based on source priority"""
        for source in [DataSource.ON3, DataSource.TWO47, DataSource.RIVALS]:
            if source in self.stats:
                return self.stats[source]
        return None


class AgentMetrics(BaseModel):
    """Metrics for a single agent"""
    last_successful_refresh: Optional[str] = None
    last_refresh_attempt: Optional[str] = None
    refresh_count: int = 0
    error_count: int = 0
    player_count: int = 0
    average_refresh_time_ms: Optional[float] = None
    status: AgentStatus = AgentStatus.INACTIVE


class PortalQuery(BaseModel):
    """Query parameters for the transfer portal"""
    position: Optional[str] = None
    min_ppg: Optional[float] = None
    school: Optional[str] = None
    status: Optional[str] = None
    source: Optional[DataSource] = DataSource.ALL
    limit: Optional[int] = 20
    min_ranking: Optional[int] = None
    max_ranking: Optional[int] = None


class TransferPortalOrchestrator:
    """
    Orchestrator for managing multiple transfer portal data agents
    and providing a unified interface.
    """
    
    def __init__(self, refresh_interval: int = 3600):
        """Initialize the orchestrator"""
        self.refresh_interval = refresh_interval
        self.agents = {
            DataSource.ON3: On3TransferPortalAgent(),
            DataSource.RIVALS: RivalsTransferPortalAgent(),
            DataSource.TWO47: Sports247TransferPortalAgent()
        }
        
        # Initialize data_cache for each agent
        for agent in self.agents.values():
            if not hasattr(agent, 'data_cache'):
                agent.data_cache = []
        
        # Initialize metrics
        self.metrics = {
            source: AgentMetrics() for source in self.agents.keys()
        }
        
        # Consolidated player data
        self.players: Dict[str, TransferPlayer] = {}
        self.last_consolidation: Optional[float] = None
        
        # Background tasks
        self.refresh_tasks = {}
    
    async def start(self):
        """Start the orchestrator background tasks"""
        logger.info("Starting Transfer Portal Orchestrator")
        
        try:
            # Initialize data
            logger.info("Initializing data from all agents...")
            # Make the initial refresh optional to avoid startup issues
            try:
                await self.refresh_all_agents()
            except Exception as e:
                logger.error(f"Error during initial data refresh: {str(e)}")
                logger.info("Continuing with startup despite initial refresh failure")
            
            # Start background refresh tasks
            logger.info("Starting background refresh tasks...")
            for source in self.agents.keys():
                self.refresh_tasks[source] = asyncio.create_task(
                    self._schedule_refreshes(source)
                )
                logger.info(f"Started refresh task for {source}")
            
            logger.info("Orchestrator startup complete")
        except Exception as e:
            logger.error(f"Error during orchestrator startup: {str(e)}")
            raise
    
    async def stop(self):
        """Stop the orchestrator"""
        logger.info("Stopping Transfer Portal Orchestrator")
        
        # Cancel background tasks
        for task in self.refresh_tasks.values():
            task.cancel()
        
        # Await task cancellation
        await asyncio.gather(*self.refresh_tasks.values(), return_exceptions=True)
    
    async def _schedule_refreshes(self, source: DataSource):
        """Background task to schedule periodic refreshes for a source"""
        while True:
            try:
                # Calculate time to next refresh
                metrics = self.metrics[source]
                if metrics.last_successful_refresh:
                    last_refresh_time = datetime.fromisoformat(metrics.last_successful_refresh)
                    now = datetime.now()
                    elapsed = (now - last_refresh_time).total_seconds()
                    wait_time = max(0, self.refresh_interval - elapsed)
                else:
                    # If never refreshed, wait a short time (stagger initial refreshes)
                    source_index = list(self.agents.keys()).index(source)
                    wait_time = source_index * 10  # Stagger by 10 seconds per source
                
                # Wait until next refresh
                await asyncio.sleep(wait_time)
                
                # Refresh data
                await self.refresh_agent(source)
                
            except asyncio.CancelledError:
                logger.info(f"Refresh task for {source} cancelled")
                break
            except Exception as e:
                logger.error(f"Error in refresh task for {source}: {str(e)}")
                # Wait before retrying
                await asyncio.sleep(60)
    
    async def refresh_agent(self, source: DataSource) -> bool:
        """Refresh data from a specific agent"""
        agent = self.agents[source]
        metrics = self.metrics[source]
        
        try:
            # Update metrics
            metrics.status = AgentStatus.RUNNING
            metrics.last_refresh_attempt = datetime.now().isoformat()
            
            # Time the refresh operation
            start_time = time.time()
            
            # Perform the refresh
            data = await agent.scrape_players()
            
            # Update metrics
            end_time = time.time()
            refresh_time_ms = (end_time - start_time) * 1000
            
            if metrics.average_refresh_time_ms is None:
                metrics.average_refresh_time_ms = refresh_time_ms
            else:
                # Exponential moving average
                metrics.average_refresh_time_ms = (
                    0.8 * metrics.average_refresh_time_ms + 0.2 * refresh_time_ms
                )
            
            metrics.refresh_count += 1
            metrics.last_successful_refresh = datetime.now().isoformat()
            metrics.player_count = len(data) if data else 0
            metrics.status = AgentStatus.READY
            
            # Save agent data
            agent.data_cache = data
            
            # Consolidate data
            await self.consolidate_data()
            
            return True
            
        except Exception as e:
            # Update metrics
            metrics.error_count += 1
            metrics.status = AgentStatus.ERROR
            logger.error(f"Error refreshing {source}: {str(e)}")
            return False
    
    async def refresh_all_agents(self):
        """Refresh data from all agents"""
        refresh_tasks = [
            self.refresh_agent(source)
            for source in self.agents.keys()
        ]
        
        results = await asyncio.gather(*refresh_tasks, return_exceptions=True)
        
        # Check if at least one agent succeeded
        return any(isinstance(result, bool) and result for result in results)
    
    async def consolidate_data(self):
        """Consolidate data from all agents"""
        logger.info("Consolidating data from all sources")
        
        # Track existing players for cleanup
        existing_players = set(self.players.keys())
        processed_players = set()
        
        # Process each source
        for source, agent in self.agents.items():
            metrics = self.metrics[source]
            
            # Skip inactive or error agents
            if metrics.status not in [AgentStatus.READY, AgentStatus.RUNNING]:
                continue
            
            # Get data from agent cache
            try:
                data = agent.data_cache
                if not data:
                    continue
                
                for player_data in data:
                    # Generate a consistent player ID
                    player_id = self._generate_player_id(player_data["name"], player_data.get("previous_school"))
                    processed_players.add(player_id)
                    
                    # Create or update player record
                    if player_id not in self.players:
                        # Create new consolidated player record
                        player = TransferPlayer(
                            player_id=player_id,
                            name=player_data["name"],
                            sources=[source]
                        )
                        self.players[player_id] = player
                    else:
                        # Update existing player
                        player = self.players[player_id]
                        if source not in player.sources:
                            player.sources.append(source)
                    
                    # Update player details with data from this source
                    self._update_player_from_source(player, player_data, source)
            
            except Exception as e:
                logger.error(f"Error consolidating data from {source}: {str(e)}")
        
        # Remove players that no longer exist in any source
        for player_id in existing_players - processed_players:
            self.players.pop(player_id, None)
        
        # Update consolidation timestamp
        self.last_consolidation = time.time()
        
        logger.info(f"Data consolidation complete. {len(self.players)} players in consolidated database.")
    
    def _generate_player_id(self, name: str, school: Optional[str]) -> str:
        """Generate a consistent ID for a player"""
        # Normalize name (lowercase, remove spaces)
        normalized_name = name.lower().replace(" ", "")
        
        # Add school if available
        if school:
            normalized_school = school.lower().replace(" ", "")
            return f"{normalized_name}_{normalized_school}"
        
        return normalized_name
    
    def _update_player_from_source(self, player: TransferPlayer, source_player: Dict[str, Any], source: DataSource):
        """Update a consolidated player record with data from a specific source"""
        # Update last updated timestamp
        player.last_updated[source] = datetime.now().isoformat()
        
        # Update profile URL
        if "profile_url" in source_player and source_player["profile_url"]:
            player.profile_urls[source] = source_player["profile_url"]
        
        # Update rankings
        if "rank" in source_player and source_player["rank"]:
            try:
                # Parse the rank to an integer
                rank = int(source_player["rank"])
                player.rankings[source] = rank
                
                # Calculate composite ranking (average of available rankings)
                if player.rankings:
                    player.composite_ranking = int(sum(player.rankings.values()) / len(player.rankings))
            except (ValueError, TypeError):
                pass
        
        # Update player stats if available
        if "stats" in source_player and source_player["stats"]:
            # Convert source-specific stats object to our standard model
            stats_dict = source_player["stats"]
            stats = PlayerStats(
                ppg=stats_dict.get("ppg"),
                rpg=stats_dict.get("rpg"),
                apg=stats_dict.get("apg"),
                spg=stats_dict.get("spg"),
                bpg=stats_dict.get("bpg"),
                fg_pct=stats_dict.get("fg_pct"),
                three_pt_pct=stats_dict.get("three_pt_pct"),
                ft_pct=stats_dict.get("ft_pct"),
                source=source
            )
            player.stats[source] = stats
        
        # Update NIL valuation
        if "nil_valuation" in source_player and source_player["nil_valuation"]:
            player.nil_valuation[source] = str(source_player["nil_valuation"])
        
        # Update basic fields (only if not already set or if this is ON3)
        # We prioritize ON3 data for basic fields as it's generally more complete
        update_basic = (source == DataSource.ON3) or not any([
            player.position,
            player.height,
            player.previous_school,
            player.class_year,
            player.eligibility,
            player.status,
            player.destination_school
        ])
        
        if update_basic:
            if "position" in source_player and source_player["position"]:
                player.position = source_player["position"]
            
            if "height" in source_player and source_player["height"]:
                player.height = source_player["height"]
            
            if "previous_school" in source_player and source_player["previous_school"]:
                player.previous_school = source_player["previous_school"]
            elif "last_team" in source_player and source_player["last_team"]:
                player.previous_school = source_player["last_team"]
            
            if "class_year" in source_player and source_player["class_year"]:
                player.class_year = source_player["class_year"]
            
            if "eligibility" in source_player and source_player["eligibility"]:
                player.eligibility = source_player["eligibility"]
            
            if "status" in source_player and source_player["status"]:
                player.status = source_player["status"]
            
            if "destination_school" in source_player and source_player["destination_school"]:
                player.destination_school = source_player["destination_school"]
            elif "new_team" in source_player and source_player["new_team"] and source_player["new_team"] != "N/A":
                player.destination_school = source_player["new_team"]
    
    def query_players(self, query: PortalQuery) -> List[TransferPlayer]:
        """Query the consolidated player database"""
        # Return empty list if no data
        if not self.players:
            return []
        
        # Make a list from the dictionary values
        players = list(self.players.values())
        
        # Filter by source if specified
        if query.source != DataSource.ALL:
            players = [p for p in players if query.source in p.sources]
        
        # Apply basic filters
        if query.position:
            players = [p for p in players if p.position and query.position.lower() in p.position.lower()]
        
        if query.school:
            players = [p for p in players if (
                (p.previous_school and query.school.lower() in p.previous_school.lower()) or
                (p.destination_school and query.school.lower() in p.destination_school.lower())
            )]
        
        if query.status:
            players = [p for p in players if p.status and query.status.lower() in p.status.lower()]
        
        # Apply stats filter (check all sources)
        if query.min_ppg is not None:
            players = [
                p for p in players 
                if any(
                    stats.ppg and stats.ppg >= query.min_ppg 
                    for stats in p.stats.values()
                )
            ]
        
        # Apply ranking filters
        if query.min_ranking is not None:
            players = [
                p for p in players
                if p.composite_ranking and p.composite_ranking >= query.min_ranking
            ]
        
        if query.max_ranking is not None:
            players = [
                p for p in players
                if p.composite_ranking and p.composite_ranking <= query.max_ranking
            ]
        
        # Sort by composite ranking if available, otherwise by name
        players.sort(
            key=lambda p: (
                -(p.composite_ranking or float('inf')),
                p.name
            )
        )
        
        # Apply limit
        if query.limit:
            players = players[:query.limit]
        
        return players


# Initialize the orchestrator
orchestrator = TransferPortalOrchestrator()


@app.on_event("startup")
async def startup_event():
    """Initialize the orchestrator when the API starts"""
    await orchestrator.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the orchestrator when the API shuts down"""
    await orchestrator.stop()


@app.get("/portal/players")
async def get_players():
    """Get all consolidated transfer portal players"""
    if not orchestrator.players:
        raise HTTPException(status_code=404, detail="No player data available")
    
    return {
        "last_updated": orchestrator.last_consolidation,
        "player_count": len(orchestrator.players),
        "players": [p.dict() for p in orchestrator.players.values()]
    }


@app.post("/portal/refresh")
async def refresh_data(source: Optional[DataSource] = DataSource.ALL):
    """Force a refresh of the transfer portal data"""
    try:
        if source == DataSource.ALL:
            success = await orchestrator.refresh_all_agents()
        else:
            success = await orchestrator.refresh_agent(source)
        
        return {
            "status": "success" if success else "partial_failure",
            "player_count": len(orchestrator.players),
            "source": source.value
        }
    except Exception as e:
        logger.error(f"Error refreshing data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/portal/metrics")
async def get_metrics():
    """Get metrics about the transfer portal data collection"""
    return {
        "agent_metrics": {
            source.value: metrics.dict() 
            for source, metrics in orchestrator.metrics.items()
        },
        "total_players": len(orchestrator.players),
        "last_consolidation": orchestrator.last_consolidation
    }


@app.post("/portal/query")
async def query_players(query: PortalQuery):
    """
    Query the transfer portal for players matching specific criteria
    """
    try:
        players = orchestrator.query_players(query)
        return {"players": [p.dict() for p in players]}
    except Exception as e:
        logger.error(f"Error querying players: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/portal/player/{player_id}")
async def get_player_details(player_id: str):
    """
    Get detailed information about a specific player
    """
    if player_id not in orchestrator.players:
        raise HTTPException(status_code=404, detail=f"Player with ID {player_id} not found")
    
    return orchestrator.players[player_id].dict()


@app.get("/health")
async def health_check():
    """Simple health check endpoint to verify the API is running"""
    return {
        "status": "ok",
        "service": "Transfer Portal Orchestrator",
        "time": datetime.now().isoformat(),
        "agents": {
            source.value: metrics.status
            for source, metrics in orchestrator.metrics.items()
        }
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Basketball Transfer Portal Orchestrator on port 9000...")
    try:
        # Use uvicorn.run with log_config to ensure logs are visible
        uvicorn.run(
            "src.agents.transfer_portal_orchestrator:app", 
            host="0.0.0.0",  # Listen on all interfaces 
            port=9000, 
            log_level="debug",
            reload=False
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise 