# recommend/engine.py
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.ytmusic_client import search_songs
from redis.client import get_redis_client

log = logging.getLogger(__name__)

class RecommendationEngine:
    def __init__(self):
        self.redis = get_redis_client()
    
    async def get_recommendations(self, current_video_id: Optional[str] = None,
                                 user_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        try:
            # Get recent activity if user_id provided
            recent_tracks = []
            if user_id and self.redis:
                try:
                    activity_key = f"activity:{user_id}"
                    activities = await self.redis.lrange(activity_key, 0, 9)
                    recent_tracks = [eval(a)["video_id"] for a in activities if "video_id" in eval(a)]
                except:
                    pass
            
            # Generate recommendations
            if current_video_id:
                # Search for similar tracks
                tracks = search_songs("similar music", limit=limit)
            elif recent_tracks:
                # Based on user history
                tracks = search_songs("popular", limit=limit)
            else:
                # Popular tracks
                tracks = search_songs("trending music", limit=limit)
            
            # Add labels
            labeled_tracks = []
            for i, track in enumerate(tracks):
                label = "Recommended"
                if i == 0:
                    label = "Top Pick"
                elif i < 3:
                    label = "Trending"
                
                labeled_tracks.append({
                    **track,
                    "label": label,
                    "score": 1.0 - (i * 0.05)
                })
            
            return {
                "tracks": labeled_tracks,
                "context": {
                    "has_history": len(recent_tracks) > 0,
                    "has_current": current_video_id is not None
                },
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            log.error(f"Recommendation failed: {e}")
            return {
                "tracks": [],
                "context": {},
                "generated_at": datetime.utcnow().isoformat()
            }