# recommend/engine.py
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from models.schemas import RecommendationResponse, Track
from redis.client import safe_redis_get
from core.ytmusic_client import search_songs
from core.config import settings
from .heuristics import (
    get_similar_artists,
    get_genre_based_recommendations,
    get_time_based_recommendations,
    calculate_skip_velocity
)

log = logging.getLogger(__name__)

class RecommendationEngine:
    """Context-aware recommendation engine"""
    
    def __init__(self):
        self.limit = settings.recommendation_limit
    
    async def get_contextual_recommendations(
        self,
        current_track: Optional[Dict] = None,
        recent_activity: Optional[List[Dict]] = None,
        user_id: Optional[str] = None,
        taste_profile: Optional[Dict] = None,
        limit: int = None
    ) -> RecommendationResponse:
        """Generate context-aware recommendations"""
        if limit is None:
            limit = self.limit
        
        try:
            # Get recent activity from Redis if not provided
            if user_id and not recent_activity:
                recent_activity = await self._get_user_recent_activity(user_id)
            
            # Extract context
            context = self._extract_context(current_track, recent_activity, taste_profile)
            
            # Generate recommendations based on context
            tracks = await self._generate_recommendations(context, limit)
            
            # Apply ranking and labeling
            ranked_tracks = self._rank_and_label_tracks(tracks, context)
            
            return RecommendationResponse(
                tracks=ranked_tracks[:limit],
                labels=[track.get("label", "") for track in ranked_tracks[:limit] if track.get("label")],
                context=context,
                generated_at=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            log.error(f"Recommendation generation failed: {e}")
            # Return empty response instead of error
            return RecommendationResponse(
                tracks=[],
                labels=[],
                context={},
                generated_at=datetime.utcnow().isoformat()
            )
    
    async def _get_user_recent_activity(self, user_id: str) -> List[Dict]:
        """Get user's recent activity from Redis"""
        try:
            from redis.client import get_redis_client
            redis_client = get_redis_client()
            if redis_client:
                activity_key = f"recent_activity:{user_id}"
                activities = await redis_client.lrange(activity_key, 0, -1)
                return [json.loads(act) for act in activities]
        except Exception as e:
            log.debug(f"Failed to get recent activity: {e}")
        return []
    
    def _extract_context(
        self,
        current_track: Optional[Dict],
        recent_activity: Optional[List[Dict]],
        taste_profile: Optional[Dict]
    ) -> Dict[str, Any]:
        """Extract context from inputs"""
        context = {
            "current_artist": None,
            "recent_artists": set(),
            "genres": set(),
            "skip_velocity": 0.0,
            "time_of_day": datetime.utcnow().hour,
            "mood": "neutral"
        }
        
        # Extract from current track
        if current_track:
            if "artists" in current_track:
                context["current_artist"] = current_track["artists"].split(", ")[0] if current_track["artists"] else None
        
        # Extract from recent activity
        if recent_activity:
            # Calculate skip velocity
            context["skip_velocity"] = calculate_skip_velocity(recent_activity)
            
            # Extract recent artists
            for activity in recent_activity[-10:]:  # Last 10 activities
                if "video_id" in activity:
                    # In production, you'd fetch track details to get artist
                    pass
        
        # Extract from taste profile
        if taste_profile:
            if "preferred_genres" in taste_profile:
                context["genres"].update(taste_profile["preferred_genres"])
            if "mood" in taste_profile:
                context["mood"] = taste_profile["mood"]
        
        return context
    
    async def _generate_recommendations(self, context: Dict, limit: int) -> List[Track]:
        """Generate recommendations based on context"""
        tracks = []
        
        # 1. Similar artists to current artist
        if context["current_artist"]:
            similar_artists = get_similar_artists(context["current_artist"])
            for artist in similar_artists[:3]:
                artist_tracks = search_songs(artist, limit=5)
                for track in artist_tracks:
                    if track not in tracks:
                        tracks.append(track)
        
        # 2. Genre-based recommendations
        if context["genres"]:
            for genre in list(context["genres"])[:2]:
                genre_tracks = get_genre_based_recommendations(genre, limit=5)
                tracks.extend(genre_tracks)
        
        # 3. Time-based recommendations
        time_tracks = get_time_based_recommendations(context["time_of_day"], limit=5)
        tracks.extend(time_tracks)
        
        # 4. Fallback: popular tracks
        if len(tracks) < limit:
            popular_tracks = search_songs("popular music", limit=limit - len(tracks))
            tracks.extend(popular_tracks)
        
        return tracks[:limit * 2]  # Return more for ranking
    
    def _rank_and_label_tracks(self, tracks: List[Track], context: Dict) -> List[Dict]:
        """Rank tracks and apply labels"""
        ranked = []
        
        for track in tracks:
            score = 1.0
            label = None
            
            # Apply scoring based on context
            if context["current_artist"] and context["current_artist"] in track.get("artists", ""):
                score *= 1.5
                label = "More by this artist"
            
            # Apply label based on similarity
            elif not label and context["current_artist"]:
                label = "Similar artist"
            
            # Time-based labeling
            if 6 <= context["time_of_day"] < 12:
                if not label:
                    label = "Morning vibes"
            elif 18 <= context["time_of_day"] < 22:
                if not label:
                    label = "Evening chill"
            
            # Genre-based labeling (simplified)
            if "punjabi" in track.get("title", "").lower() or "punjabi" in track.get("artists", "").lower():
                if not label:
                    label = "Punjabi vibes"
                score *= 1.2
            
            # Skip velocity adjustment
            if context["skip_velocity"] > 0.7:  # High skipping
                # Prefer shorter tracks
                if track.get("duration_seconds", 0) < 180:
                    score *= 1.3
            
            track_with_score = dict(track)
            track_with_score["score"] = score
            if label:
                track_with_score["label"] = label
            
            ranked.append(track_with_score)
        
        # Sort by score
        ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return ranked