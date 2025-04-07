"""
Simple Transfer Portal Orchestrator

A basic script to test the orchestrator functionality without FastAPI
"""
import asyncio
import logging
import json
from datetime import datetime
from src.agents.on3_agent import On3TransferPortalAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    logger.info("Starting Simple Transfer Portal Orchestrator Test")
    
    try:
        # Initialize agent
        agent = On3TransferPortalAgent()
        logger.info("Initialized agent")
        
        # Scrape players
        logger.info("Scraping players...")
        players = await agent.scrape_players()
        
        # Print results
        logger.info(f"Found {len(players)} players")
        
        # Print the first 3 players
        for i, player in enumerate(players[:3], 1):
            logger.info(f"Player {i}: {json.dumps(player, indent=2)}")
        
    except Exception as e:
        logger.error(f"Error in orchestrator test: {str(e)}")
    
    logger.info("Orchestrator test complete")


if __name__ == "__main__":
    asyncio.run(main()) 