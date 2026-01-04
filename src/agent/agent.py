"""
Main agent module - Entry point for Microsoft Message Center Monitor
Connects to Microsoft Foundry for AI-powered brief generation
"""

import asyncio
import logging
import os
from typing import Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI

from .config import settings

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_agent():
    """
    Create and initialize the Microsoft Message Center Monitor with Microsoft Foundry.
    
    Uses OpenAI SDK with Foundry's OpenAI-compatible endpoint.
    
    Returns:
        AsyncOpenAI: Configured client ready for API calls
        
    Raises:
        ValueError: If Foundry configuration is missing
    """
    logger.info("Microsoft Message Center Monitor initializing...")
    
    # Validate required configuration
    if not settings.foundry_openai_endpoint:
        raise ValueError("FOUNDRY_OPENAI_ENDPOINT is not set in .env file")
    if not settings.foundry_api_key:
        raise ValueError("FOUNDRY_API_KEY is not set in .env file")
    if not settings.foundry_model_deployment:
        raise ValueError("FOUNDRY_MODEL_DEPLOYMENT is not set in .env file")
    
    logger.info(f"Connecting to Foundry: {settings.foundry_openai_endpoint}")
    logger.info(f"Using model: {settings.foundry_model_deployment}")
    
    try:
        # Create OpenAI client with Foundry endpoint
        client = AsyncOpenAI(
            base_url=settings.foundry_openai_endpoint,
            api_key=settings.foundry_api_key
        )
        
        logger.info("Foundry client initialized successfully")
        return client
        
    except Exception as e:
        logger.error(f"Failed to create agent: {e}", exc_info=True)
        raise RuntimeError(f"Failed to initialize Microsoft Message Center Monitor: {e}") from e


async def generate_brief(client: AsyncOpenAI, prompt: str) -> str:
    """
    Generate a brief using the Foundry GPT-4o model.
    
    Args:
        client: AsyncOpenAI client configured for Foundry
        prompt: User prompt/instruction for the brief
        
    Returns:
        str: Generated brief text
    """
    try:
        response = await client.chat.completions.create(
            model=settings.foundry_model_deployment,
            messages=[
                {
                    "role": "system",
                    "content": _get_system_prompt()
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=settings.ai_temperature,
            max_tokens=settings.ai_max_tokens,
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Failed to generate brief: {e}", exc_info=True)
        raise


def _get_system_prompt() -> str:
    """
    Get the system prompt for the Microsoft Message Center Monitor.
    
    Returns:
        str: System prompt for the LLM
    """
    return """You are Microsoft Message Center Monitor, an intelligent assistant that aggregates and summarizes 
Microsoft announcements from Message Center and Product Roadmap.

Your responsibilities:
1. Analyze Microsoft announcements and roadmap updates
2. Remove duplicate information and filter for relevance
3. Categorize items as: Breaking Changes, New Features, Deprecations, or Updates
4. Assess business impact (High, Medium, Low) for SMB customers
5. Generate concise 2-3 key items with clear reasoning
6. Provide links to official documentation

Format your brief in a structured way with:
- Item Title
- Category (Breaking Change / New Feature / Deprecation / Update)
- Business Impact Level
- Summary (1-2 sentences)
- Relevant Links
- Reasoning (why this matters to SMBs)

Be concise, professional, and business-focused. Avoid technical jargon when possible."""


async def test_agent():
    """
    Test the agent connection and functionality.
    Useful for debugging and verifying setup.
    """
    logger.info("Starting agent connection test...")
    try:
        client = await create_agent()
        
        # Simple test query
        test_prompt = "Hello! Are you ready to generate Microsoft briefs?"
        logger.info(f"Sending test prompt: {test_prompt}")
        
        response = await generate_brief(client, test_prompt)
        
        logger.info("Agent response:")
        print("---")
        print(response)
        print("---")
        
        logger.info("Agent test successful!")
        return True
        
    except Exception as e:
        logger.error(f"Agent test failed: {e}", exc_info=True)
        return False


async def main():
    """Main entry point for the agent."""
    logger.info("=" * 60)
    logger.info("Microsoft Message Center Monitor - Starting up")
    logger.info("=" * 60)
    
    try:
        client = await create_agent()
        
        # Test the agent if in debug mode
        if settings.debug:
            logger.info("Debug mode enabled - running test...")
            await test_agent()
        
        logger.info("Microsoft Message Center Monitor started successfully")
        logger.info("Ready to generate Microsoft briefs!")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
