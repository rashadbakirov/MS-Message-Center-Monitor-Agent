"""
Service Health Tool - Fetches Microsoft 365 Service Health issues via Microsoft Graph API
Uses Client Credentials OAuth2 flow for secure authentication
Supports polling with last_check_time tracking
"""

import asyncio
import aiohttp
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ServiceHealthTool:
    """Fetches Microsoft 365 Service Health issues via Microsoft Graph API"""

    STATE_FILE = Path("data/service_health_state.json")

    def __init__(self, tenant_id: str, app_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.app_id = app_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_check_time: Optional[datetime] = None
        self._load_state()
        logger.info(f"ServiceHealthTool initialized for tenant {tenant_id}")

    def _load_state(self) -> None:
        """Load last_check_time from persistent state file"""
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE, "r") as f:
                    state = json.load(f)
                    if "last_check_time" in state:
                        self.last_check_time = datetime.fromisoformat(state["last_check_time"])
                        logger.info(f"Loaded service health last_check_time: {self.last_check_time}")
        except Exception as e:
            logger.warning(f"Failed to load service health state: {e}")

    def _save_state(self) -> None:
        """Save last_check_time to persistent state file"""
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "last_check_time": datetime.now(timezone.utc).isoformat(),
                "last_check_timestamp": datetime.now(timezone.utc).timestamp(),
            }
            with open(self.STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
            self.last_check_time = datetime.now(timezone.utc)
            logger.debug("Service health state saved to file")
        except Exception as e:
            logger.warning(f"Failed to save service health state: {e}")

    async def connect(self) -> bool:
        """Establish connection and get access token"""
        try:
            self.session = aiohttp.ClientSession()
            await self._refresh_token()
            logger.info("ServiceHealthTool connected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect ServiceHealthTool: {e}")
            return False

    async def _refresh_token(self) -> None:
        """Get access token using Client Credentials flow"""
        try:
            token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": self.app_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
            }

            async with self.session.post(token_url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result["access_token"]
                    self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=3500)
                    logger.debug("Service health access token refreshed")
                else:
                    error_text = await response.text()
                    raise Exception(f"Token request failed: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"Failed to refresh service health token: {e}")
            raise

    async def fetch_recent(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Fetch issues updated within the last N hours (does not update state).

        Args:
            hours_back: Lookback window in hours

        Returns:
            List of raw Graph API issue items (as dicts)
        """
        try:
            if not self.access_token or datetime.now(timezone.utc) > self.token_expires_at:
                await self._refresh_token()

            query_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            time_filter = query_time.isoformat().replace("+00:00", "Z")

            url = "https://graph.microsoft.com/v1.0/admin/serviceAnnouncement/issues"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            params = {
                "$filter": f"lastModifiedDateTime gt {time_filter}",
                "$orderby": "lastModifiedDateTime desc",
                "$top": 100,
            }

            logger.debug(f"Fetching service health issues updated since: {time_filter}")

            items = []
            async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("value", [])
                elif response.status == 400 and "$filter" in params:
                    logger.warning("Service health filter not supported, retrying without filter")
                else:
                    error_text = await response.text()
                    logger.error(f"Service health Graph API error: {response.status} - {error_text}")
                    return []

            if not items and "$filter" in params:
                params.pop("$filter", None)
                async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("value", [])
                    else:
                        error_text = await response.text()
                        logger.error(f"Service health Graph API error: {response.status} - {error_text}")
                        return []

            cutoff_date = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            filtered = self._filter_since(items, cutoff_date)

            logger.info(f"Fetched {len(filtered)} service health issues updated in last {hours_back}h")
            return filtered

        except asyncio.TimeoutError:
            logger.warning("Service health Graph API request timed out")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch service health issues: {e}")
            return []

    async def fetch_since(self, since_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch ONLY NEW issues since last check (for live polling).
        Updates last_check_time after successful fetch.

        Args:
            since_time: Optional explicit datetime to fetch since (defaults to last_check_time)

        Returns:
            List of raw Graph API issue items (as dicts) from since_time onwards
        """
        try:
            if not self.access_token or datetime.now(timezone.utc) > self.token_expires_at:
                await self._refresh_token()

            query_time = since_time or self.last_check_time or (datetime.now(timezone.utc) - timedelta(hours=6))
            time_filter = query_time.isoformat().replace("+00:00", "Z")

            url = "https://graph.microsoft.com/v1.0/admin/serviceAnnouncement/issues"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            params = {
                "$filter": f"lastModifiedDateTime gt {time_filter}",
                "$orderby": "lastModifiedDateTime desc",
                "$top": 50,
            }

            logger.debug(f"Fetching service health issues since: {time_filter}")

            items = []
            async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("value", [])
                elif response.status == 400 and "$filter" in params:
                    logger.warning("Service health filter not supported, retrying without filter")
                else:
                    error_text = await response.text()
                    logger.error(f"Service health Graph API error: {response.status} - {error_text}")
                    return []

            if not items and "$filter" in params:
                params.pop("$filter", None)
                async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("value", [])
                    else:
                        error_text = await response.text()
                        logger.error(f"Service health Graph API error: {response.status} - {error_text}")
                        return []

            filtered = self._filter_since(items, query_time)
            self._save_state()
            logger.info(f"Fetched {len(filtered)} NEW service health issues since {time_filter}")
            return filtered

        except asyncio.TimeoutError:
            logger.warning("Service health Graph API request timed out")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch new service health issues: {e}")
            return []

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> datetime:
        """Parse ISO datetime string"""
        try:
            if not dt_str:
                return datetime.now(timezone.utc)
            return datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

    @staticmethod
    def _filter_since(items: List[Dict[str, Any]], cutoff: datetime) -> List[Dict[str, Any]]:
        """Filter issues updated on/after cutoff."""
        filtered = []
        for item in items:
            item_time = ServiceHealthTool._parse_datetime(
                item.get("lastModifiedDateTime") or item.get("startDateTime")
            )
            if item_time >= cutoff:
                filtered.append(item)
        return filtered

    async def close(self) -> None:
        """Clean up resources"""
        if self.session:
            await self.session.close()
            logger.info("ServiceHealthTool closed")
