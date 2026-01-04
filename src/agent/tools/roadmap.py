"""
Roadmap Tool - Fetches Microsoft 365 public roadmap updates
Uses the public Microsoft roadmap API
"""

import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import re

logger = logging.getLogger(__name__)


class RoadmapStatus(Enum):
    """Roadmap item status"""
    ROLLING_OUT = "Rolling out"
    IN_DEVELOPMENT = "In development"
    LAUNCHED = "Launched"
    CANCELLED = "Cancelled"
    PAUSED = "Paused"


@dataclass
class RoadmapItem:
    """Represents a single roadmap item"""
    id: str
    title: str
    description: str
    status: str
    product: str
    target_start: Optional[datetime]
    target_completion: Optional[datetime]
    last_updated: datetime
    platforms: List[str]
    is_smb_relevant: bool = False


class RoadmapTool:
    """Fetches and processes Microsoft 365 public roadmap updates"""

    def __init__(self, roadmap_api_url: str = "https://www.microsoft.com/releasecommunications/api/v1/m365"):
        self.roadmap_api_url = roadmap_api_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.microsoft.com/en-us/microsoft-365/roadmap"
        }
        logger.info(f"RoadmapTool initialized")

    async def connect(self) -> bool:
        """Establish connection"""
        try:
            self.session = aiohttp.ClientSession()
            logger.info("RoadmapTool connected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Roadmap API: {e}")
            return False

    async def fetch_items(
        self,
        days_back: int = 30,
        products: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None
    ) -> List[RoadmapItem]:
        """
        Fetch roadmap items updated in last N days
        
        Args:
            days_back: Number of days back to fetch (default 30)
            products: Filter by products (e.g., ['Teams', 'Exchange', 'SharePoint'])
            statuses: Filter by statuses (e.g., ['Rolling out', 'In development'])
        
        Returns:
            List of RoadmapItem objects
        """
        try:
            url = f"{self.roadmap_api_url}/features"
            
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    items = []
                    cutoff_date = datetime.utcnow() - timedelta(days=days_back)
                    
                    for item in data.get('value', []):
                        try:
                            roadmap_item = self._parse_roadmap_item(item)
                            
                            # Filter by last update date
                            if roadmap_item.last_updated < cutoff_date:
                                continue
                            
                            # Filter by product
                            if products and roadmap_item.product not in products:
                                continue
                            
                            # Filter by status
                            if statuses and roadmap_item.status not in statuses:
                                continue
                            
                            # Check SMB relevance
                            roadmap_item.is_smb_relevant = self._is_smb_relevant(roadmap_item)
                            
                            items.append(roadmap_item)
                        except Exception as e:
                            logger.warning(f"Failed to parse roadmap item: {e}")
                            continue
                    
                    logger.info(f"Fetched {len(items)} roadmap items")
                    return items
                else:
                    logger.error(f"Roadmap API error: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to fetch roadmap items: {e}")
            return []

    def _parse_roadmap_item(self, item: Dict[str, Any]) -> RoadmapItem:
        """Parse roadmap API response into RoadmapItem"""
        return RoadmapItem(
            id=item.get('id', ''),
            title=item.get('title', ''),
            description=item.get('description', ''),
            status=item.get('releaseStatus', 'Unknown'),
            product=item.get('product', ''),
            target_start=self._parse_date(item.get('targetStartDate')),
            target_completion=self._parse_date(item.get('targetCompletionDate')),
            last_updated=self._parse_date(item.get('lastModifiedDateTime')) or datetime.utcnow(),
            platforms=item.get('platforms', [])
        )

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            # Handle ISO format with timezone
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            try:
                # Try simple date format (YYYY-MM-DD)
                return datetime.strptime(date_str, '%Y-%m-%d')
            except:
                return None

    @staticmethod
    def _is_smb_relevant(item: RoadmapItem) -> bool:
        """
        Determine if roadmap item is relevant for SMBs.
        SMBs typically care about:
        - Teams/collaboration features
        - Security and compliance
        - Cost-effective improvements
        - Easy-to-implement changes
        """
        smb_keywords = [
            'teams', 'chat', 'meeting', 'security', 'encryption',
            'compliance', 'copilot', 'ai', 'governance', 'tenant',
            'user management', 'hybrid', 'remote', 'sharepoint',
            'integration', 'performance'
        ]
        
        title_lower = item.title.lower()
        desc_lower = item.description.lower()
        
        # Check for SMB-relevant keywords
        relevant = any(keyword in title_lower or keyword in desc_lower for keyword in smb_keywords)
        
        # Avoid overly enterprise features
        enterprise_keywords = ['enterprise scale', 'large-scale', 'datacenter', 'premium only']
        is_enterprise = any(kw in desc_lower for kw in enterprise_keywords)
        
        return relevant and not is_enterprise

    async def get_product_updates(self, product: str, days_back: int = 30) -> List[RoadmapItem]:
        """Get updates for a specific product"""
        return await self.fetch_items(days_back=days_back, products=[product])

    async def filter_smb_relevant(self, items: List[RoadmapItem]) -> List[RoadmapItem]:
        """Filter items relevant to SMBs"""
        return [item for item in items if item.is_smb_relevant]

    async def close(self) -> None:
        """Clean up resources"""
        if self.session:
            await self.session.close()
            logger.info("RoadmapTool closed")
