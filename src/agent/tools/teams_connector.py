import logging
import asyncio
import aiohttp
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TeamsConnector:
    """Send briefs to Teams via Power Automate webhook with Adaptive Cards"""
    
    def __init__(self, webhook_url: str):
        """
        Initialize Teams connector
        
        Args:
            webhook_url: Power Automate webhook URL
        """
        self.webhook_url = webhook_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def connect(self) -> bool:
        """Create connection session"""
        try:
            self.session = aiohttp.ClientSession()
            logger.info("TeamsConnector initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize TeamsConnector: {e}")
            return False
    
    async def send_brief(
        self,
        title: str,
        items: List[Any],
        cost_summary: Optional[Dict] = None,
        is_weekly: bool = False
    ) -> bool:
        """
        Send brief to Teams via Power Automate webhook
        
        Args:
            title: Brief title
            items: List of items (dicts or objects with attributes)
            cost_summary: Optional cost data
            is_weekly: Whether this is weekly brief
            
        Returns:
            True if sent successfully
        """
        try:
            if not self.session:
                return False

            # Format items - handle both dict and object types
            formatted_items = []
            for item in items[:10]:  # Limit to 10 items
                formatted_item = self._format_item(item)
                if formatted_item:
                    formatted_items.append(formatted_item)

            # Build Adaptive Card payload for Teams
            payload = self._build_adaptive_card(
                title=title,
                items=formatted_items,
                is_weekly=is_weekly,
                item_count=len(items)
            )

            headers = {"Content-Type": "application/json"}

            # Send to Power Automate webhook
            async with self.session.post(self.webhook_url, json=payload, headers=headers) as response:
                if response.status in [200, 201, 202]:
                    logger.info(f"Brief sent to Power Automate successfully (status: {response.status})")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send brief: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error sending brief: {e}")
            return False

    async def send_raw_card(self, card: Dict[str, Any]) -> bool:
        """
        Send a pre-built Adaptive Card directly to Teams
        Used for real-time item delivery from AI enrichment
        
        Args:
            card: Adaptive Card JSON object
            
        Returns:
            True if sent successfully
        """
        try:
            if not self.session:
                logger.error("No session - call connect() first")
                return False

            headers = {"Content-Type": "application/json"}

            # Send card directly to Power Automate webhook
            async with self.session.post(self.webhook_url, json=card, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status in [200, 201, 202]:
                    logger.debug(f"Card sent successfully (status: {response.status})")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send card: {response.status} - {error_text}")
                    return False
        except asyncio.TimeoutError:
            logger.error("Timeout sending card to Teams")
            return False
        except Exception as e:
            logger.error(f"Error sending raw card: {e}")
            return False

    def _format_item(self, item: Any) -> Optional[Dict]:
        """Convert item (dict or dataclass) to formatted dict"""
        try:
            if isinstance(item, dict):
                return {
                    "title": item.get("title", ""),
                    "summary": item.get("summary", "")[:200],
                    "category": item.get("category", "General"),
                    "impact": item.get("severity", item.get("impact", "Normal")),
                    "date": item.get("startDateTime", "")[:10]
                }
            else:
                # Handle dataclass objects
                return {
                    "title": getattr(item, "title", ""),
                    "summary": getattr(item, "summary", "")[:200],
                    "category": getattr(item, "category", "General"),
                    "impact": getattr(item, "severity", getattr(item, "impact", "Normal")),
                    "date": str(getattr(item, "startDateTime", ""))[:10]
                }
        except Exception as e:
            logger.error(f"Error formatting item: {e}")
            return None

    def _build_adaptive_card(
        self,
        title: str,
        items: List[Dict],
        is_weekly: bool = False,
        item_count: int = 0
    ) -> Dict:
        """Build proper Adaptive Card JSON for Power Automate"""
        
        # Build body with items
        body = [
            {
                "type": "TextBlock",
                "size": "Large",
                "weight": "Bolder",
                "text": f"{'Weekly' if is_weekly else 'Daily'} Microsoft Brief",
                "color": "Accent"
            },
            {
                "type": "TextBlock",
                "size": "Medium",
                "text": title,
                "wrap": True,
                "spacing": "Small"
            },
            {
                "type": "TextBlock",
                "text": f" {item_count} updates",
                "isSubtle": True,
                "spacing": "Small"
            },
            {
                "type": "Container",
                "separator": True,
                "spacing": "Medium",
                "items": self._build_items_containers(items)
            },
            {
                "type": "TextBlock",
                "text": f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                "isSubtle": True,
                "size": "Small",
                "spacing": "Large"
            }
        ]

        # Adaptive Card format required by Power Automate
        return {
            "type": "AdaptiveCard",
            "version": "1.4",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "body": body
        }

    def _build_items_containers(self, items: List[Dict]) -> List[Dict]:
        """Build container elements for each item"""
        containers = []
        for item in items:
            containers.append({
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": item.get("title", "No Title"),
                        "weight": "Bolder",
                        "wrap": True
                    },
                    {
                        "type": "TextBlock",
                        "text": f"**Category:** {item.get('category', 'N/A')} | **Impact:** {item.get('impact', 'Normal')}",
                        "isSubtle": True,
                        "spacing": "Small",
                        "wrap": True
                    },
                    {
                        "type": "TextBlock",
                        "text": item.get("summary", "")[:150] + ("..." if len(item.get("summary", "")) > 150 else ""),
                        "wrap": True,
                        "spacing": "Small",
                        "isSubtle": True
                    }
                ],
                "separator": True,
                "spacing": "Medium"
            })
        return containers

    async def close(self):
        """Close connection session"""
        if self.session:
            await self.session.close()
            logger.info("TeamsConnector closed")
