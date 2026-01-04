#!/usr/bin/env python3
"""
Microsoft Message Center Monitor - Live monitoring orchestrator
Message Center polling with AI enrichment
Immediately sends analyzed items to Teams as they arrive
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from src.agent.config import Settings
from src.agent.tools.message_center import MessageCenterTool
from src.agent.tools.ai_enricher import AIEnricher
from src.connectors.adaptive_card_builder import AdaptiveCardBuilder
from src.agent.tools.teams_connector import TeamsConnector

# Settings
settings = Settings()

# Configure logging
logging.basicConfig(
    level=str(settings.log_level).upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class LiveBriefOrchestrator:
    """Real-time Message Center monitoring with AI enrichment"""

    # Configuration
    POLL_INTERVAL_SECONDS = 6 * 60 * 60  # 6 hours
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 10
    DAILY_BRIEF_LOOKBACK_HOURS = None

    def __init__(self):
        self.mc: MessageCenterTool = None
        self.ai: AIEnricher = None
        self.tm: TeamsConnector = None
        self.running = False
        self.processed_ids = set()  # Track processed items to avoid duplicates
        self.daily_brief_lookback_hours = settings.daily_brief_lookback_hours

    async def initialize(self) -> bool:
        """Initialize all components"""
        try:
            logger.info("Initializing Live Brief Orchestrator...")

            # Initialize Message Center Tool
            self.mc = MessageCenterTool(
                settings.azure_tenant_id,
                settings.mc_app_id,
                settings.mc_client_secret
            )
            if not await self.mc.connect():
                logger.error("Failed to connect to Message Center API")
                return False
            logger.info("Message Center connected")

            # Initialize AI Enricher
            self.ai = AIEnricher(
                endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                deployment=settings.azure_openai_deployment,
                api_version=settings.azure_openai_api_version
            )
            logger.info("AI Enricher initialized")

            # Initialize Teams Connector if configured
            if settings.teams_webhook_url:
                self.tm = TeamsConnector(settings.teams_webhook_url)
                if not await self.tm.connect():
                    logger.warning("Teams webhook configured but connection failed - will log only")
                    self.tm = None
                else:
                    logger.info("Teams Connector connected")
            else:
                logger.warning("Teams webhook not configured - items will be logged but not sent to Teams")

            logger.info("Orchestrator initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            return False

    async def monitor_loop(self):
        """Main monitoring loop - polls and processes new items"""
        poll_hours = self.POLL_INTERVAL_SECONDS // 3600
        logger.info(f"Starting live monitoring loop (polling every {poll_hours} hours)")
        
        retry_count = 0
        self.running = True

        while self.running:
            try:
                # Fetch new items since last check
                logger.debug("Polling for new Message Center items...")
                raw_items = await self.mc.fetch_since()

                if raw_items:
                    logger.info(f"Found {len(raw_items)} new item(s)")
                    retry_count = 0  # Reset retry counter on success

                    for item in raw_items:
                        await self._process_item(item, skip_if_processed=True, source="live")
                else:
                    logger.debug("No new items at this check")

                # Wait before next poll
                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

            except Exception as e:
                retry_count += 1
                logger.error(f"Error in monitoring loop (attempt {retry_count}/{self.MAX_RETRIES}): {e}")

                if retry_count >= self.MAX_RETRIES:
                    logger.error("Max retries reached - stopping orchestrator")
                    self.running = False
                else:
                    logger.info(f"Retrying in {self.RETRY_DELAY_SECONDS}s...")
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)

    async def _process_item(self, raw_item: dict, skip_if_processed: bool = True, source: str = "live"):
        """Process a single raw Message Center item"""
        try:
            item_id = raw_item.get('id')
            title = raw_item.get('title', 'Unknown')

            # Skip if already processed
            if skip_if_processed and item_id in self.processed_ids:
                logger.debug(f"Item already processed: {item_id}")
                return

            logger.info(f"Processing {source} item: {title[:60]}")

            # Get report date for AI enrichment
            report_date = datetime.fromisoformat(
                raw_item.get('startDateTime', datetime.now(timezone.utc).isoformat()).replace('Z', '+00:00')
            )

            # AI Enrichment - analyze with system prompt
            logger.debug("Enriching with AI analysis...")
            enriched = await self.ai.enrich_item(raw_item, report_date)

            # Build Adaptive Card for Teams
            logger.debug("Building Adaptive Card...")
            card = AdaptiveCardBuilder.build_card(enriched, include_link=True)

            # Send to Teams immediately (if connected)
            if self.tm:
                logger.debug("Sending to Teams...")
                success = await self.tm.send_raw_card(card)
                if success:
                    logger.info(f"Sent to Teams: {title[:60]}")
                else:
                    logger.warning(f"Failed to send to Teams: {title[:60]}")
            else:
                logger.info(f"Ready (not sent to Teams): {title[:60]}")

            # Mark as processed
            self.processed_ids.add(item_id)
            logger.debug(f"Item processed: {item_id}")

        except Exception as e:
            logger.error(f"Error processing item: {e}")

    def _get_timezone(self):
        """Resolve timezone from settings, fallback to UTC."""
        tz_name = settings.timezone
        try:
            return ZoneInfo(tz_name)
        except Exception:
            logger.warning(f"Invalid TIMEZONE '{tz_name}', defaulting to UTC")
            return timezone.utc

    @staticmethod
    def _parse_time_string(time_str: str):
        """Parse HH:MM[:SS] time string with fallback."""
        try:
            parts = [int(p) for p in time_str.strip().split(":")]
            if len(parts) < 2:
                raise ValueError("Time must be HH:MM or HH:MM:SS")
            hour, minute = parts[0], parts[1]
            second = parts[2] if len(parts) > 2 else 0
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                raise ValueError("Time values out of range")
            return hour, minute, second
        except Exception:
            logger.warning(f"Invalid DAILY_BRIEF_TIME '{time_str}', defaulting to 09:00")
            return 9, 0, 0

    def _next_daily_run(self, tzinfo):
        """Get next scheduled daily brief time."""
        hour, minute, second = self._parse_time_string(settings.daily_brief_time)
        now = datetime.now(tzinfo)
        next_run = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run

    async def daily_brief_loop(self):
        """Daily brief scheduler loop."""
        tzinfo = self._get_timezone()
        while self.running:
            next_run = self._next_daily_run(tzinfo)
            sleep_seconds = max(0, (next_run - datetime.now(tzinfo)).total_seconds())
            logger.info(f"Next daily brief scheduled at {next_run.isoformat()}")
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                return
            if not self.running:
                return
            await self._run_daily_brief()

    async def _run_daily_brief(self):
        """Send a daily brief for the last 24 hours."""
        if not self.mc:
            logger.warning("Daily brief skipped: Message Center not initialized")
            return

        logger.info(f"Running daily brief for last {self.daily_brief_lookback_hours} hours")
        try:
            raw_items = await self.mc.fetch_recent(hours_back=self.daily_brief_lookback_hours)
        except Exception as e:
            logger.error(f"Daily brief fetch failed: {e}")
            return

        if not raw_items:
            logger.info("Daily brief: no announcements in last 24 hours")
            return

        def _item_ts(raw_item: dict) -> datetime:
            value = raw_item.get('lastModifiedDateTime') or raw_item.get('startDateTime')
            if not value:
                return datetime.min.replace(tzinfo=timezone.utc)
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except Exception:
                return datetime.min.replace(tzinfo=timezone.utc)

        raw_items.sort(key=_item_ts, reverse=True)

        for item in raw_items:
            await self._process_item(item, skip_if_processed=False, source="daily")

    async def close(self):
        """Clean up resources"""
        try:
            self.running = False
            logger.info("Closing orchestrator...")

            if self.mc:
                await self.mc.close()
            if self.tm:
                await self.tm.close()

            logger.info("Orchestrator closed successfully")
        except Exception as e:
            logger.error(f"Error closing orchestrator: {e}")


async def signal_handler(orchestrator: LiveBriefOrchestrator):
    """Handle shutdown signals gracefully"""
    logger.info("Shutdown signal received")
    await orchestrator.close()


async def main():
    """Main entry point"""
    orchestrator = LiveBriefOrchestrator()

    # Register signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(signal_handler(orchestrator))
            )
        except NotImplementedError:
            # Windows event loop doesn't support add_signal_handler
            signal.signal(sig, lambda *_: asyncio.create_task(signal_handler(orchestrator)))

    try:
        # Initialize all components
        if not await orchestrator.initialize():
            logger.error("Failed to initialize - exiting")
            return False

        # Start monitoring loop and daily brief scheduler
        orchestrator.running = True
        monitor_task = asyncio.create_task(orchestrator.monitor_loop())
        daily_task = asyncio.create_task(orchestrator.daily_brief_loop())

        done, pending = await asyncio.wait(
            {monitor_task, daily_task},
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            if task.exception():
                raise task.exception()

        logger.info("Orchestrator finished")
        return True

    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        return False

    finally:
        # Always close resources
        for task in ("monitor_task", "daily_task"):
            current = locals().get(task)
            if current and not current.done():
                current.cancel()
        await orchestrator.close()


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("Microsoft Message Center Monitor - Live Monitor Started")
    logger.info("=" * 80)

    result = asyncio.run(main())

    logger.info("=" * 80)
    logger.info(f"Microsoft Message Center Monitor - Stopped (Result: {result})")
    logger.info("=" * 80)

    exit(0 if result else 1)

