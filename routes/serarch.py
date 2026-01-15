# routes/search.py
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
            # Check session events for intent patterns
            # This is simplified - implement actual intent detection
            return "neutral"
    except:
        pass
    
    return "neutral"

@router.get("/search/suggest")
async def search_suggest(
    q: str = Query(..., min_length=1, max_length=100),
    session_id: Optional[str] = None,
    limit: int = 5
):
    """Enhanced search with suggestions and intent"""
    if not ytmusic_client.get_client():
        return {
            "intent": "neutral",
            "suggestions": [],
            "artists": [],
            "tracks": [],
            "related_artists": []
        }
    
    try:
        # Get intent
        intent = await get_session_intent(session_id)
        
        # Get search suggestions
        suggestions = ytmusic_client.get_search_suggestions(q)
        
        # Search for artists
        artists = ytmusic_client.search_artists(q, limit=3)
        
        # Search for tracks (using original function for compatibility)
        tracks = ytmusic_client.search_songs(q, limit=limit)
        
        # Get related artists if we found a primary artist
        related_artists = []
        if artists and intent != "artist-loop":
            # Get first artist's details to find related
            artist_data = ytmusic_client.get_artist(artists[0]["id"])
            if artist_data and "related" in artist_data:
                for related in artist_data.get("related", [])[:3]:
                    related_artists.append({
                        "id": related.get("browseId", ""),
                        "name": related.get("title", "")
                    })
        
        # Apply intent ordering (simplified)
        if intent == "artist-loop" and artists:
            # Boost tracks from primary artist
            primary_artist = artists[0]["name"].lower()
            for track in tracks:
                if primary_artist in track.get("artists", "").lower():
                    track["score"] = track.get("score", 0) + 0.5
        
        return {
            "intent": intent,
            "suggestions": suggestions[:5],
            "artists": artists,
            "tracks": tracks[:limit],
            "related_artists": related_artists[:3]
        }
        
    except Exception as e:
        log.error(f"Search suggest failed: {e}")
        return {
            "intent": "neutral",
            "suggestions": [],
            "artists": [],
            "tracks": [],
            "related_artists": []
        }

@router.get("/charts")
async def get_charts(country: str = "IN"):
    """Get charts for a country"""
    if not ytmusic_client.get_client():
        return {"tracks": [], "videos": [], "artists": []}
    
    try:
        charts = ytmusic_client.get_charts(country)
        
        # Format response
        return {
            "tracks": charts.get("tracks", [])[:50],
            "videos": charts.get("videos", [])[:50],
            "artists": charts.get("artists", [])[:20]
        }
    except Exception as e:
        log.error(f"Charts failed: {e}")
        return {"tracks": [], "videos": [], "artists": []}

@router.get("/moods")
async def get_moods():
    """Get mood categories and playlists"""
    if not ytmusic_client.get_client():
        return {"categories": []}
    
    try:
        categories = ytmusic_client.get_mood_categories()
        
        # Format response
        formatted_categories = []
        for category in categories[:10]:  # Limit to 10
            category_data = {
                "id": category.get("params", ""),
                "title": category.get("title", ""),
                "playlists": []
            }
            
            # Get playlists for this mood
            playlists = ytmusic_client.get_mood_playlists(category.get("params", ""))
            for playlist in playlists[:5]:  # Limit to 5 per category
                category_data["playlists"].append({
                    "id": playlist.get("playlistId", ""),
                    "title": playlist.get("title", ""),
                    "thumbnail": playlist.get("thumbnails", [{}])[-1].get("url", "") if playlist.get("thumbnails") else "",
                    "count": playlist.get("count", 0)
                })
            
            formatted_categories.append(category_data)
        
        return {"categories": formatted_categories}
    except Exception as e:
        log.error(f"Moods failed: {e}")
        return {"categories": []}