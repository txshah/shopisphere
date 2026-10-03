"""Jerry the mouse agent (Claude SDK)."""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from characters import generate_jerry_prompt

from band import Agent, configure_logging
from band.adapters import ClaudeSDKAdapter, ClaudeSDKAdapterConfig
from band.core.types import Emit

configure_logging(
    logging.INFO,
    extra_loggers={
        "band_claude_sdk_agent": logging.INFO,
        "session_manager": logging.INFO,
    },
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run Jerry the mouse agent."""
    load_dotenv()

    adapter = ClaudeSDKAdapter(
        ClaudeSDKAdapterConfig(custom_section=generate_jerry_prompt("Jerry")),
        emit=Emit.TOOL_CALLS | Emit.THOUGHTS,
    )

    agent = Agent.from_config(
        "jerry_agent",
        adapter=adapter,
    )

    logger.info("Jerry is cozy in his hole, watching for Tom...")
    logger.info("Agent ID: %s", agent.runtime.agent_id)
    logger.info("Press Ctrl+C to stop")

    try:
        async with agent:
            await agent.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
