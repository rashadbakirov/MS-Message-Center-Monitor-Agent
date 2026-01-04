"""
Adaptive Card Builder - Converts enriched AI items to Teams Adaptive Cards
Produces beautiful, interactive cards for Teams channels
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AdaptiveCardBuilder:
    """Builds Teams Adaptive Cards from enriched AI-analyzed items"""

    # Color mapping for severity
    SEVERITY_COLORS = {
        "critical": "#D13438",      # Red
        "high": "#D93B27",          # Orange-Red
        "important": "#FFB900",     # Amber
        "normal": "#6E8387"         # Gray
    }

    SEVERITY_ICONS = {
        "critical": "⚠️",
        "high": "⚠️",
        "important": "ℹ️",
        "normal": "📢"
    }

    @staticmethod
    def _build_message_center_link(message_id: Optional[str]) -> Optional[str]:
        """Build a Message Center deep link from a message ID."""
        if not message_id:
            return None
        message_id = str(message_id).strip()
        if not message_id.upper().startswith("MC"):
            return None
        return f"https://admin.microsoft.com/Adminportal/Home#/MessageCenter/:/messages/{message_id}"

    @staticmethod
    def _format_friendly_datetime(value: Optional[str]) -> Optional[str]:
        """Format ISO datetime to a friendly date (UTC)."""
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            return dt.astimezone(timezone.utc).strftime("%d %B %Y")
        except Exception:
            return None

    @staticmethod
    def build_card(item: Dict[str, Any], include_link: bool = True) -> Dict[str, Any]:
        """
        Build a single Adaptive Card from enriched item
        
        Args:
            item: Enriched item from AI analysis
            include_link: Whether to include link to Message Center
            
        Returns:
            Adaptive Card JSON object
        """
        try:
            severity = item.get("severity", "normal").lower()
            bucket = item.get("bucket", "info")
            is_major = item.get("is_major_change", False)
            admin_impact = item.get("admin_impact", False)

            # Determine color and icon
            color = AdaptiveCardBuilder.SEVERITY_COLORS.get(severity, "#6E8387")
            icon = AdaptiveCardBuilder.SEVERITY_ICONS.get(severity, "📢")

            # Build chips/tags
            chips = item.get("chips", [])
            has_admin_chip = False
            if isinstance(chips, list):
                has_admin_chip = any(
                    (c.get("text", "").lower() == "admin impact") if isinstance(c, dict) else str(c).lower() == "admin impact"
                    for c in chips
                )
            highlight = bool(is_major or admin_impact or has_admin_chip)
            if isinstance(chips, list) and len(chips) > 0:
                chip_text = " | ".join([c.get("text", c) if isinstance(c, dict) else str(c) for c in chips])
            else:
                chip_text = ""

            # Build actions list
            actions = item.get("actions", [])
            if isinstance(actions, str):
                actions = [actions]

            # Resolve Message Center link
            link = item.get("link")
            if include_link and not link:
                link = AdaptiveCardBuilder._build_message_center_link(
                    item.get("message_id") or item.get("id")
                )

            # Build the card
            card = {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    # Header with title and severity indicator
                    {
                        "type": "Container",
                        "style": "attention" if highlight else "emphasis",
                        "items": [
                            {
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "width": "auto",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": icon,
                                                "size": "extraLarge",
                                                "spacing": "none"
                                            }
                                        ]
                                    },
                                    {
                                        "width": "stretch",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": item.get("title", "Microsoft 365 Update"),
                                                "size": "large",
                                                "weight": "bolder",
                                                "wrap": True,
                                                "spacing": "small"
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": item.get("service", "Microsoft 365"),
                                                "size": "small",
                                                "isSubtle": True,
                                                "spacing": "none"
                                            }
                                        ]
                                    },
                                    {
                                        "width": "auto",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": severity.upper(),
                                                "size": "small",
                                                "weight": "bolder",
                                                "color": "attention" if severity in ["critical", "high"] else "default",
                                                "spacing": "none"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }

            # Add chips/tags if present
            if chip_text:
                card["body"].append({
                    "type": "TextBlock",
                    "text": chip_text,
                    "size": "small",
                    "isSubtle": True,
                    "wrap": True,
                    "spacing": "medium"
                })

            # Add main content sections
            card["body"].append({
                "type": "Container",
                "spacing": "medium",
                "items": []
            })

            content_container = card["body"][-1]["items"]

            # What's happening
            if item.get("what"):
                content_container.append({
                    "type": "TextBlock",
                    "text": "**What's happening?**",
                    "weight": "bolder",
                    "size": "small",
                    "spacing": "medium"
                })
                content_container.append({
                    "type": "TextBlock",
                    "text": item.get("what", ""),
                    "wrap": True,
                    "spacing": "small"
                })

            # Why it matters
            if item.get("why"):
                content_container.append({
                    "type": "TextBlock",
                    "text": "**Why it matters?**",
                    "weight": "bolder",
                    "size": "small",
                    "spacing": "medium"
                })
                content_container.append({
                    "type": "TextBlock",
                    "text": item.get("why", ""),
                    "wrap": True,
                    "spacing": "small"
                })

            # Action items
            if actions and len(actions) > 0:
                content_container.append({
                    "type": "TextBlock",
                    "text": "**📋 Recommended Actions:**",
                    "weight": "bolder",
                    "size": "small",
                    "spacing": "medium"
                })
                
                for action in actions[:3]:  # Limit to 3 actions
                    content_container.append({
                        "type": "TextBlock",
                        "text": f"• {action}",
                        "wrap": True,
                        "spacing": "small"
                    })

            # Timeline/Window
            if item.get("window"):
                content_container.append({
                    "type": "TextBlock",
                    "text": "**⏰ Timeline:**",
                    "weight": "bolder",
                    "size": "small",
                    "spacing": "medium"
                })
                content_container.append({
                    "type": "TextBlock",
                    "text": item.get("window", ""),
                    "wrap": True,
                    "spacing": "small"
                })

            # Countdown if available
            if item.get("countdown"):
                content_container.append({
                    "type": "TextBlock",
                    "text": f"*{item.get('countdown')}*",
                    "isSubtle": True,
                    "size": "small",
                    "wrap": True,
                    "spacing": "small"
                })

            # Published date (friendly)
            published_raw = item.get("published")
            published_fmt = AdaptiveCardBuilder._format_friendly_datetime(published_raw)
            if published_fmt:
                content_container.append({
                    "type": "TextBlock",
                    "text": f"Published: {published_fmt}",
                    "isSubtle": True,
                    "size": "small",
                    "wrap": True,
                    "spacing": "small"
                })

            # Add separator
            card["body"].append({
                "type": "Container",
                "separator": True,
                "spacing": "medium"
            })

            # Action buttons
            actions_list = []

            # Message Center link
            if include_link and link:
                actions_list.append({
                    "type": "Action.OpenUrl",
                    "title": "View in Message Center",
                    "url": link
                })

            card["actions"] = actions_list if actions_list else []

            logger.debug(f"Built Adaptive Card for: {item.get('title', 'Unknown')[:50]}")
            return card

        except Exception as e:
            logger.error(f"Error building Adaptive Card: {e}")
            return AdaptiveCardBuilder._build_error_card(str(e))

    @staticmethod
    def build_batch(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Build cards for multiple items
        
        Args:
            items: List of enriched items
            
        Returns:
            List of Adaptive Card JSON objects
        """
        cards = []
        for item in items:
            card = AdaptiveCardBuilder.build_card(item)
            cards.append(card)
        return cards

    @staticmethod
    def _build_error_card(error_message: str) -> Dict[str, Any]:
        """Build a card for error display"""
        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "⚠️ Error Processing Update",
                    "size": "large",
                    "weight": "bolder",
                    "color": "attention"
                },
                {
                    "type": "TextBlock",
                    "text": error_message,
                    "wrap": True,
                    "isSubtle": True
                }
            ]
        }

    @staticmethod
    def wrap_in_message(card: Dict[str, Any], channel_mention: str = None) -> Dict[str, Any]:
        """
        Wrap Adaptive Card in a Teams message object for Power Automate
        
        Args:
            card: The Adaptive Card JSON
            channel_mention: Optional channel mention text
            
        Returns:
            Message object compatible with Power Automate
        """
        message = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": card
                }
            ]
        }
        
        if channel_mention:
            message["body"] = channel_mention
        
        return message
