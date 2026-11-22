"""
Lightweight async retry decorator (zero-dependency alternative to tenacity)
"""
import asyncio
import functools
import structlog

logger = structlog.get_logger()

def async_retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions=(Exception,)):
    """Async retry decorator with exponential backoff"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error("Function retry exhausted", function=func.__name__, attempts=max_attempts, error=str(e))
                        raise
                    logger.warning(
                        "Function failed, retrying...",
                        function=func.__name__,
                        attempt=attempt,
                        next_delay=current_delay,
                        error=str(e)
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator
