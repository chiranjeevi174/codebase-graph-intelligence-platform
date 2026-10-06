#!/usr/bin/env python3
"""Smoke test for validating live OpenAI LLM provider integration.

Run with:
    uv run python scripts/test_openai_smoke.py
"""

import sys
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import get_settings
from app.llm.factory import get_llm
from app.llm.openai_provider import OpenAIProvider
from app.utils.logger import logger


def run_openai_smoke_test():
    """Execute minimal synchronous and asynchronous requests against OpenAI API."""
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY

    if not api_key or api_key.startswith("your-"):
        logger.warning("[SmokeTest:Skipped] OPENAI_API_KEY is not configured in .env.")
        print("SKIPPED: OPENAI_API_KEY is not set.")
        return False

    print(f"Initializing OpenAIProvider with model '{settings.OPENAI_MODEL}'...")
    provider = get_llm(provider="openai")
    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "openai"

    print("Executing synchronous generate()...")
    sync_response = provider.generate(
        prompt="Reply with exactly the word 'OK'.",
        temperature=0.0,
        max_tokens=10,
    )
    print(f"Sync Response: '{sync_response.strip()}'")
    assert len(sync_response.strip()) > 0

    print("Executing asynchronous agenerate()...")
    async_response = asyncio.run(
        provider.agenerate(
            prompt="Reply with exactly the word 'OK'.",
            temperature=0.0,
            max_tokens=10,
        )
    )
    print(f"Async Response: '{async_response.strip()}'")
    assert len(async_response.strip()) > 0

    print("[SUCCESS] OpenAI Live Smoke Test Passed Successfully!")
    return True


if __name__ == "__main__":
    try:
        success = run_openai_smoke_test()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[FAILED] OpenAI Smoke Test Failed: {e}")
        sys.exit(1)
