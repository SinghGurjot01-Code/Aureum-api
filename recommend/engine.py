# recommend/engine.py
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from core import ytmusic_client
from redis.client import get_redis_client

log = logging.getLogger(__name__)

class RecommendationEngine:
    def __init__(self):
        self.redis = get_redis_client()
    
    async def _get_intent(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> str:
        """Determine user intent"""
        # Simplified intent detection
        # In production, implement based on user behavior
        return "neutral"
    
    async def _apply_intent_ordering(self, tracks: List[Dict[str, Any]], intent: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply intent-based ordering to tracks"""
        if intent == "artist-loop" and context.get("current_artist"):
            # Boost tracks from same artist
            current_artist = context["current_artist"].lower()
            for track in tracks:
                if current_artist in track.get("artists", "").lower():
                    track["score"] = track.get("score", 0) + 0.3
        
        elif intent == "explore":
            # Boost variety - ensure different artists
            seen_artists = set()
            for track in tracks:
                artists = track.get("artists", "")
                if artists and artists not in seen_artists:
                    track["score"] = track.get("score", 0) + 0.2
                    seen_artists.add(artists)
        
        # Sort by score
        return sorted(tracks, key=lambda x: x.get("score", 0), reverse=True)
    
    async def get_recommendations(self, current_video_id: Optional[str] = None,
                                 user_id: Optional[str] = None, 
                                 session_id: Optional[str] = None,
                                 limit: int = 20) -> Dict[str, Any]:
        try:
            # Get intent
            intent = await self._get_intent(user_id, session_id)
            
            # Get recent activity if user_id provided
            recent_tracks = []
            if user_id and self.redis:
                try:
                    activity_key = f"activity:{user_id}"
                    activities = await self.redis.lrange(activity_key, 0, 9)
                    recent_tracks = [eval(a)["video_id"] for a in activities if "video_id" in eval(a)]
                except:
                    pass
            
            # Generate recommendations using ytmusicapi
            tracks = []
            context = {"has_history": len(recent_tracks) > 0}
            
            if current_video_id:
                # Use watch playlist for radio recommendations
                watch_tracks = ytmusic_client.get_watch_playlist(current_video_id, radio=True)
                if watch_tracks:
                    tracks = watch_tracks[:limit]
                    context["source"] = "radio"
                else:
                    # Fallback to search
                    tracks = ytmusic_client.search_songs("similar music", limit=limit)
                    context["source"] = "search"
            
            elif recent_tracks:
                # Based on user history - use last track for radio
                try:
                    last_track = recent_tracks[0]
                    watch_tracks = ytmusic_client.get_watch_playlist(last_track, radio=True)
                    if watch_tracks:
                        tracks = watch_tracks[:limit]
                        context["source"] = "history_radio"
                    else:
                        tracks = ytmusic_client.search_songs("popular", limit=limit)
                        context["source"] = "popular"
                except:
                    tracks = ytmusic_client.search_songs("popular", limit=limit)
                    context["source"] = "popular_fallback"
            
            else:
                # Get trending from charts
                charts = ytmusic_client.get_charts("IN")
                if charts and "tracks" in charts and charts["tracks"]:
                    tracks = [
                        {
                            "videoId": t.get("videoId", ""),
                            "title": t.get("title", ""),
                            "artists": ", ".join(a["name"] for a in t.get("artists", [])),
                            "duration": t.get("duration", ""),
                            "thumbnail": t.get("thumbnails", [{}])[-1].get("url", "") if t.get("thumbnails") else ""
                        }
                        for t in charts["tracks"][:limit]
                    ]
                    context["source"] = "charts"
                else:
                    # Fallback to search
                    tracks = ytmusic_client.search_songs("trending music", limit=limit)
                    context["source"] = "search_fallback"
            
            # Add scores and labels
            labeled_tracks = []
            for i, track in enumerate(tracks):
                label = "Recommended"
                if i == 0:
                    label = "Top Pick"
                elif i < 3:
                    label = "Trending"
                
                labeled_track = {
                    **track,
                    "label": label,
                    "score": 1.0 - (i * 0.05)
                }
                labeled_tracks.append(labeled_track)
            
            # Apply intent ordering
            if current_video_id and len(tracks) > 0:
                # Try to get current artist from first track
                context["current_artist"] = tracks[0].get("artists", "")
            
            ordered_tracks = await self._apply_intent_ordering(labeled_tracks, intent, context)
            
            return {
                "tracks": ordered_tracks[:limit],
                "context": {
                    **context,
                    "intent": intent,
                    "has_history": len(recent_tracks) > 0,
                    "has_current": current_video_id is not None
                },
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            log.error(f"Recommendation failed: {e}")
            return {
                "tracks": [],
                "context": {"intent": "neutral", "source": "error"},
                "generated_at": datetime.utcnow().isoformat()
            }