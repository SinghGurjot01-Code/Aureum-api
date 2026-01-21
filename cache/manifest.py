# cache/manifest.py
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from core.ytmusic_client import search_songs
from redis.client import get_redis_client

log = logging.getLogger(__name__)

class CacheManifestGenerator:
    def __init__(self):
        self.redis = None

    async def _get_redis(self):
        if self.redis is None:
            self.redis = await get_redis_client()
        return self.redis

    async def generate(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            must_cache = search_songs("popular music", limit=10)[:5]
            likely_next = []

            redis = await self._get_redis()
            if user_id and redis:
                try:
                    activities = await redis.lrange(f"activity:{user_id}", 0, 4)
                    if activities:
                        hour = datetime.now().hour
                        query = (
                            "morning music" if hour < 12
                            else "afternoon music" if hour < 18
                            else "evening music"
                        )
                        likely_next = search_songs(query, limit=10)
                except:
                    pass

            if not likely_next:
                likely_next = search_songs("trending", limit=10)

            return {
                "must_cache": must_cache,
                "likely_next": likely_next[:10],
                "expires_at": int((datetime.utcnow() + timedelta(hours=24)).timestamp())
            }

        except Exception as e:
            log.error(f"Cache manifest failed: {e}")
            return {
                "must_cache": [],
                "likely_next": [],
                "expires_at": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
            }
