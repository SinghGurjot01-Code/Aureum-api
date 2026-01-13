# cache/manifest.py
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from models.schemas import CacheManifestResponse
from redis.client import safe_redis_get
from core.config import settings
from recommend.engine import RecommendationEngine

log = logging.getLogger(__name__)

class CacheManifestGenerator:
    """Generate intelligent offline cache predictions"""
    
    def __init__(self):
        self.must_cache_size = settings.must_cache_size
        self.likely_next_size = settings.likely_next_size
    
    async def generate_manifest(self, user_id: Optional[str] = None) -> CacheManifestResponse:
        """Generate cache manifest for offline playback"""
        try:
            must_cache = []
            likely_next = []
            
            if user_id:
                # Personalized cache prediction
                must_cache = await self._get_personalized_must_cache(user_id)
                likely_next = await self._get_likely_next_tracks(user_id)
            else:
                # Anonymous user - generic cache
                must_cache = await self._get_generic_must_cache()
                likely_next = await self._get_generic_likely_next()
            
            # Ensure we have the right number of tracks
            must_cache = must_cache[:self.must_cache_size]
            likely_next = likely_next[:self.likely_next_size]
            
            # Calculate expiry (24 hours)
            expires_at = int((datetime.utcnow() + timedelta(hours=settings.cache_prediction_hours)).timestamp())
            
            return CacheManifestResponse(
                must_cache=must_cache,
                likely_next=likely_next,
                expires_at=expires_at
            )
            
        except Exception as e:
            log.error(f"Cache manifest generation failed: {e}")
            # Return empty manifest
            return CacheManifestResponse(
                must_cache=[],
                likely_next=[],
                expires_at=int((datetime.utcnow() + timedelta(hours=1)).timestamp())
            )
    
    async def _get_personalized_must_cache(self, user_id: str) -> List[Dict]:
        """Get must-cache tracks for specific user"""
        tracks = []
        
        try:
            # Get recent frequently played tracks
            from redis.client import get_redis_client
            redis_client = get_redis_client()
            if redis_client:
                activity_key = f"recent_activity:{user_id}"
                activities = await redis_client.lrange(activity_key, 0, 49)  # Last 50 activities
                
                # Count video occurrences
                video_counts = {}
                for activity_json in activities:
                    try:
                        activity = json.loads(activity_json)
                        video_id = activity.get("video_id")
                        if video_id and activity.get("event_type") == "play":
                            video_counts[video_id] = video_counts.get(video_id, 0) + 1
                    except:
                        continue
                
                # Get top played tracks
                sorted_videos = sorted(video_counts.items(), key=lambda x: x[1], reverse=True)
                for video_id, count in sorted_videos[:5]:
                    # In production, you'd fetch track details
                    tracks.append({"videoId": video_id, "reason": f"Played {count} times"})
        
        except Exception as e:
            log.debug(f"Personalized cache failed: {e}")
        
        # Fallback to generic if not enough
        if len(tracks) < 3:
            generic = await self._get_generic_must_cache()
            tracks.extend(generic[:3])
        
        return tracks[:self.must_cache_size]
    
    async def _get_likely_next_tracks(self, user_id: str) -> List[Dict]:
        """Get likely next tracks based on user behavior"""
        try:
            # Use recommendation engine
            engine = RecommendationEngine()
            recent_activity = await engine._get_user_recent_activity(user_id)
            
            if recent_activity:
                # Get last played track
                last_play = None
                for activity in reversed(recent_activity):
                    if activity.get("event_type") == "play":
                        last_play = {"video_id": activity.get("video_id")}
                        break
                
                if last_play:
                    # Generate recommendations based on last play
                    response = await engine.get_contextual_recommendations(
                        current_track=last_play,
                        recent_activity=recent_activity,
                        user_id=user_id,
                        limit=self.likely_next_size
                    )
                    return response.tracks
        
        except Exception as e:
            log.debug(f"Likely next tracks failed: {e}")
        
        # Fallback
        return await self._get_generic_likely_next()
    
    async def _get_generic_must_cache(self) -> List[Dict]:
        """Get generic must-cache tracks (popular globally)"""
        from core.ytmusic_client import search_songs
        
        try:
            # Popular tracks across genres
            popular_genres = ["pop", "hip hop", "punjabi", "electronic"]
            tracks = []
            
            for genre in popular_genres[:2]:
                genre_tracks = search_songs(f"{genre} hits 2024", limit=3)
                for track in genre_tracks:
                    if track not in tracks:
                        tracks.append(track)
            
            return tracks[:self.must_cache_size]
        except Exception as e:
            log.debug(f"Generic must-cache failed: {e}")
            return []
    
    async def _get_generic_likely_next(self) -> List[Dict]:
        """Get generic likely next tracks"""
        from core.ytmusic_client import search_songs
        
        try:
            # Trending tracks
            return search_songs("trending music", limit=self.likely_next_size)
        except Exception as e:
            log.debug(f"Generic likely next failed: {e}")
            return []