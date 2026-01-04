#!/usr/bin/env python3
"""
One-shot GitHub Actions run:
- Fetch Message Center items updated in the last N hours
- Enrich with Azure OpenAI
- Send one card per new item to Teams
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Set

from src.agent.config import Settings
from src.agent.tools.message_center import MessageCenterTool
from src.agent.tools.ai_enricher import AIEnricher
from src.connectors.adaptive_card_builder import AdaptiveCardBuilder
from src.agent.tools.teams_connector import TeamsConnector


STATE_FILE = Path("data/gh_sent_ids.json")


def _load_sent_ids() -> Set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("sent_ids", []))
    except Exception:
        return set()


def _save_sent_ids(sent_ids: Set[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sent_ids": sorted(sent_ids),
        "last_run_utc": datetime.now(timezone.utc).isoformat(),
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _item_timestamp(item: Dict[str, Any]) -> datetime:
    value = item.get("lastModifiedDateTime") or item.get("startDateTime")
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _notify_on_empty() -> bool:
    value = os.getenv("NOTIFY_ON_EMPTY", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _no_news_card(lookback_hours: int) -> Dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "Microsoft Message Center Monitor",
                "size": "Large",
                "weight": "Bolder",
            },
            {
                "type": "TextBlock",
                "text": f"No new Message Center announcements as of {timestamp}.",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"Lookback window: last {lookback_hours} hours.",
                "isSubtle": True,
                "size": "Small",
                "wrap": True,
            },
        ],
    }


async def _send_no_news(settings: Settings, lookback_hours: int) -> None:
    tm = TeamsConnector(webhook_url=settings.teams_webhook_url)
    if not await tm.connect():
        print("Failed to connect to Teams")
        return
    await tm.send_raw_card(_no_news_card(lookback_hours))
    await tm.close()


async def main() -> int:
    settings = Settings()
    lookback_hours = settings.daily_brief_lookback_hours
    notify_on_empty = _notify_on_empty()

    mc = MessageCenterTool(
        tenant_id=settings.azure_tenant_id,
        app_id=settings.mc_app_id,
        client_secret=settings.mc_client_secret,
    )
    if not await mc.connect():
        print("Failed to connect to Message Center")
        return 1

    items = await mc.fetch_recent(hours_back=lookback_hours)
    await mc.close()

    if not items:
        print("No recent items")
        if notify_on_empty:
            await _send_no_news(settings, lookback_hours)
        _save_sent_ids(_load_sent_ids())
        return 0

    items.sort(key=_item_timestamp, reverse=True)
    sent_ids = _load_sent_ids()
    new_items = [
        item for item in items
        if item.get("id") and item.get("id") not in sent_ids
    ]
    if not new_items:
        print("No new items since last run")
        if notify_on_empty:
            await _send_no_news(settings, lookback_hours)
        _save_sent_ids(sent_ids)
        return 0

    ai = AIEnricher(
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        deployment=settings.azure_openai_deployment,
        api_version=settings.azure_openai_api_version,
    )

    tm = TeamsConnector(webhook_url=settings.teams_webhook_url)
    if not await tm.connect():
        print("Failed to connect to Teams")
        return 1

    sent = 0
    for item in new_items:
        item_id = item.get("id")
        if not item_id or item_id in sent_ids:
            continue

        enriched = await ai.enrich(item)
        if not enriched:
            continue

        card = AdaptiveCardBuilder.build_card(enriched)
        if await tm.send_raw_card(card):
            sent_ids.add(item_id)
            sent += 1

    await tm.close()
    _save_sent_ids(sent_ids)
    print(f"Sent {sent} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
