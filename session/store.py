# session/store.py
import logging
from datetime import datetime
from typing import Optional
from redis.client import get_redis_client

log = logging.getLogger(__name__)

class SessionStore:
    def __init__(self):
        self.redis = get_redis_client()
    
    async def start_session(self, session_id: str, user_id: Optional[str] = None):
        if not self.redis:
            return
        
        try:
            data = {
                "id": session_id,
                "user_id": user_id,
                "created": datetime.utcnow().isoformat()
            }
            await self.redis.set(f"session:{session_id}", str(data), ex=86400)
        except Exception as e:
            log.error(f"Failed to start session: {e}")
    
    async def record_event(self, session_id: str, event_type: str, 
                          video_id: Optional[str] = None, user_id: Optional[str] = None):
        if not self.redis:
            return
        
        try:
            data = {
                "session_id": session_id,
                "event_type": event_type,
                "video_id": video_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            key = f"event:{session_id}:{datetime.utcnow().timestamp()}"
            await self.redis.set(key, str(data), ex=604800)
            
            # Update user activity
            if user_id and video_id:
                activity_key = f"activity:{user_id}"
                await self.redis.lpush(activity_key, str({
                    "video_id": video_id,
                    "event_type": event_type,
                    "timestamp": datetime.utcnow().isoformat()
                }))
                await self.redis.ltrim(activity_key, 0, 49)
        except Exception as e:
            log.error(f"Failed to record event: {e}")