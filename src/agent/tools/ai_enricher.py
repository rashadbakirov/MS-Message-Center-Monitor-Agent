"""
AI Enricher - Uses Azure OpenAI to enrich Message Center items with analysis
Applies expert system prompt to generate structured, actionable cards
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class AIEnricher:
    """Enriches raw Message Center items with AI analysis using Azure OpenAI"""

    # Expert Microsoft 365 admin system prompt
    SYSTEM_PROMPT = """You are an expert Microsoft 365 admin assistant. Given raw Message Center-like documents, produce a compact JSON object with enriched, human-ready cards that fit a specific HTML template. Keep outputs accurate, concise, and actionable for enterprise admins.

Rules:
- Strict JSON only in your final output: {"items":[ ... ]}
- For each input item, decide bucket:
  - "action" if category is planForChange / preventOrFix / actionRequired OR adminImpact/admin_impact=true OR retirement=true.
  - Otherwise "info".
- Always return bucket as "action" or "info"; never null.
- Determine:
  - is_major_change: true if explicit "Major change", "(Update)" that introduces behavior change, or similar indicator.
  - severity: one of ["critical","high","important","normal"] inferred from text/dates/impact. Be conservative.
  - chips: include category, "Admin impact" if applicable, "Retirement" if applicable, each platform in Platforms, and "Roadmap: <id>" if present.
  - what / why / actions: rewrite into friendly executive summaries. What/Why should be 2-4 sentences each, clear and human-friendly, avoiding jargon. Use the document's facts; do not invent.
  - window: human-friendly text from WindowStart/WindowEnd if present. Use clear phrasing like "Expected in Apr 2026", "Retirement in Apr 2026", "Begins Sep 26, 2025", "Due Oct 17, 2025", or "Sep 26, 2025 - Oct 10, 2025".
  - countdown: compute relative to report_date if WindowEnd is present ("in ~35 days", "today", "2 days ago").
- Do not output confidential URLs; for Message Center link, keep provided deep link if present.
- Preserve MessageId as e.g., "MC123456".
- Title: keep original but remove redundant "(Update)" if it hurts readability; otherwise keep it.
- Service: copy from source if present.
- If Why/Actions are missing in source, propose sensible admin-focused ones based on the text (no hallucinations beyond obvious operational steps).
- Always include these fields in each item: title, service, bucket, is_major_change, severity, chips, what, why, actions, window, countdown, link, message_id, published. Use null or empty values if unknown."""

    def __init__(self, endpoint: str, api_key: str, deployment: str, api_version: str = "2024-10-01-preview"):
        """
        Initialize AI Enricher with Azure OpenAI credentials
        
        Args:
            endpoint: Azure OpenAI endpoint URL
            api_key: Azure OpenAI API key
            deployment: Deployment name (e.g., 'gpt-4o')
            api_version: Azure OpenAI API version
        """
        self.client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key
        )
        self.deployment = deployment
        logger.info(f"AIEnricher initialized with deployment: {deployment}")

    async def enrich_item(self, item: Dict[str, Any], report_date: str = None) -> Optional[Dict[str, Any]]:
        """
        Enrich a single Message Center item with AI analysis
        
        Args:
            item: Raw message center item dictionary
            report_date: Report date for countdown calculation (YYYY-MM-DD format)
            
        Returns:
            Enriched item with structured analysis or None if processing fails
        """
        try:
            if report_date is None:
                report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # Prepare the user prompt with the item data
            user_prompt = f"""
{{
  "report_date": "{report_date}",
  "items": [{{
    "message_id": "{item.get('id', item.get('message_id', ''))}",
    "title": "{self._escape_json(item.get('title', ''))}",
    "service": "{self._escape_json(item.get('service', item.get('affected_services', [''])[0] if item.get('affected_services') else ''))}",
    "category": "{self._escape_json(item.get('category', ''))}",
    "is_major_change": {str(item.get('is_major_change', False)).lower()},
    "severity": "{item.get('severity', 'normal')}",
    "admin_impact": {str(item.get('admin_impact', False)).lower()},
    "retirement": {str(item.get('retirement', False)).lower()},
    "platforms": "{self._escape_json(item.get('platforms', ''))}",
    "roadmap_id": "{item.get('roadmap_id', '')}",
    "summary": "{self._escape_json(self._truncate_text(item.get('summary', item.get('body', '')), 1000))}",
    "why_raw": "{self._escape_json(item.get('why_raw', ''))}",
    "actions_raw": "{self._escape_json(item.get('actions_raw', ''))}",
    "window_start": "{item.get('window_start', '')}",
    "window_end": "{item.get('window_end', '')}",
    "link": "{item.get('link', '')}",
    "published": "{item.get('published', item.get('startDateTime', ''))}",
    "last_updated": "{item.get('last_updated', item.get('lastModifiedDateTime', ''))}"
  }}]
}}
"""

            # Call Azure OpenAI
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Low temperature for consistency
                max_tokens=1500,
                response_format={"type": "json_object"}  # Ensure JSON output
            )

            # Parse response
            response_text = response.choices[0].message.content
            parsed = json.loads(response_text)

            # Return first enriched item
            if parsed.get("items") and len(parsed["items"]) > 0:
                enriched_item = parsed["items"][0]
                # Preserve original ID
                enriched_item["message_id"] = item.get("id", item.get("message_id", ""))
                logger.debug(f"Enriched item: {enriched_item.get('title', 'Unknown')}")
                return enriched_item
            else:
                logger.warning(f"No items in AI response for {item.get('title', 'Unknown')}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error enriching item {item.get('title', 'Unknown')}: {e}")
            return None

    async def enrich_batch(self, items: List[Dict[str, Any]], report_date: str = None) -> List[Dict[str, Any]]:
        """
        Enrich multiple items (processes sequentially to avoid rate limiting)
        
        Args:
            items: List of raw message center items
            report_date: Report date for countdown calculation
            
        Returns:
            List of enriched items
        """
        enriched_items = []
        for i, item in enumerate(items):
            logger.info(f"Enriching item {i+1}/{len(items)}: {item.get('title', 'Unknown')[:50]}...")
            enriched = await self.enrich_item(item, report_date)
            if enriched:
                enriched_items.append(enriched)
            # Rate limiting - wait a bit between API calls
            import asyncio
            await asyncio.sleep(0.5)
        
        logger.info(f"Enriched {len(enriched_items)}/{len(items)} items")
        return enriched_items

    async def enrich(self, item: Dict[str, Any], report_date: str = None) -> Optional[Dict[str, Any]]:
        """
        Convenience method - alias for enrich_item()
        Enrich a single Message Center item with AI analysis
        
        Args:
            item: Raw message center item dictionary
            report_date: Report date for countdown calculation (YYYY-MM-DD format)
            
        Returns:
            Enriched item with structured analysis or None if processing fails
        """
        return await self.enrich_item(item, report_date)

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
