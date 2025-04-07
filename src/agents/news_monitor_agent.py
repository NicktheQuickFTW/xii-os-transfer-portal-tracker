"""
News and Social Media Monitoring Agent that operates under the transfer_portal_orchestrator for Basketball Transfers

This module implements a specialized agent for monitoring news sources and social media
platforms for information related to men's basketball transfers. It captures contextual
information that may not be available in official transfer portal data.

Key capabilities:
1. Monitoring sports news outlets for transfer announcements
2. Tracking player and program social media accounts for updates
3. Detecting coaching changes that might influence transfer activity
4. Identifying unofficial commitments and intentions
5. Capturing contextual information about transfer motivations
"""

import asyncio
import datetime
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union

import aiohttp
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewsSource(str, Enum):
    """Enumeration of news sources to monitor"""
    ESPN = "espn"
    CBS_SPORTS = "cbssports"
    ATHLETIC = "theathletic"
    RIVALS = "rivals"
    TWO47SPORTS = "247sports"
    ON3 = "on3"
    STADIUM = "stadium"
    FIELD_OF_68 = "fieldof68"
    SPORTS_ILLUSTRATED = "si"


class SocialPlatform(str, Enum):
    """Enumeration of social media platforms to monitor"""
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    THREADS = "threads"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class TransferEventType(str, Enum):
    """Enumeration of transfer-related event types"""
    PORTAL_ENTRY = "portal_entry"
    COMMITMENT = "commitment"
    VISIT_SCHEDULED = "visit_scheduled"
    VISIT_COMPLETED = "visit_completed"
    FINAL_LIST = "final_list"
    COACH_CHANGE = "coach_change"
    NIL_RELATED = "nil_related"
    ACADEMIC_RELATED = "academic_related"
    PLAYING_TIME = "playing_time"
    FAMILY_RELATED = "family_related"
    GRADUATION_TRANSFER = "graduation_transfer"
    MEDICAL_RELATED = "medical_related"
    DECOMMITMENT = "decommitment"


class TransferNewsItem(BaseModel):
    """Model for a transfer-related news item"""
    id: str
    player_name: str
    source_type: Union[NewsSource, SocialPlatform]
    source_name: str
    source_url: str
    title: Optional[str] = None
    content_snippet: Optional[str] = None
    publication_date: str
    event_types: List[TransferEventType] = Field(default_factory=list)
    previous_school: Optional[str] = None
    destination_school: Optional[str] = None
    mentioned_schools: List[str] = Field(default_factory=list)
    confidence_score: float = 1.0  # 0.0 to 1.0
    extracted_quotes: List[str] = Field(default_factory=list)
    verified: bool = False
    keywords: List[str] = Field(default_factory=list)


class NewsMonitorConfig(BaseModel):
    """Configuration for the news monitoring agent"""
    news_sources: List[NewsSource] = Field(default_factory=list)
    social_platforms: List[SocialPlatform] = Field(default_factory=list)
    refresh_interval: int = 3600  # seconds
    max_age_days: int = 7  # maximum age of news to retrieve
    additional_keywords: List[str] = Field(default_factory=list)
    tracked_coaches: List[str] = Field(default_factory=list)
    tracked_programs: List[str] = Field(default_factory=list)
    max_items_per_source: int = 100 


