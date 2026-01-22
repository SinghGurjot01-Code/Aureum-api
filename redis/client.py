# redis/client.py
import os
import logging
from typing import Optional

log = logging.getLogger("redis.client")

_redis_client = None


async def get_redis_client() -> Optional["Redis"]:
    """
    Returns an async Redis client or None.
    Never crashes the app.
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        log.warning("REDIS_URL not set. Redis disabled.")
        return None

    try:
        import redis.asyncio as redis

        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )

        # Connection test (ONLY reliable check)
        await client.ping()

        _redis_client = client
        log.info("Redis connected successfully")
        return _redis_client

    except Exception as e:
        log.error(f"Redis connection failed: {e}")
        return None
