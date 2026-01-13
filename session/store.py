# session/store.py

import logging
import json
from datetime import datetime
from typing import Optional

from redis.client import get_redis_client

log = logging.getLogger("session.store")


class SessionStore:
    async def _redis(self):
        return await get_redis_client()

    async def start_session(self, session_id: str, user_id: Optional[str] = None):
        redis = await self._redis()
        if not redis:
            return

        payload = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        try:
            await redis.set(
                f"session:{session_id}",
                json.dumps(payload),
                ex=86400,  # 24 hours
            )
        except Exception as e:
            log.error(f"start_session failed: {e}")

    async def record_event(
        self,
        session_id: str,
        event_type: str,
        video_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        redis = await self._redis()
        if not redis:
            return

        event = {
            "session_id": session_id,
            "event_type": event_type,
            "video_id": video_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Store event (TTL 7 days)
            await redis.lpush(
                f"events:{session_id}",
                json.dumps(event),
            )
            await redis.ltrim(f"events:{session_id}", 0, 199)
            await redis.expire(f"events:{session_id}", 604800)

            # Optional per-user activity
            if user_id:
                await redis.lpush(
                    f"user_activity:{user_id}",
                    json.dumps(event),
                )
                await redis.ltrim(f"user_activity:{user_id}", 0, 99)
                await redis.expire(f"user_activity:{user_id}", 604800)

        except Exception as e:
            log.error(f"record_event failed: {e}")