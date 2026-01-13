# session/store.py
import uuid
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from redis.client import safe_redis_set, safe_redis_get, safe_redis_delete
from core.config import settings

log = logging.getLogger(__name__)

class SessionStore:
    """Store session data in Redis"""
    
    def __init__(self):
        self.session_ttl = settings.session_ttl
        self.event_ttl = settings.event_ttl
    
    async def start_session(
        self,
        user_id: Optional[str] = None,
        device_info: Optional[Dict] = None,
        location: Optional[str] = None
    ) -> str:
        """Start a new session and store metadata"""
        session_id = str(uuid.uuid4())
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "device_info": device_info or {},
            "location": location,
            "started_at": datetime.utcnow().isoformat(),
            "event_count": 0
        }
        
        # Store session metadata
        session_key = f"session:{session_id}"
        await safe_redis_set(
            session_key,
            json.dumps(session_data),
            ttl=self.session_ttl
        )
        
        # Link user to session if authenticated
        if user_id:
            user_sessions_key = f"user_sessions:{user_id}"
            await safe_redis_set(
                user_sessions_key,
                session_id,
                ttl=self.session_ttl
            )
        
        log.info(f"Started session {session_id} for user {user_id or 'anonymous'}")
        return session_id
    
    async def record_event(
        self,
        session_id: str,
        event_type: str,
        video_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        user_id: Optional[str] = None,
        additional_data: Optional[Dict] = None
    ) -> bool:
        """Record a session event"""
        if not timestamp:
            timestamp = datetime.utcnow().isoformat()
        
        event_data = {
            "session_id": session_id,
            "event_type": event_type,
            "video_id": video_id,
            "timestamp": timestamp,
            "user_id": user_id,
            "additional_data": additional_data or {}
        }
        
        # Generate unique event ID
        event_id = str(uuid.uuid4())
        event_key = f"event:{session_id}:{event_id}"
        
        # Store event
        success = await safe_redis_set(
            event_key,
            json.dumps(event_data),
            ttl=self.event_ttl
        )
        
        if success:
            # Update session metadata
            session_key = f"session:{session_id}"
            session_json = await safe_redis_get(session_key)
            if session_json:
                try:
                    session_data = json.loads(session_json)
                    session_data["event_count"] = session_data.get("event_count", 0) + 1
                    session_data["last_event_at"] = timestamp
                    await safe_redis_set(
                        session_key,
                        json.dumps(session_data),
                        ttl=self.session_ttl
                    )
                except Exception as e:
                    log.debug(f"Failed to update session metadata: {e}")
            
            # Store recent activity for user
            if user_id and video_id and event_type in ["play", "skip"]:
                await self._update_user_recent_activity(user_id, video_id, event_type, timestamp)
        
        return success
    
    async def _update_user_recent_activity(
        self,
        user_id: str,
        video_id: str,
        event_type: str,
        timestamp: str
    ):
        """Update user's recent activity in Redis"""
        try:
            activity_key = f"recent_activity:{user_id}"
            activity_item = {
                "video_id": video_id,
                "event_type": event_type,
                "timestamp": timestamp
            }
            
            # Use Redis list to store recent activity
            activity_data = json.dumps(activity_item)
            
            # Get Redis client
            from redis.client import get_redis_client
            redis_client = get_redis_client()
            if redis_client:
                await redis_client.lpush(activity_key, activity_data)
                await redis_client.ltrim(activity_key, 0, settings.recent_activity_window - 1)
                await redis_client.expire(activity_key, self.event_ttl)
        except Exception as e:
            log.debug(f"Failed to update recent activity: {e}")
    
    async def get_session_events(self, session_id: str) -> List[Dict]:
        """Get all events for a session"""
        # This is a simplified version - in production you'd use SCAN
        return []