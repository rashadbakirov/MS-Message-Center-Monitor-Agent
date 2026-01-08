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
from src.agent.tools.service_health import ServiceHealthTool
from src.agent.tools.service_health_enricher import ServiceHealthEnricher
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
        self.sh: ServiceHealthTool = None
        self.sh_ai: ServiceHealthEnricher = None
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

            # Initialize Service Health Tool
            self.sh = ServiceHealthTool(
                settings.azure_tenant_id,
                settings.mc_app_id,
                settings.mc_client_secret
            )
            if not await self.sh.connect():
                logger.warning("Failed to connect to Service Health API - continuing with Message Center only")
                self.sh = None
            else:
                logger.info("Service Health connected")

            # Initialize AI Enricher
            self.ai = AIEnricher(
                endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                deployment=settings.azure_openai_deployment,
                api_version=settings.azure_openai_api_version
            )
            logger.info("AI Enricher initialized")

            if self.sh:
                self.sh_ai = ServiceHealthEnricher(
                    endpoint=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_api_key,
                    deployment=settings.azure_openai_deployment,
                    api_version=settings.azure_openai_api_version
                )
                logger.info("Service Health Enricher initialized")

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
                logger.debug("Polling for new Message Center and Service Health items...")
                mc_items = await self.mc.fetch_since()
                sh_items = await self.sh.fetch_since() if self.sh else []

                if mc_items or sh_items:
                    logger.info(
                        f"Found {len(mc_items)} Message Center and {len(sh_items)} Service Health item(s)"
                    )
                    retry_count = 0  # Reset retry counter on success

                    for item in mc_items:
                        await self._process_item(
                            item,
                            item_source="message_center",
                            skip_if_processed=True,
                            run_source="live"
                        )
                    for item in sh_items:
                        await self._process_item(
                            item,
                            item_source="service_health",
                            skip_if_processed=True,
                            run_source="live"
                        )
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

    async def _process_item(
        self,
        raw_item: dict,
        item_source: str,
        skip_if_processed: bool = True,
        run_source: str = "live"
    ):
        """Process a single raw item"""
        try:
            item_id = raw_item.get("id")
            title = raw_item.get("title", "Unknown")
            dedupe_key = f"{item_source}:{item_id}"

            # Skip if already processed
            if skip_if_processed and dedupe_key in self.processed_ids:
                logger.debug(f"Item already processed: {dedupe_key}")
                return

            logger.info(f"Processing {run_source} {item_source} item: {title[:60]}")

            report_date = self._get_report_date(raw_item)

            logger.debug("Enriching with AI analysis...")
            if item_source == "service_health":
                if not self.sh_ai:
                    logger.warning("Service Health enricher not initialized - skipping item")
                    return
                enriched = await self.sh_ai.enrich_item(raw_item, report_date)
                if not enriched:
                    return
                self._apply_service_health_defaults(enriched, raw_item)
            else:
                enriched = await self.ai.enrich_item(raw_item, report_date)
                if not enriched:
                    return
                self._apply_message_center_defaults(enriched)

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
            self.processed_ids.add(dedupe_key)
            logger.debug(f"Item processed: {dedupe_key}")

        except Exception as e:
            logger.error(f"Error processing item: {e}")

    @staticmethod
    def _get_report_date(raw_item: dict) -> datetime:
        """Resolve report date for AI enrichment."""
        value = raw_item.get("lastModifiedDateTime") or raw_item.get("startDateTime")
        if not value:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

    def _apply_alert_indicator(self, enriched: dict) -> None:
        alert_url = settings.critical_alert_image_url
        if not alert_url:
            return
        severity = str(enriched.get("severity", "")).lower()
        if severity in {"critical", "high"}:
            enriched.setdefault("alert_image_url", alert_url)

    def _apply_message_center_defaults(self, enriched: dict) -> None:
        enriched.setdefault("source", "message_center")
        enriched.setdefault("source_label", "Message Center")
        self._apply_alert_indicator(enriched)

    def _apply_service_health_defaults(self, enriched: dict, raw_item: dict) -> None:
        enriched.setdefault("source", "service_health")
        enriched.setdefault("source_label", "Service Health")
        enriched.setdefault("issue_id", raw_item.get("id"))
        enriched.setdefault("published", raw_item.get("startDateTime"))
        enriched.setdefault("last_updated", raw_item.get("lastModifiedDateTime"))
        if not enriched.get("affected_services"):
            impacted = raw_item.get("impactedServices") or raw_item.get("affectedServices")
            if impacted:
                enriched["affected_services"] = impacted
        if not enriched.get("link"):
            enriched["link"] = settings.service_health_portal_url
        self._apply_alert_indicator(enriched)

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
        if not self.mc and not self.sh:
            logger.warning("Daily brief skipped: Message Center and Service Health not initialized")
            return

        logger.info(f"Running daily brief for last {self.daily_brief_lookback_hours} hours")

        mc_items = []
        sh_items = []
        if self.mc:
            try:
                mc_items = await self.mc.fetch_recent(hours_back=self.daily_brief_lookback_hours)
            except Exception as e:
                logger.error(f"Daily brief fetch failed for Message Center: {e}")
        if self.sh:
            try:
                sh_items = await self.sh.fetch_recent(hours_back=self.daily_brief_lookback_hours)
            except Exception as e:
                logger.error(f"Daily brief fetch failed for Service Health: {e}")

        if not mc_items and not sh_items:
            logger.info("Daily brief: no updates in last 24 hours")
            return

        combined = [("message_center", item) for item in mc_items]
        combined.extend([("service_health", item) for item in sh_items])
        combined.sort(key=lambda entry: self._get_report_date(entry[1]), reverse=True)

        for item_source, item in combined:
            await self._process_item(
                item,
                item_source=item_source,
                skip_if_processed=False,
                run_source="daily"
            )

    async def close(self):
        """Clean up resources"""
        try:
            self.running = False
            logger.info("Closing orchestrator...")

            if self.mc:
                await self.mc.close()
            if self.sh:
                await self.sh.close()
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

