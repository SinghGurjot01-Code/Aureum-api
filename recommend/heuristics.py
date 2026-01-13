# recommend/heuristics.py
import logging
from typing import List, Dict, Any
from datetime import datetime
from core.ytmusic_client import search_songs

log = logging.getLogger(__name__)

# Simplified artist similarity mapping
ARTIST_SIMILARITY = {
    "drake": ["kendrick lamar", "j. cole", "travis scott", "post malone"],
    "taylor swift": ["olivia rodrigo", "sabrina carpenter", "lana del rey"],
    "weeknd": ["bruno mars", "david guetta", "calvin harris"],
    "bad bunny": ["j balvin", "ozuna", "anuel aa"],
    "ed sheeran": ["james arthur", "passenger", "calum scott"],
    "punjabi": ["diljit dosanjh", "ap dhillon", "shubh", "karan aujla"],
}

# Time-based genre preferences
TIME_GENRES = {
    "morning": ["pop", "upbeat", "motivational"],
    "afternoon": ["rock", "hip hop", "electronic"],
    "evening": ["chill", "lofi", "r&b"],
    "night": ["jazz", "ambient", "classical"]
}

def get_similar_artists(artist: str) -> List[str]:
    """Get similar artists based on mapping"""
    artist_lower = artist.lower()
    
    # Direct mapping
    if artist_lower in ARTIST_SIMILARITY:
        return ARTIST_SIMILARITY[artist_lower]
    
    # Fuzzy matching
    for key, similar in ARTIST_SIMILARITY.items():
        if key in artist_lower or artist_lower in key:
            return similar
    
    # Fallback: search for related artists
    try:
        results = search_songs(artist, limit=1)
        if results:
            # Return empty for now - in production would use actual similarity
            return []
    except Exception as e:
        log.debug(f"Failed to find similar artists for {artist}: {e}")
    
    return []

def get_genre_based_recommendations(genre: str, limit: int = 10) -> List[Dict]:
    """Get recommendations based on genre"""
    try:
        # Map genre to search terms
        genre_terms = {
            "pop": "pop music",
            "rock": "rock music",
            "hip hop": "hip hop",
            "electronic": "electronic music",
            "punjabi": "punjabi music",
            "lofi": "lofi beats",
            "jazz": "jazz music"
        }
        
        search_term = genre_terms.get(genre.lower(), genre)
        return search_songs(search_term, limit=limit)
    except Exception as e:
        log.debug(f"Genre recommendations failed for {genre}: {e}")
        return []

def get_time_based_recommendations(hour: int, limit: int = 10) -> List[Dict]:
    """Get recommendations based on time of day"""
    if 6 <= hour < 12:
        time_slot = "morning"
    elif 12 <= hour < 18:
        time_slot = "afternoon"
    elif 18 <= hour < 22:
        time_slot = "evening"
    else:
        time_slot = "night"
    
    genres = TIME_GENRES.get(time_slot, ["pop"])
    
    recommendations = []
    for genre in genres[:2]:
        recs = get_genre_based_recommendations(genre, limit=limit//2)
        recommendations.extend(recs)
    
    return recommendations[:limit]

def calculate_skip_velocity(recent_activity: List[Dict]) -> float:
    """Calculate skip velocity (how frequently user skips)"""
    if not recent_activity or len(recent_activity) < 3:
        return 0.0
    
    # Look at last 10 events
    recent = recent_activity[-10:]
    skip_count = sum(1 for event in recent if event.get("event_type") == "skip")
    play_count = sum(1 for event in recent if event.get("event_type") == "play")
    
    total = skip_count + play_count
    if total == 0:
        return 0.0
    
    return skip_count / total