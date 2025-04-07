"""
News Monitor Integration with Transfer Portal Orchestrator

This module integrates the News and Social Media Monitoring Agent with the
Transfer Portal Orchestrator, enabling enriched data and early detection
of transfer activities before they appear in official portals.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from src.agents.news_monitor_agent import (
    NewsAndSocialMonitorAgent,
    NewsMonitorConfig,
    NewsMonitorMCPAdapter,
    NewsSource,
    SocialPlatform,
    TransferEventType,
    TransferNewsItem
)

from src.agents.transfer_portal_orchestrator import (
    TransferPortalOrchestrator,
    DataSource,
    TransferPlayer,
    PortalQuery
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewsEnrichedOrchestrator(TransferPortalOrchestrator):
    """
    Extended orchestrator that integrates news and social media data
    with the transfer portal information.
    """
    
    def __init__(self, refresh_interval: int = 3600, news_refresh_interval: int = 3600):
        """Initialize the extended orchestrator"""
        # Initialize the base orchestrator
        super().__init__(refresh_interval)
        
        # Create news monitor configuration
        news_config = NewsMonitorConfig(
            news_sources=[
                NewsSource.ESPN,
                NewsSource.CBS_SPORTS,
                NewsSource.ON3, 
                NewsSource.TWO47SPORTS,
                NewsSource.RIVALS
            ],
            social_platforms=[
                SocialPlatform.TWITTER,
                SocialPlatform.INSTAGRAM
            ],
            refresh_interval=news_refresh_interval,
            max_age_days=14,  # Track news for up to 2 weeks
            tracked_programs=self._get_tracked_programs()
        )
        
        # Create news monitor agent
        self.news_agent = NewsAndSocialMonitorAgent(news_config)
        self.news_adapter = NewsMonitorMCPAdapter(self.news_agent)
        
        # News refresh task
        self.news_refresh_task = None
    
    def _get_tracked_programs(self) -> List[str]:
        """Get the list of programs to track in news"""
        # In a production environment, this would likely come from a configuration file
        # or database, but for this example we'll hardcode some major programs
        return [
            "Duke", "North Carolina", "Kentucky", "Kansas", "UCLA", "Gonzaga", 
            "Michigan State", "Villanova", "Arizona", "Indiana", "Georgetown", 
            "Louisville", "Connecticut", "Syracuse", "Ohio State", "Michigan", 
            "Florida", "Wisconsin", "Purdue", "Illinois", "Alabama", "Auburn", 
            "Tennessee", "Texas", "Baylor", "Houston", "Arkansas", "Iowa State", 
            "Iowa", "Maryland", "Virginia"
        ]
    
    async def start(self):
        """Start the enriched orchestrator"""
        logger.info("Starting News-Enriched Transfer Portal Orchestrator")
        
        # Initialize news data
        try:
            await self.news_agent.refresh_all_sources()
        except Exception as e:
            logger.error(f"Error initializing news data: {str(e)}")
            logger.info("Continuing startup despite news initialization failure")
        
        # Start news refresh task
        self.news_refresh_task = asyncio.create_task(
            self._schedule_news_refreshes()
        )
        
        # Start the base orchestrator
        await super().start()
    
    async def stop(self):
        """Stop the enriched orchestrator"""
        logger.info("Stopping News-Enriched Transfer Portal Orchestrator")
        
        # Cancel news refresh task
        if self.news_refresh_task:
            self.news_refresh_task.cancel()
            try:
                await self.news_refresh_task
            except asyncio.CancelledError:
                logger.info("News refresh task cancelled")
        
        # Stop the base orchestrator
        await super().stop()
    
    async def _schedule_news_refreshes(self):
        """Background task to schedule periodic refreshes of news data"""
        while True:
            try:
                # Wait for initial delay (stagger the news refresh from portal refresh)
                await asyncio.sleep(300)  # 5 minutes initial delay
                
                # Refresh news data
                await self.news_agent.refresh_all_sources()
                
                # Integrate news data with portal data
                await self._integrate_news_data()
                
                # Wait for next refresh
                await asyncio.sleep(self.news_agent.config.refresh_interval)
                
            except asyncio.CancelledError:
                logger.info("News refresh task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in news refresh task: {str(e)}")
                # Wait before retrying
                await asyncio.sleep(60)
    
    async def _integrate_news_data(self):
        """
        Integrate news data with the transfer portal data.
        This adds contextual information to players and may detect
        transfers before they appear in the official portal.
        """
        logger.info("Integrating news data with transfer portal data")
        
        # Get all players from the consolidated database
        for player_id, player in list(self.players.items()):
            # Get news items for this player
            news_items = self.news_agent.query_news_items(
                player_name=player.name,
                limit=0
            )
            
            if not news_items:
                continue
            
            # Add any new transfer information
            for item in news_items:
                # Update destination school if news reports a commitment
                if (TransferEventType.COMMITMENT in item.event_types or 
                    TransferEventType.PORTAL_ENTRY in item.event_types):
                    # Only update if we have high confidence and player doesn't already have destination
                    if item.confidence_score >= 0.7 and not player.destination_school and item.destination_school:
                        player.destination_school = item.destination_school
                        logger.info(f"Updated destination school for {player.name} to {item.destination_school} based on news")
                    
                    # Update previous school if not already known
                    if not player.previous_school and item.previous_school:
                        player.previous_school = item.previous_school
                        logger.info(f"Updated previous school for {player.name} to {item.previous_school} based on news")
        
        # Check for players in news that aren't in our database yet
        all_news_items = list(self.news_agent.news_items.values())
        
        # Group by player name
        player_news = {}
        for item in all_news_items:
            if item.player_name not in player_news:
                player_news[item.player_name] = []
            player_news[item.player_name].append(item)
        
        # Check each player
        for player_name, items in player_news.items():
            # Skip if player is already in our database
            player_exists = any(p.name == player_name for p in self.players.values())
            if player_exists:
                continue
            
            # Check if we have high-confidence news about this player entering the portal
            portal_items = [item for item in items if TransferEventType.PORTAL_ENTRY in item.event_types]
            if not portal_items:
                continue
            
            # Sort by confidence score
            portal_items.sort(key=lambda x: x.confidence_score, reverse=True)
            
            # If we have high confidence, create a new player record
            if portal_items[0].confidence_score >= 0.8:
                best_item = portal_items[0]
                
                # Generate a player ID
                player_id = self._generate_player_id(best_item.player_name, best_item.previous_school)
                
                # Create new player record
                player = TransferPlayer(
                    player_id=player_id,
                    name=best_item.player_name,
                    previous_school=best_item.previous_school,
                    destination_school=best_item.destination_school,
                    sources=[DataSource.ALL],  # Mark as detected from news sources
                    status="in portal"
                )
                
                # Add to database
                self.players[player_id] = player
                logger.info(f"Added new player {player.name} based on news data")
    
    def get_player_news(self, player_name: str, limit: int = 10) -> List[Dict]:
        """Get news items related to a specific player"""
        news_items = self.news_agent.query_news_items(
            player_name=player_name,
            limit=limit
        )
        return [item.dict() for item in news_items]
    
    def get_player_timeline(self, player_name: str) -> List[Dict]:
        """Get a chronological timeline of news for a player"""
        timeline = self.news_agent.get_player_timeline(player_name)
        return [item.dict() for item in timeline]
    
    def get_school_news_activity(self, school: str) -> Dict:
        """Get transfer news activity for a specific school"""
        return self.news_agent.get_school_activity(school)
    
    def detect_coaching_changes(self) -> List[Dict]:
        """Detect coaching changes that might affect transfers"""
        return self.news_agent.detect_coaching_changes()
    
    def get_transfer_trends(self) -> Dict:
        """Get notable trends in transfer activity"""
        return self.news_agent.identify_notable_trends()
    
    def query_news(self, **query_params) -> List[Dict]:
        """Query news items with the given parameters"""
        return self.news_adapter.query_news_items(query_params)


# FastAPI endpoints for the news-enriched orchestrator
def register_news_endpoints(app, enriched_orchestrator):
    """Register FastAPI endpoints for the news-enriched orchestrator"""
    from fastapi import APIRouter, Query, HTTPException
    
    # Create router
    news_router = APIRouter(prefix="/news", tags=["news"])
    
    @news_router.get("/player/{player_name}")
    async def get_player_news(player_name: str, limit: int = Query(10, ge=1, le=100)):
        """Get news items for a specific player"""
        try:
            return enriched_orchestrator.get_player_news(player_name, limit)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @news_router.get("/player/{player_name}/timeline")
    async def get_player_timeline(player_name: str):
        """Get chronological timeline for a player"""
        try:
            return enriched_orchestrator.get_player_timeline(player_name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @news_router.get("/school/{school}")
    async def get_school_activity(school: str):
        """Get transfer activity for a school"""
        try:
            return enriched_orchestrator.get_school_news_activity(school)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @news_router.get("/coaching-changes")
    async def get_coaching_changes():
        """Get detected coaching changes"""
        try:
            return enriched_orchestrator.detect_coaching_changes()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @news_router.get("/trends")
    async def get_trends():
        """Get transfer portal trends from news"""
        try:
            return enriched_orchestrator.get_transfer_trends()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @news_router.get("/search")
    async def search_news(
        player_name: Optional[str] = None,
        school: Optional[str] = None,
        event_type: Optional[str] = None,
        min_confidence: float = Query(0.0, ge=0.0, le=1.0),
        verified_only: bool = False,
        days_back: int = Query(7, ge=1, le=30),
        limit: int = Query(20, ge=1, le=100)
    ):
        """Search news with the given parameters"""
        try:
            # Convert event_type string to enum if provided
            event_type_enum = None
            if event_type:
                try:
                    event_type_enum = TransferEventType(event_type)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")
            
            # Build query params
            params = {
                "player_name": player_name,
                "school": school,
                "event_type": event_type_enum,
                "min_confidence": min_confidence,
                "verified_only": verified_only,
                "days_back": days_back,
                "limit": limit
            }
            
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}
            
            return enriched_orchestrator.query_news(**params)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Add router to app
    app.include_router(news_router)


async def main():
    """Run the news-enriched orchestrator as a standalone service"""
    from fastapi import FastAPI
    import uvicorn
    
    # Create orchestrator
    orchestrator = NewsEnrichedOrchestrator()
    
    # Create FastAPI app
    app = FastAPI(title="Basketball Transfer Portal with News Integration")
    
    # Register news endpoints
    register_news_endpoints(app, orchestrator)
    
    # Start orchestrator
    await orchestrator.start()
    
    # Run API
    config = uvicorn.Config(app, host="0.0.0.0", port=9000)
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main()) 