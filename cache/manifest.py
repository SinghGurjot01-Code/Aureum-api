# cache/manifest.py
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from core.ytmusic_client import search_songs
from redis.client import get_redis_client

log = logging.getLogger(__name__)

class CacheManifestGenerator:
    def __init__(self):
        self.redis = get_redis_client()
    
    async def generate(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            must_cache = []
            likely_next = []
            
            # Get popular tracks for must_cache
            popular = search_songs("popular music", limit=10)
            must_cache = popular[:5]
            
            # Get personalized suggestions if user_id
            if user_id and self.redis:
                try:
                    activity_key = f"activity:{user_id}"
                    activities = await self.redis.lrange(activity_key, 0, 4)
                    if activities:
                        # Get trending based on time of day
                        hour = datetime.now().hour
                        if hour < 12:
                            likely_next = search_songs("morning music", limit=10)
                        elif hour < 18:
                            likely_next = search_songs("afternoon music", limit=10)
                        else:
                            likely_next = search_songs("evening music", limit=10)
                except:
                    pass
            
            # Fallback if no personalized suggestions
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