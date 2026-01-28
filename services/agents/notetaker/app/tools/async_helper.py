"""
Helper for running async code in sync context (for CrewAI tools)
"""
import asyncio
from typing import Any, Coroutine
import logging
from app.core import database as db_module

logger = logging.getLogger(__name__)


def run_async(coro: Coroutine) -> Any:
    """
    Run async coroutine in sync context.
    
    This is used by CrewAI tools that need to call async database functions.
    Creates a new event loop if needed (since CrewAI runs in thread pool).
    
    Args:
        coro: Async coroutine to run
    
    Returns:
        Result of the coroutine
    """
    try:
        # CrewAI runs in thread pool, so we need a new event loop
        # Try to get existing loop first
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running loop - need new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            # No event loop, create new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
    except Exception as e:
        logger.error(f"Error running async code: {e}", exc_info=True)
        raise


def get_db_session_sync():
    """
    Get a database session in sync context.
    
    Returns:
        AsyncSession (but usable via run_async)
    """
    if db_module.async_session_maker is None:
        db_module.init_engine()
    # Create a new event loop for this session
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Create session
    session = loop.run_until_complete(db_module.async_session_maker().__aenter__())
    return session, loop
