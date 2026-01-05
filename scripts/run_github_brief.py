#!/usr/bin/env python3
"""
One-shot GitHub Actions run:
- Fetch Message Center and Service Health items updated in the last N hours
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
from src.agent.tools.service_health import ServiceHealthTool
from src.agent.tools.service_health_enricher import ServiceHealthEnricher
from src.connectors.adaptive_card_builder import AdaptiveCardBuilder
from src.agent.tools.teams_connector import TeamsConnector


MC_STATE_FILE = Path("data/gh_sent_ids.json")
SH_STATE_FILE = Path("data/gh_service_health_sent_ids.json")


def _load_sent_ids(state_file: Path) -> Set[str]:
    if not state_file.exists():
        return set()
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return set(data.get("sent_ids", []))
    except Exception:
        return set()


def _save_sent_ids(state_file: Path, sent_ids: Set[str]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sent_ids": sorted(sent_ids),
        "last_run_utc": datetime.now(timezone.utc).isoformat(),
    }
    state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
                "text": "Microsoft 365 Updates Monitor",
                "size": "Large",
                "weight": "Bolder",
            },
            {
                "type": "TextBlock",
                "text": f"No new Message Center or Service Health updates as of {timestamp}.",
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


def _apply_alert_indicator(enriched: Dict[str, Any], settings: Settings) -> None:
    alert_url = getattr(settings, "critical_alert_image_url", "")
    if not alert_url:
        return
    severity = str(enriched.get("severity", "")).lower()
    if severity in {"critical", "high"}:
        enriched.setdefault("alert_image_url", alert_url)


def _apply_message_center_defaults(enriched: Dict[str, Any], settings: Settings) -> None:
    enriched.setdefault("source", "message_center")
    enriched.setdefault("source_label", "Message Center")
    _apply_alert_indicator(enriched, settings)


def _apply_service_health_defaults(enriched: Dict[str, Any], raw_item: Dict[str, Any], settings: Settings) -> None:
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
    _apply_alert_indicator(enriched, settings)


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

    sh = ServiceHealthTool(
        tenant_id=settings.azure_tenant_id,
        app_id=settings.mc_app_id,
        client_secret=settings.mc_client_secret,
    )
    sh_connected = await sh.connect()
    if not sh_connected:
        print("Failed to connect to Service Health (continuing with Message Center only)")
        sh = None

    mc_items = await mc.fetch_recent(hours_back=lookback_hours)
    await mc.close()

    sh_items: List[Dict[str, Any]] = []
    if sh:
        sh_items = await sh.fetch_recent(hours_back=lookback_hours)
        await sh.close()

    if not mc_items and not sh_items:
        print("No recent items in Message Center or Service Health")
        if notify_on_empty:
            await _send_no_news(settings, lookback_hours)
        _save_sent_ids(MC_STATE_FILE, _load_sent_ids(MC_STATE_FILE))
        _save_sent_ids(SH_STATE_FILE, _load_sent_ids(SH_STATE_FILE))
        return 0

    mc_items.sort(key=_item_timestamp, reverse=True)
    sh_items.sort(key=_item_timestamp, reverse=True)
    mc_sent_ids = _load_sent_ids(MC_STATE_FILE)
    sh_sent_ids = _load_sent_ids(SH_STATE_FILE)
    new_mc_items = [
        item for item in mc_items
        if item.get("id") and item.get("id") not in mc_sent_ids
    ]
    new_sh_items = [
        item for item in sh_items
        if item.get("id") and item.get("id") not in sh_sent_ids
    ]
    if not new_mc_items and not new_sh_items:
        print("No new items since last run")
        if notify_on_empty:
            await _send_no_news(settings, lookback_hours)
        _save_sent_ids(MC_STATE_FILE, mc_sent_ids)
        _save_sent_ids(SH_STATE_FILE, sh_sent_ids)
        return 0

    ai = AIEnricher(
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        deployment=settings.azure_openai_deployment,
        api_version=settings.azure_openai_api_version,
    )
    sh_ai = None
    if new_sh_items:
        sh_ai = ServiceHealthEnricher(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
        )

    tm = TeamsConnector(webhook_url=settings.teams_webhook_url)
    if not await tm.connect():
        print("Failed to connect to Teams")
        return 1

    candidates = [("message_center", item) for item in new_mc_items]
    candidates.extend([("service_health", item) for item in new_sh_items])
    candidates.sort(key=lambda entry: _item_timestamp(entry[1]), reverse=True)

    sent_mc = 0
    sent_sh = 0
    for source, item in candidates:
        item_id = item.get("id")
        if not item_id:
            continue

        if source == "message_center":
            if item_id in mc_sent_ids:
                continue
            enriched = await ai.enrich(item)
            if not enriched:
                continue
            _apply_message_center_defaults(enriched, settings)
            card = AdaptiveCardBuilder.build_card(enriched)
            if await tm.send_raw_card(card):
                mc_sent_ids.add(item_id)
                sent_mc += 1
        else:
            if item_id in sh_sent_ids or sh_ai is None:
                continue
            enriched = await sh_ai.enrich(item)
            if not enriched:
                continue
            _apply_service_health_defaults(enriched, item, settings)
            card = AdaptiveCardBuilder.build_card(enriched)
            if await tm.send_raw_card(card):
                sh_sent_ids.add(item_id)
                sent_sh += 1

    await tm.close()
    _save_sent_ids(MC_STATE_FILE, mc_sent_ids)
    _save_sent_ids(SH_STATE_FILE, sh_sent_ids)
    print(f"Sent {sent_mc + sent_sh} cards (Message Center: {sent_mc}, Service Health: {sent_sh})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