class NewsAndSocialMonitorAgent:
    """
    Agent for monitoring news and social media for basketball transfer information.
    Captures contextual information not available in official portal data.
    """
    
    def __init__(self, config: NewsMonitorConfig):
        """Initialize the news monitoring agent"""
        self.config = config
        self.news_items: Dict[str, TransferNewsItem] = {}
        self.last_refresh: Dict[Union[NewsSource, SocialPlatform], str] = {}
        self.school_aliases = self._load_school_aliases()
        
        # Seed some keywords for better filtering
        self.transfer_keywords = [
            "transfer portal", "transfers to", "commits to", 
            "verbal commitment", "official visit", "final list",
            "top schools", "enters portal", "leaving", "announced transfer",
            "transfer decision", "graduate transfer", "coach fired",
            "coach hired", "coaching change", "NIL deal", "NIL opportunity",
            "playing time", "closer to home", "medical hardship"
        ] + self.config.additional_keywords
    
    def _load_school_aliases(self) -> Dict[str, List[str]]:
        """Load aliases for school names to handle variations"""
        # In production, this would load from a file or database
        # For this implementation, we'll include some common variations
        return {
            "North Carolina": ["UNC", "Tar Heels", "Carolina"],
            "Duke": ["Blue Devils"],
            "Kentucky": ["UK", "Wildcats", "BBN"],
            "Kansas": ["Jayhawks", "KU"],
            "UCLA": ["Bruins"],
            "Indiana": ["Hoosiers", "IU"],
            "Michigan State": ["MSU", "Spartans"],
            "Arizona": ["Wildcats", "U of A"],
            "Gonzaga": ["Zags", "Bulldogs"],
            # Add more as needed
        }
    
    def _generate_item_id(self, source_type: Union[NewsSource, SocialPlatform], 
                         source_url: str, player_name: str) -> str:
        """Generate a unique ID for a news item"""
        # Create a stable ID by hashing key components
        import hashlib
        input_str = f"{source_type}|{source_url}|{player_name}"
        return hashlib.md5(input_str.encode()).hexdigest()
    
    async def refresh_all_sources(self):
        """Refresh data from all configured sources"""
        logger.info("Starting refresh of all news and social sources")
        
        tasks = []
        
        # Add tasks for news sources
        for source in self.config.news_sources:
            tasks.append(self.refresh_news_source(source))
        
        # Add tasks for social platforms
        for platform in self.config.social_platforms:
            tasks.append(self.refresh_social_platform(platform))
        
        # Run all tasks and collect results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful sources
        successful = sum(1 for result in results if isinstance(result, int) and result > 0)
        logger.info(f"Completed refresh of {successful}/{len(tasks)} sources")
        
        # Process and consolidate the news items
        await self._post_process_news_items()
        
        return {
            "total_sources": len(tasks),
            "successful_sources": successful,
            "total_items": len(self.news_items)
        }
    
    async def refresh_news_source(self, source: NewsSource) -> int:
        """Refresh data from a specific news source"""
        logger.info(f"Refreshing news source: {source}")
        
        try:
            # Record refresh timestamp
            self.last_refresh[source] = datetime.datetime.now().isoformat()
            
            # Use different methods based on the source
            if source == NewsSource.ESPN:
                items = await self._scrape_espn()
            elif source == NewsSource.CBS_SPORTS:
                items = await self._scrape_cbs_sports()
            elif source == NewsSource.ON3:
                items = await self._scrape_on3()
            elif source == NewsSource.TWO47SPORTS:
                items = await self._scrape_247sports()
            elif source == NewsSource.RIVALS:
                items = await self._scrape_rivals()
            else:
                # Generic approach for other sources
                items = await self._scrape_generic_news(source)
            
            # Add items to the collection
            for item in items:
                self.news_items[item.id] = item
            
            logger.info(f"Retrieved {len(items)} items from {source}")
            return len(items)
            
        except Exception as e:
            logger.error(f"Error refreshing {source}: {str(e)}")
            return 0
    
    async def refresh_social_platform(self, platform: SocialPlatform) -> int:
        """Refresh data from a specific social media platform"""
        logger.info(f"Refreshing social platform: {platform}")
        
        try:
            # Record refresh timestamp
            self.last_refresh[platform] = datetime.datetime.now().isoformat()
            
            # Use different methods based on the platform
            if platform == SocialPlatform.TWITTER:
                items = await self._scrape_twitter()
            elif platform == SocialPlatform.INSTAGRAM:
                items = await self._scrape_instagram()
            elif platform == SocialPlatform.THREADS:
                items = await self._scrape_threads()
            else:
                # Generic approach for other platforms
                items = await self._scrape_generic_social(platform)
            
            # Add items to the collection
            for item in items:
                self.news_items[item.id] = item
            
            logger.info(f"Retrieved {len(items)} items from {platform}")
            return len(items)
            
        except Exception as e:
            logger.error(f"Error refreshing {platform}: {str(e)}")
            return 0
    
    async def _scrape_espn(self) -> List[TransferNewsItem]:
        """Scrape transfer news from ESPN"""
        items = []
        logger.info("Scraping ESPN news (placeholder implementation)")
        # This would be a full implementation in production
        return items
    
    async def _scrape_cbs_sports(self) -> List[TransferNewsItem]:
        """Scrape transfer news from CBS Sports"""
        items = []
        logger.info("Scraping CBS Sports news (placeholder implementation)")
        # This would be a full implementation in production
        return items
    
    async def _scrape_twitter(self) -> List[TransferNewsItem]:
        """Scrape transfer news from Twitter (X)"""
        items = []
        logger.info("Scraping Twitter content (placeholder implementation)")
        # This would be a full implementation in production
        return items
    
    async def _scrape_on3(self) -> List[TransferNewsItem]:
        """Scrape transfer news from On3"""
        items = []
        logger.info("Scraping On3 news (placeholder implementation)")
        # This would be a full implementation in production
        return items
    
    async def _scrape_generic_news(self, source: NewsSource) -> List[TransferNewsItem]:
        """Generic scraper for news sources"""
        # This is a placeholder for a more complete implementation
        logger.info(f"Generic scraping for {source} (placeholder implementation)")
        return []
    
    async def _scrape_generic_social(self, platform: SocialPlatform) -> List[TransferNewsItem]:
        """Generic scraper for social platforms"""
        # This is a placeholder for a more complete implementation
        logger.info(f"Generic scraping for {platform} (placeholder implementation)")
        return []
    
    async def _scrape_instagram(self) -> List[TransferNewsItem]:
        """Scrape transfer news from Instagram"""
        # This is a placeholder for a more complete implementation
        logger.info("Scraping Instagram content (placeholder implementation)")
        return []
    
    async def _scrape_threads(self) -> List[TransferNewsItem]:
        """Scrape transfer news from Threads"""
        # This is a placeholder for a more complete implementation
        logger.info("Scraping Threads content (placeholder implementation)")
        return []
    
    async def _scrape_247sports(self) -> List[TransferNewsItem]:
        """Scrape transfer news from 247Sports"""
        # This is a placeholder for a more complete implementation
        items = []
        logger.info("Scraping 247Sports news (placeholder implementation)")
        return items
    
    async def _scrape_rivals(self) -> List[TransferNewsItem]:
        """Scrape transfer news from Rivals"""
        # Similar implementation pattern as other news sources
        # This is a placeholder for a more complete implementation
        items = []
        logger.info("Scraping Rivals news (placeholder implementation)")
        return items
    
    def _extract_player_names(self, text: str) -> List[str]:
        """
        Extract player names from text using pattern matching and filters
        
        In a production environment, this would use a more sophisticated NER model
        """
        if not text:
            return []
        
        # Simple pattern for detecting names (First Last)
        # This is a simplified approach and would need refinement in production
        name_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+)'
        potential_names = re.findall(name_pattern, text)
        
        # Filter out common non-player phrases
        filtered_names = []
        stop_phrases = [
            "Associated Press", "Head Coach", "Athletic Director", "College Basketball",
            "Breaking News", "Final Four", "NCAA Tournament", "Big Ten", "SEC", "ACC",
            "Big 12", "Pac 12", "Monday Night", "Tuesday Night", "Wednesday Night",
            "Thursday Night", "Friday Night", "Saturday Night", "Sunday Night",
            "Source Confirmed", "No Decision", "Decision Made"
        ]
        
        for name in potential_names:
            if name not in stop_phrases and len(name.split()) == 2:
                filtered_names.append(name)
        
        return list(set(filtered_names))  # Remove duplicates
    
    def _extract_school_mentions(self, text: str) -> List[str]:
        """Extract mentions of schools from text"""
        if not text:
            return []
        
        # List of D1 basketball programs
        # This would be a much more comprehensive list in production
        school_names = [
            "Duke", "North Carolina", "Kentucky", "Kansas", "UCLA", "Gonzaga", 
            "Michigan State", "Villanova", "Arizona", "Indiana", "Georgetown", 
            "Louisville", "Connecticut", "Syracuse", "Ohio State", "Michigan", 
            "Florida", "Wisconsin", "Purdue", "Illinois", "Alabama", "Auburn", 
            "Tennessee", "Texas", "Baylor", "Houston", "Arkansas", "Iowa State", 
            "Iowa", "Maryland", "Virginia", "North Carolina State", "Notre Dame"
        ]
        
        # Check for school names and their aliases
        mentioned_schools = []
        for school, aliases in self.school_aliases.items():
            if school in text:
                mentioned_schools.append(school)
                continue
                
            for alias in aliases:
                if alias in text:
                    mentioned_schools.append(school)
                    break
        
        # Check for other schools in the list
        for school in school_names:
            if school in text and school not in mentioned_schools:
                mentioned_schools.append(school)
        
        return mentioned_schools
    
    def _extract_quotes(self, text: str) -> List[str]:
        """Extract quoted statements from text"""
        if not text:
            return []
        
        # Find text between quotation marks
        quote_pattern = r'"([^"]*)"'
        quotes = re.findall(quote_pattern, text)
        
        # Also find text with single quotes
        single_quote_pattern = r"'([^']*)'"
        single_quotes = re.findall(single_quote_pattern, text)
        
        # Combine and filter for minimum length (avoid short expressions)
        all_quotes = quotes + single_quotes
        filtered_quotes = [q for q in all_quotes if len(q) > 15]
        
        return filtered_quotes
    
    def _detect_event_types(self, title: Optional[str], content: Optional[str]) -> List[TransferEventType]:
        """Detect types of transfer events mentioned in the content"""
        event_types = []
        combined_text = ""
        
        if title:
            combined_text += title + " "
        if content:
            combined_text += content
            
        if not combined_text:
            return event_types
            
        # Check for each event type using keyword patterns
        event_patterns = {
            TransferEventType.PORTAL_ENTRY: ["enters portal", "enters transfer portal", "has entered the portal"],
            TransferEventType.COMMITMENT: ["commits to", "committed to", "signs with", "chooses", "announces commitment"],
            TransferEventType.VISIT_SCHEDULED: ["scheduled visit", "plans to visit", "official visit to", "visit scheduled"],
            TransferEventType.VISIT_COMPLETED: ["completed visit", "visited", "after visiting", "following visit"],
            TransferEventType.FINAL_LIST: ["final list", "top schools", "narrowed down", "finalists"],
            TransferEventType.COACH_CHANGE: ["coach fired", "coaching change", "new coach", "head coach", "coaching staff"],
            TransferEventType.NIL_RELATED: ["NIL deal", "NIL opportunity", "name, image and likeness", "NIL collective"],
            TransferEventType.ACADEMIC_RELATED: ["academic", "degree", "graduate", "major", "education", "classroom"],
            TransferEventType.PLAYING_TIME: ["playing time", "minutes", "starter", "bench", "rotation", "role"],
            TransferEventType.FAMILY_RELATED: ["family", "closer to home", "parents", "child", "hometown"],
            TransferEventType.GRADUATION_TRANSFER: ["graduate transfer", "fifth year", "sixth year", "grad transfer"],
            TransferEventType.MEDICAL_RELATED: ["injury", "medical", "surgery", "recovery", "health"],
            TransferEventType.DECOMMITMENT: ["decommits", "reopens recruitment", "backs out", "decommitment"]
        }
        
        for event_type, patterns in event_patterns.items():
            for pattern in patterns:
                if pattern.lower() in combined_text.lower():
                    event_types.append(event_type)
                    break
        
        return event_types
    
    def _determine_schools(self, player_name: str, text: str, mentioned_schools: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Determine previous and destination schools for a player"""
        if not text or not player_name or not mentioned_schools:
            return None, None
            
        previous_school = None
        destination_school = None
        
        # Look for patterns indicating previous school
        prev_patterns = [
            f"{player_name} from ([A-Za-z ]+)",
            f"{player_name}, from ([A-Za-z ]+)",
            f"{player_name} of ([A-Za-z ]+)",
            f"{player_name} \(([A-Za-z ]+)\)"
        ]
        
        for pattern in prev_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                for school in mentioned_schools:
                    if school.lower() in match.lower():
                        previous_school = school
                        break
                if previous_school:
                    break
            if previous_school:
                break
        
        # Look for patterns indicating destination school
        dest_patterns = [
            f"{player_name} to ([A-Za-z ]+)",
            f"{player_name} commits to ([A-Za-z ]+)",
            f"{player_name} chooses ([A-Za-z ]+)",
            f"{player_name} picks ([A-Za-z ]+)",
            f"{player_name} signs with ([A-Za-z ]+)"
        ]
        
        for pattern in dest_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                for school in mentioned_schools:
                    if school.lower() in match.lower():
                        destination_school = school
                        break
                if destination_school:
                    break
            if destination_school:
                break
        
        return previous_school, destination_school
    
    async def _post_process_news_items(self):
        """Post-process collected news items to improve quality and remove duplicates"""
        # Identify duplicate information about the same player
        player_events = {}
        
        for item_id, item in self.news_items.items():
            if item.player_name not in player_events:
                player_events[item.player_name] = []
            player_events[item.player_name].append(item)
        
        # For each player, verify information across multiple sources when possible
        for player_name, items in player_events.items():
            if len(items) > 1:
                # Sort by publication date (newest first)
                items.sort(key=lambda x: x.publication_date, reverse=True)
                
                # Identify the most common schools mentioned
                prev_schools = {}
                dest_schools = {}
                
                for item in items:
                    if item.previous_school:
                        prev_schools[item.previous_school] = prev_schools.get(item.previous_school, 0) + 1
                    if item.destination_school:
                        dest_schools[item.destination_school] = dest_schools.get(item.destination_school, 0) + 1
                
                # Find the most frequently mentioned schools
                most_common_prev = max(prev_schools.items(), key=lambda x: x[1])[0] if prev_schools else None
                most_common_dest = max(dest_schools.items(), key=lambda x: x[1])[0] if dest_schools else None
                
                # If there's consensus, increase confidence for consistent items
                for item in items:
                    consistent_prev = item.previous_school == most_common_prev if most_common_prev else False
                    consistent_dest = item.destination_school == most_common_dest if most_common_dest else False
                    
                    # If information is consistent across sources, mark as verified
                    if consistent_prev and consistent_dest and len(items) >= 3:
                        item.verified = True
                        item.confidence_score = min(1.0, item.confidence_score + 0.1)
                    
                    # If information is inconsistent, reduce confidence
                    if (most_common_prev and item.previous_school and item.previous_school != most_common_prev) or \
                       (most_common_dest and item.destination_school and item.destination_school != most_common_dest):
                        item.confidence_score = max(0.3, item.confidence_score - 0.2)
    
    def query_news_items(self, 
                        player_name: Optional[str] = None,
                        school: Optional[str] = None,
                        event_type: Optional[TransferEventType] = None,
                        min_confidence: float = 0.0,
                        verified_only: bool = False,
                        days_back: int = 7,
                        limit: int = 20) -> List[TransferNewsItem]:
        """Query the collected news items based on filters"""
        # Calculate the earliest date to include
        earliest_date = datetime.datetime.now() - datetime.timedelta(days=days_back)
        
        # Start with all items
        items = list(self.news_items.values())
        
        # Apply filters
        if player_name:
            items = [item for item in items if player_name.lower() in item.player_name.lower()]
        
        if school:
            items = [item for item in items if 
                     (item.previous_school and school.lower() in item.previous_school.lower()) or
                     (item.destination_school and school.lower() in item.destination_school.lower()) or
                     any(school.lower() in s.lower() for s in item.mentioned_schools)]
        
        if event_type:
            items = [item for item in items if event_type in item.event_types]
        
        if min_confidence > 0.0:
            items = [item for item in items if item.confidence_score >= min_confidence]
        
        if verified_only:
            items = [item for item in items if item.verified]
        
        # Filter by date
        items = [item for item in items if 
                 datetime.datetime.fromisoformat(item.publication_date.replace('Z', '+00:00')) >= earliest_date]
        
        # Sort by publication date (newest first) and confidence
        items.sort(key=lambda x: (datetime.datetime.fromisoformat(x.publication_date.replace('Z', '+00:00')), x.confidence_score), reverse=True)
        
        # Apply limit
        if limit > 0:
            items = items[:limit]
        
        return items
    
    def get_player_timeline(self, player_name: str) -> List[TransferNewsItem]:
        """Get a chronological timeline of events for a specific player"""
        items = self.query_news_items(player_name=player_name, limit=0)
        
        # Sort chronologically (oldest first)
        items.sort(key=lambda x: datetime.datetime.fromisoformat(x.publication_date.replace('Z', '+00:00')))
        
        return items
    
    def get_school_activity(self, school: str) -> Dict:
        """Get transfer portal activity summary for a specific school"""
        # Query items related to the school
        items = self.query_news_items(school=school, limit=0)
        
        # Count incoming vs outgoing transfers
        incoming = [item for item in items if item.destination_school and school.lower() in item.destination_school.lower()]
        outgoing = [item for item in items if item.previous_school and school.lower() in item.previous_school.lower()]
        
        # Count by event type
        event_counts = {}
        for event_type in TransferEventType:
            event_counts[event_type] = len([item for item in items if event_type in item.event_types])
        
        # Group by player
        player_items = {}
        for item in items:
            if item.player_name not in player_items:
                player_items[item.player_name] = []
            player_items[item.player_name].append(item)
        
        # Build response
        return {
            "school": school,
            "total_mentions": len(items),
            "incoming_transfers": len(incoming),
            "outgoing_transfers": len(outgoing),
            "event_counts": event_counts,
            "players_mentioned": list(player_items.keys()),
            "latest_news": sorted(items, key=lambda x: datetime.datetime.fromisoformat(x.publication_date.replace('Z', '+00:00')), reverse=True)[:5]
        }
    
    def detect_coaching_changes(self) -> List[Dict]:
        """Detect potential coaching changes that might affect transfers"""
        # Query items related to coach changes
        items = self.query_news_items(event_type=TransferEventType.COACH_CHANGE, limit=0)
        
        # Group by school
        school_items = {}
        for item in items:
            for school in item.mentioned_schools:
                if school not in school_items:
                    school_items[school] = []
                school_items[school].append(item)
        
        # Create summaries for each school
        results = []
        for school, news_items in school_items.items():
            # Sort by date (newest first)
            news_items.sort(key=lambda x: datetime.datetime.fromisoformat(x.publication_date.replace('Z', '+00:00')), reverse=True)
            
            results.append({
                "school": school,
                "coaching_news_count": len(news_items),
                "latest_news": news_items[0] if news_items else None,
                "confidence": sum(item.confidence_score for item in news_items) / len(news_items) if news_items else 0
            })
        
        # Sort by confidence (highest first)
        results.sort(key=lambda x: x["confidence"], reverse=True)
        
        return results
    
    def identify_notable_trends(self) -> Dict:
        """Identify notable trends in the transfer portal data"""
        # This would be more sophisticated in production
        all_items = list(self.news_items.values())
        
        # Count events by type
        event_counts = {}
        for event_type in TransferEventType:
            event_counts[event_type] = len([item for item in all_items if event_type in item.event_types])
        
        # Count transfers by school
        school_counts = {}
        for item in all_items:
            # Count as destination school if available
            if item.destination_school:
                if item.destination_school not in school_counts:
                    school_counts[item.destination_school] = {"incoming": 0, "outgoing": 0}
                school_counts[item.destination_school]["incoming"] += 1
            
            # Count as previous school if available
            if item.previous_school:
                if item.previous_school not in school_counts:
                    school_counts[item.previous_school] = {"incoming": 0, "outgoing": 0}
                school_counts[item.previous_school]["outgoing"] += 1
        
        # Find schools with most activity
        active_schools = sorted(
            school_counts.items(), 
            key=lambda x: x[1]["incoming"] + x[1]["outgoing"], 
            reverse=True
        )[:10]
        
        # Find schools with highest net incoming transfers
        net_gain_schools = sorted(
            school_counts.items(),
            key=lambda x: x[1]["incoming"] - x[1]["outgoing"],
            reverse=True
        )[:5]
        
        # Find schools with highest net outgoing transfers
        net_loss_schools = sorted(
            school_counts.items(),
            key=lambda x: x[1]["outgoing"] - x[1]["incoming"],
            reverse=True
        )[:5]
        
        return {
            "total_news_items": len(all_items),
            "event_counts": event_counts,
            "most_active_schools": active_schools,
            "highest_net_gain_schools": net_gain_schools,
            "highest_net_loss_schools": net_loss_schools
        }


class NewsMonitorMCPAdapter:
    """
    Adapter class to integrate the News and Social Media Monitor with the MCP protocol.
    This provides a standardized interface for the orchestrator to interact with the agent.
    """
    
    def __init__(self, agent: NewsAndSocialMonitorAgent):
        self.agent = agent
    
    async def refresh_data(self):
        """Refresh data from all sources"""
        return await self.agent.refresh_all_sources()
    
    def query_news_items(self, query_params: Dict) -> List[Dict]:
        """Query news items with the given parameters"""
        # Convert dict params to expected types
        player_name = query_params.get('player_name')
        school = query_params.get('school')
        event_type = query_params.get('event_type')
        if event_type:
            event_type = TransferEventType(event_type)
        min_confidence = float(query_params.get('min_confidence', 0.0))
        verified_only = bool(query_params.get('verified_only', False))
        days_back = int(query_params.get('days_back', 7))
        limit = int(query_params.get('limit', 20))
        
        # Get items from agent
        items = self.agent.query_news_items(
            player_name=player_name,
            school=school,
            event_type=event_type,
            min_confidence=min_confidence,
            verified_only=verified_only,
            days_back=days_back,
            limit=limit
        )
        
        # Convert to dicts
        return [item.dict() for item in items]
    
    def get_player_timeline(self, player_name: str) -> List[Dict]:
        """Get timeline for a player"""
        items = self.agent.get_player_timeline(player_name)
        return [item.dict() for item in items]
    
    def get_school_activity(self, school: str) -> Dict:
        """Get activity for a school"""
        result = self.agent.get_school_activity(school)
        
        # Convert news items to dicts
        if 'latest_news' in result:
            result['latest_news'] = [item.dict() for item in result['latest_news']]
        
        return result
    
    def detect_coaching_changes(self) -> List[Dict]:
        """Detect coaching changes"""
        results = self.agent.detect_coaching_changes()
        
        # Convert news items to dicts
        for result in results:
            if 'latest_news' in result and result['latest_news']:
                result['latest_news'] = result['latest_news'].dict()
        
        return results
    
    def identify_notable_trends(self) -> Dict:
        """Identify notable trends"""
        return self.agent.identify_notable_trends()


async def main():
    """Main entry point for running the agent standalone"""
    # Example configuration
    config = NewsMonitorConfig(
        news_sources=[
            NewsSource.ESPN,
            NewsSource.CBS_SPORTS,
            NewsSource.ON3,
            NewsSource.TWO47SPORTS,
            NewsSource.RIVALS
        ],
        social_platforms=[
            SocialPlatform.TWITTER
        ],
        refresh_interval=3600,  # 1 hour
        max_age_days=7,
        additional_keywords=[
            "basketball transfer",
            "college hoops",
            "recruiting news"
        ],
        tracked_coaches=[
            "Jon Scheyer",
            "Bill Self",
            "John Calipari",
            "Hubert Davis",
            "Mark Few",
            "Scott Drew"
        ],
        tracked_programs=[
            "Duke",
            "North Carolina",
            "Kentucky",
            "Kansas",
            "Gonzaga",
            "UCLA",
            "Baylor",
            "Auburn",
            "Michigan State"
        ]
    )
    
    # Create agent
    agent = NewsAndSocialMonitorAgent(config)
    
    try:
        # Initial data refresh
        await agent.refresh_all_sources()
        
        # Example: Query for specific players
        player_items = agent.query_news_items(player_name="Smith", limit=5)
        print(f"Found {len(player_items)} news items for players named Smith")
        
        # Example: Get school activity
        duke_activity = agent.get_school_activity("Duke")
        print(f"Duke transfer activity: {duke_activity['incoming_transfers']} incoming, {duke_activity['outgoing_transfers']} outgoing")
        
        # Keep running and refresh periodically
        while True:
            # Wait for the refresh interval
            await asyncio.sleep(config.refresh_interval)
            
            # Refresh data
            await agent.refresh_all_sources()
            
    except KeyboardInterrupt:
        print("Agent stopped by user")


if __name__ == "__main__":
    asyncio.run(main())