# routes/play.py
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging
from core import ytmusic_client
from redis.client import get_redis_client

log = logging.getLogger(__name__)
router = APIRouter()

async def get_session_intent(session_id: Optional[str] = None) -> str:
    """Get intent from session - defaults to neutral"""
    if not session_id:
        return "neutral"
    
    try:
        redis_client = get_redis_client()
        if redis_client:
            # Simplified intent detection
            return "neutral"
    except:
        pass
    
    return "neutral"

@router.get("/play/next")
async def get_next_track(
    video_id: str = Query(..., description="Current video ID"),
    session_id: Optional[str] = None,
    radio: bool = True,
    limit: int = 10
):
    """Get next tracks with radio logic"""
    if not ytmusic_client.get_client():
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    try:
        # Get watch playlist (radio)
        tracks = ytmusic_client.get_watch_playlist(video_id, radio=radio)
        
        if not tracks:
            # Fallback to search for similar
            from core.ytmusic_client import search_songs
            tracks_data = search_songs("music", limit=limit)
            tracks = [
                {
                    "videoId": t["videoId"],
                    "title": t["title"],
                    "artists": t["artists"],
                    "duration": t["duration"]
                }
                for t in tracks_data
            ]
        
        # Get intent
        intent = await get_session_intent(session_id)
        
        # Apply intent filtering (simplified)
        if intent == "artist-loop":
            # Try to keep same artist
            current_track = None
            for track in tracks:
                if track["videoId"] == video_id:
                    current_track = track
                    break
            
            if current_track:
                # Filter tracks by same artist (simplified)
                filtered_tracks = [t for t in tracks if current_track.get("artists", "") in t.get("artists", "")]
                if filtered_tracks:
                    tracks = filtered_tracks
        
        # Limit results
        tracks = tracks[:limit]
        
        return {
            "next": tracks,
            "count": len(tracks),
            "radio": radio,
            "intent": intent
        }
        
    except Exception as e:
        log.error(f"Next track failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")