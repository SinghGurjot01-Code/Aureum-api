# routes/artist.py
from fastapi import APIRouter, HTTPException
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

@router.get("/artist/{artist_id}")
async def get_artist(
    artist_id: str,
    session_id: Optional[str] = None,
    include_songs: bool = True,
    include_albums: bool = True
):
    """Get artist details with intent-aware ordering"""
    if not ytmusic_client.get_client():
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    try:
        # Get artist data
        artist_data = ytmusic_client.get_artist(artist_id)
        if not artist_data:
            raise HTTPException(status_code=404, detail="Artist not found")
        
        # Get intent
        intent = await get_session_intent(session_id)
        
        # Apply intent ordering to songs
        if include_songs and "songs" in artist_data:
            songs = artist_data["songs"]
            
            if intent == "artist-loop":
                # For artist-loop, ensure popular songs come first
                # This is simplified - implement actual popularity scoring
                artist_data["songs"] = sorted(
                    songs,
                    key=lambda x: len(x.get("title", "")),  # Placeholder
                    reverse=True
                )
        
        # Apply intent to related artists
        related = []
        if "related" in artist_data:
            related = artist_data["related"]
            
            if intent == "explore":
                # For explore, show diverse related artists
                related = related[:10]
            elif intent == "artist-loop":
                # For artist-loop, show similar artists only
                related = related[:5]
            else:
                related = related[:8]
        
        # Build response
        response = {
            "id": artist_data["id"],
            "name": artist_data["name"],
            "description": artist_data.get("description", ""),
            "thumbnail": artist_data.get("thumbnails", [{}])[-1].get("url", "") if artist_data.get("thumbnails") else "",
            "intent": intent
        }
        
        if include_songs:
            response["songs"] = artist_data.get("songs", [])[:20]  # Limit to 20 songs
        
        if include_albums:
            response["albums"] = artist_data.get("albums", [])[:10]  # Limit to 10 albums
        
        response["related_artists"] = [
            {
                "id": r.get("browseId", ""),
                "name": r.get("title", ""),
                "thumbnail": r.get("thumbnails", [{}])[-1].get("url", "") if r.get("thumbnails") else ""
            }
            for r in related[:8]
        ]
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Artist lookup failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")