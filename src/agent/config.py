"""
Configuration module - Loads and validates environment variables
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Foundry/Azure AI Configuration
    foundry_project_endpoint: str = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    foundry_openai_endpoint: str = os.getenv("FOUNDRY_OPENAI_ENDPOINT", "")
    foundry_model_deployment: str = os.getenv("FOUNDRY_MODEL_DEPLOYMENT", "gpt-4o")
    foundry_api_key: str = os.getenv("FOUNDRY_API_KEY", "")
    foundry_api_version: str = os.getenv("FOUNDRY_API_VERSION", "2024-05-01-preview")

    # Azure OpenAI Configuration (for AI enrichment)
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")

    # Azure Configuration
    azure_tenant_id: str = os.getenv("AZURE_TENANT_ID", "")
    azure_subscription_id: str = os.getenv("AZURE_SUBSCRIPTION_ID", "")

    # Message Center Configuration (Client Credentials OAuth2)
    mc_app_id: str = os.getenv("MC_APP_ID", "")
    mc_client_secret: str = os.getenv("MC_CLIENT_SECRET", "")
    graph_api_endpoint: str = os.getenv("GRAPH_API_ENDPOINT", "https://graph.microsoft.com/v1.0")

    # Roadmap Configuration
    roadmap_api_url: str = os.getenv("ROADMAP_API_URL", "https://www.microsoft.com/releasecommunications/api/v1/m365")

    # Agent Configuration
    agent_name: str = os.getenv("AGENT_NAME", "Microsoft Message Center Monitor")
    ai_temperature: float = float(os.getenv("AI_TEMPERATURE", "0.3"))
    ai_max_tokens: int = int(os.getenv("AI_MAX_TOKENS", "1000"))

    # Connectors
    teams_webhook_url: Optional[str] = os.getenv("TEAMS_WEBHOOK_URL")
    power_app_api_url: Optional[str] = os.getenv("POWER_APP_API_URL")
    logic_app_trigger_url: Optional[str] = os.getenv("LOGIC_APP_TRIGGER_URL")

    # Scheduling
    daily_brief_time: str = os.getenv("DAILY_BRIEF_TIME", "09:00")
    daily_brief_lookback_hours: int = int(os.getenv("DAILY_BRIEF_LOOKBACK_HOURS", "24"))
    weekly_brief_day: int = int(os.getenv("WEEKLY_BRIEF_DAY", "4"))  # Thursday
    weekly_brief_time: str = os.getenv("WEEKLY_BRIEF_TIME", "09:00")
    timezone: str = os.getenv("TIMEZONE", "America/New_York")

    # Storage
    cosmos_db_endpoint: Optional[str] = os.getenv("COSMOS_DB_ENDPOINT")
    cosmos_db_database: str = os.getenv("COSMOS_DB_DATABASE", "briefs")
    cosmos_db_container: str = os.getenv("COSMOS_DB_CONTAINER", "history")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv("LOG_FORMAT", "console")
    log_file_path: str = os.getenv("LOG_FILE_PATH", "logs/agent.log")

    # Debug
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    dry_run: bool = os.getenv("DRY_RUN", "False").lower() == "true"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields from .env


# Create settings instance
settings = Settings()
