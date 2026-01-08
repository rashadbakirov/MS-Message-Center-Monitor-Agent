"""
Service Health Enricher - Uses Azure OpenAI to enrich Service Health issues with analysis
Produces structured, detailed incident summaries with recommendations
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class ServiceHealthEnricher:
    """Enriches raw Service Health issues with AI analysis using Azure OpenAI"""

    SYSTEM_PROMPT = """You are an expert Microsoft 365 service health analyst. Given raw Service Health incident records,
produce a compact JSON object with enriched, human-ready cards. Keep outputs accurate, concise, and operationally useful.

Rules:
- Strict JSON only in your final output: {"items":[ ... ]}
- Always return bucket as "action" or "info"; never null.
- severity must be one of ["critical","high","important","normal"] inferred from status, impact, and text.
- chips: include "Service Health", status, classification, feature, and impacted services if present.
- what: 3-6 sentences, clear and precise. Explain what is happening and current state.
- why: 2-4 sentences focused on customer/admin impact and scope.
- actions: 3-6 admin recommendations. Use concrete steps based on the text; if missing, suggest standard incident response steps.
- latest_update: 1-3 sentences summarizing the most recent post/update.
- window: human-friendly timeline using start/end/last updated. Example: "Started Sep 12, 2025 | Last updated Sep 13, 2025".
- countdown: compute relative to report_date if end time is present ("in ~35 days", "today", "2 days ago").
- Use facts from the record; do not invent root cause or resolution details.
- Always include these fields in each item:
  title, service, bucket, severity, chips, what, why, actions, status, impact, latest_update,
  window, countdown, link, issue_id, published, last_updated, affected_services.
  Use null or empty values if unknown."""

    def __init__(self, endpoint: str, api_key: str, deployment: str, api_version: str = "2024-10-01-preview"):
        """
        Initialize Service Health Enricher with Azure OpenAI credentials

        Args:
            endpoint: Azure OpenAI endpoint URL
            api_key: Azure OpenAI API key
            deployment: Deployment name (e.g., 'gpt-4o')
            api_version: Azure OpenAI API version
        """
        self.client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
        )
        self.deployment = deployment
        logger.info(f"ServiceHealthEnricher initialized with deployment: {deployment}")

    async def enrich_item(self, item: Dict[str, Any], report_date: str = None) -> Optional[Dict[str, Any]]:
        """
        Enrich a single Service Health issue with AI analysis

        Args:
            item: Raw service health issue dictionary
            report_date: Report date for countdown calculation (YYYY-MM-DD format)

        Returns:
            Enriched item with structured analysis or None if processing fails
        """
        try:
            if report_date is None:
                report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            posts_summary = self._summarize_posts(item.get("posts", []))

            user_prompt = f"""
{{
  "report_date": "{report_date}",
  "items": [{{
    "issue_id": "{item.get('id', '')}",
    "title": "{self._escape_json(item.get('title', ''))}",
    "service": "{self._escape_json(item.get('service', ''))}",
    "feature": "{self._escape_json(item.get('feature', ''))}",
    "status": "{self._escape_json(item.get('status', ''))}",
    "classification": "{self._escape_json(item.get('classification', ''))}",
    "severity_raw": "{self._escape_json(item.get('severity', ''))}",
    "impact_description": "{self._escape_json(item.get('impactDescription', ''))}",
    "affected_services": "{self._escape_json(item.get('impactedServices', item.get('affectedServices', '')))}",
    "start_date": "{item.get('startDateTime', '')}",
    "end_date": "{item.get('endDateTime', '')}",
    "last_updated": "{item.get('lastModifiedDateTime', item.get('lastUpdateDateTime', ''))}",
    "latest_posts": "{self._escape_json(posts_summary)}"
  }}]
}}
"""

            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1800,
                response_format={"type": "json_object"},
            )

            response_text = response.choices[0].message.content
            parsed = json.loads(response_text)

            if parsed.get("items") and len(parsed["items"]) > 0:
                enriched_item = parsed["items"][0]
                enriched_item["issue_id"] = item.get("id", enriched_item.get("issue_id", ""))
                logger.debug(f"Enriched service health item: {enriched_item.get('title', 'Unknown')}")
                return enriched_item

            logger.warning(f"No items in service health AI response for {item.get('title', 'Unknown')}")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse service health AI response JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error enriching service health item {item.get('title', 'Unknown')}: {e}")
            return None

    async def enrich(self, item: Dict[str, Any], report_date: str = None) -> Optional[Dict[str, Any]]:
        """Convenience method - alias for enrich_item()"""
        return await self.enrich_item(item, report_date)

    @staticmethod
    def _summarize_posts(posts: List[Dict[str, Any]], max_posts: int = 3) -> str:
        """Build a compact summary from recent posts."""
        if not posts:
            return ""
        try:
            sorted_posts = sorted(
                posts,
                key=lambda p: p.get("createdDateTime") or p.get("lastModifiedDateTime") or "",
            )
            selected = sorted_posts[-max_posts:]
        except Exception:
            selected = posts[-max_posts:]

        lines = []
        for post in selected:
            created = post.get("createdDateTime") or post.get("lastModifiedDateTime") or ""
            post_type = post.get("postType") or post.get("type") or ""
            description = post.get("description") or post.get("body", "")
            description = ServiceHealthEnricher._truncate_text(str(description), 600)
            parts = [p for p in [created, post_type] if p]
            header = " - ".join(parts) if parts else "Update"
            lines.append(f"{header}: {description}")

        return " | ".join(lines)

    @staticmethod
    def _escape_json(text: str) -> str:
        """Escape text for JSON embedding"""
        if not text:
            return ""
        text = str(text)
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        text = text.replace("\n", "\\n")
        text = text.replace("\r", "\\r")
        text = text.replace("\t", "\\t")
        return text

    @staticmethod
    def _truncate_text(text: str, max_length: int = 1000) -> str:
        """Truncate text to max length"""
        if not text:
            return ""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
