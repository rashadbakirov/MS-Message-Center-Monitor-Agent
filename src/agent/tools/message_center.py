"""
Message Center Tool - Fetches Microsoft 365 Service Health via Microsoft Graph API
Uses Client Credentials OAuth2 flow for secure authentication
Supports real-time polling with last_check_time tracking
"""

import asyncio
import aiohttp
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MessageCenterItem:
    """Represents a single Message Center announcement"""
    id: str
    title: str
    summary: str
    body: str
    category: str
    severity: str
    created_at: datetime
    last_updated: datetime
    affected_services: List[str]


class MessageCenterTool:
    """Fetches Microsoft 365 Service Health messages via Microsoft Graph API"""

    STATE_FILE = Path("data/message_center_state.json")

    def __init__(self, tenant_id: str, app_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.app_id = app_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_check_time: Optional[datetime] = None
        self._load_state()
        logger.info(f"MessageCenterTool initialized for tenant {tenant_id}")

    def _load_state(self) -> None:
        """Load last_check_time from persistent state file"""
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE, 'r') as f:
                    state = json.load(f)
                    if 'last_check_time' in state:
                        self.last_check_time = datetime.fromisoformat(state['last_check_time'])
                        logger.info(f"Loaded last_check_time: {self.last_check_time}")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")

    def _save_state(self) -> None:
        """Save last_check_time to persistent state file"""
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            state = {
                'last_check_time': datetime.now(timezone.utc).isoformat(),
                'last_check_timestamp': datetime.now(timezone.utc).timestamp()
            }
            with open(self.STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
            self.last_check_time = datetime.now(timezone.utc)
            logger.debug("State saved to file")
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    async def connect(self) -> bool:
        """Establish connection and get access token"""
        try:
            self.session = aiohttp.ClientSession()
            await self._refresh_token()
            logger.info("MessageCenterTool connected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    async def _refresh_token(self) -> None:
        """Get access token using Client Credentials flow"""
        try:
            token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.app_id,
                'client_secret': self.client_secret,
                'scope': 'https://graph.microsoft.com/.default'
            }

            async with self.session.post(token_url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result['access_token']
                    self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=3500)
                    logger.debug("Access token refreshed")
                else:
                    error_text = await response.text()
                    raise Exception(f"Token request failed: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise

    async def fetch(self) -> List[Dict[str, Any]]:
        """
        Convenience method - fetch recent announcements (last 7 days)
        Used for testing and simple cases
        
        Returns:
            List of raw Graph API message items as dicts
        """
        return await self.fetch_announcements(days_back=7)

    async def fetch_announcements(
        self,
        days_back: int = 7,
        categories: Optional[List[str]] = None,
        min_severity: Optional[str] = None
    ) -> List[MessageCenterItem]:
        """
        Fetch service announcements via Microsoft Graph API
        Endpoint: GET https://graph.microsoft.com/v1.0/admin/serviceAnnouncement/messages
        
        Args:
            days_back: Number of days back to fetch
            categories: Optional filter by category
            min_severity: Optional minimum severity filter
            
        Returns:
            List of MessageCenterItem objects
        """
        try:
            if not self.access_token or datetime.now(timezone.utc) > self.token_expires_at:
                await self._refresh_token()

            url = "https://graph.microsoft.com/v1.0/admin/serviceAnnouncement/messages"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }

            params = {
                '$orderby': 'startDateTime desc',
                '$top': 100
            }

            async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    items = []
                    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

                    for item in data.get('value', []):
                        try:
                            item_date = self._parse_datetime(item.get('startDateTime'))
                            if item_date < cutoff_date:
                                continue
                            
                            mc_item = self._parse_message_item(item)
                            
                            if min_severity and not self._meets_severity(mc_item.severity, min_severity):
                                continue
                                
                            items.append(mc_item)
                        except Exception as e:
                            logger.warning(f"Failed to parse item: {e}")
                            continue

                    logger.info(f"Fetched {len(items)} Message Center announcements")
                    return items
                else:
                    error_text = await response.text()
                    logger.error(f"Graph API error: {response.status} - {error_text}")
                    return []

        except asyncio.TimeoutError:
            logger.warning("Graph API request timed out")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch announcements: {e}")
            return []

    async def fetch_since(
        self,
        since_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch ONLY NEW items since last check (for live polling)
        Updates last_check_time after successful fetch
        
        Args:
            since_time: Optional explicit datetime to fetch since (defaults to last_check_time)
            
        Returns:
            List of raw Graph API message items (as dicts) from since_time onwards
        """
        try:
            if not self.access_token or datetime.now(timezone.utc) > self.token_expires_at:
                await self._refresh_token()

            # Use provided time or last saved time, default to 6 hours ago
            query_time = since_time or self.last_check_time or (datetime.now(timezone.utc) - timedelta(hours=6))
            
            # Format for Graph API filter (RFC3339)
            time_filter = query_time.isoformat().replace('+00:00', 'Z')
            
            url = "https://graph.microsoft.com/v1.0/admin/serviceAnnouncement/messages"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }

            # Filter for items created/updated AFTER our last check time
            params = {
                '$filter': f"startDateTime gt {time_filter}",
                '$orderby': 'startDateTime desc',
                '$top': 50
            }

            logger.debug(f"Fetching new items since: {time_filter}")

            async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('value', [])
                    
                    # Update last check time ONLY if we got results
                    self._save_state()
                    
                    logger.info(f"Fetched {len(items)} NEW items since {time_filter}")
                    return items
                else:
                    error_text = await response.text()
                    logger.error(f"Graph API error: {response.status} - {error_text}")
                    return []

        except asyncio.TimeoutError:
            logger.warning("Graph API request timed out")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch new announcements: {e}")
            return []

    async def fetch_recent(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Fetch items updated within the last N hours (does not update state).

        Args:
            hours_back: Lookback window in hours

        Returns:
            List of raw Graph API message items (as dicts)
        """
        try:
            if not self.access_token or datetime.now(timezone.utc) > self.token_expires_at:
                await self._refresh_token()

            query_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            time_filter = query_time.isoformat().replace('+00:00', 'Z')

            url = "https://graph.microsoft.com/v1.0/admin/serviceAnnouncement/messages"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            params = {
                '$filter': f"lastModifiedDateTime gt {time_filter}",
                '$orderby': 'lastModifiedDateTime desc',
                '$top': 100
            }

            logger.debug(f"Fetching items updated since: {time_filter}")

            async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('value', [])
                    logger.info(f"Fetched {len(items)} items updated in last {hours_back}h")
                    return items
                else:
                    error_text = await response.text()
                    logger.error(f"Graph API error: {response.status} - {error_text}")
                    return []

        except asyncio.TimeoutError:
            logger.warning("Graph API request timed out")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch recent announcements: {e}")
            return []

    def _parse_message_item(self, item: Dict[str, Any]) -> MessageCenterItem:
        """Parse Graph API message into MessageCenterItem"""
        return MessageCenterItem(
            id=item.get('id', ''),
            title=item.get('title', ''),
            summary=item.get('summary', ''),
            body=item.get('details', [{}])[0].get('contentType', '') if item.get('details') else '',
            category=item.get('category', 'General'),
            severity=item.get('severity', 'Normal'),
            created_at=self._parse_datetime(item.get('startDateTime')),
            last_updated=self._parse_datetime(item.get('lastModifiedDateTime')),
            affected_services=self._extract_affected_services(item)
        )

    def _extract_affected_services(self, item: Dict[str, Any]) -> List[str]:
        """Extract affected service names"""
        services = []
        if 'services' in item:
            services = [s.get('displayName', '') for s in item['services'] if 'displayName' in s]
        return services

    @staticmethod
    def _parse_datetime(dt_str: str) -> datetime:
        """Parse ISO datetime string"""
        try:
            if not dt_str:
                return datetime.now(timezone.utc)
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except:
            return datetime.now(timezone.utc)

    @staticmethod
    def _meets_severity(item_severity: str, min_severity: str) -> bool:
        """Check if item meets severity threshold"""
        levels = {'Low': 0, 'Normal': 1, 'High': 2}
        return levels.get(item_severity, 1) >= levels.get(min_severity, 1)

    async def close(self) -> None:
        """Clean up resources"""
        if self.session:
            await self.session.close()
            logger.info("MessageCenterTool closed")
