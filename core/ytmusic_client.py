# core/ytmusic_client.py
import os
import json
import logging
from typing import List, Dict, Any, Optional
from ytmusicapi import YTMusic

log = logging.getLogger(__name__)

ytm = None

def init_ytmusic():
    """Initialize YTMusic - Handle any cookie format"""
    global ytm
    
    # Try cookies from Render secrets
    cookie_path = "/etc/secrets/cookies.txt"
    
    if os.path.exists(cookie_path):
        try:
            # Read cookie file
            with open(cookie_path, 'r') as f:
                content = f.read().strip()
            
            # Check if it's JSON
            if content and content.startswith('{'):
                try:
                    # Try to parse as JSON
                    json.loads(content)
                    # Valid JSON - write to temp file
                    temp_path = "/tmp/cookies.txt"
                    with open(temp_path, 'w') as f:
                        f.write(content)
                    
                    ytm = YTMusic(auth=temp_path)
                    log.info("YTMusic authenticated with JSON cookies")
                    return ytm
                except json.JSONDecodeError:
                    log.warning("Cookie file is not valid JSON")
            
            # If not JSON, check if it's raw cookie string
            if '=' in content and ';' in content:
                # Looks like raw cookie string
                cookie_json = json.dumps({"cookie": content})
                temp_path = "/tmp/cookies.txt"
                with open(temp_path, 'w') as f:
                    f.write(cookie_json)
                
                ytm = YTMusic(auth=temp_path)
                log.info("YTMusic authenticated with raw cookie string")
                return ytm
            
        except Exception as e:
            log.warning(f"Cookie auth failed: {e}")
    
    # Fallback to unauthenticated
    try:
        ytm = YTMusic()
        log.info("YTMusic initialized without cookies")
        return ytm
    except Exception as e:
        log.error(f"YTMusic failed: {e}")
        return None

def get_client():
    """Get YTMusic client instance"""
    return ytm

# ORIGINAL FUNCTION - PRESERVED EXACTLY
def search_songs(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search songs - original behavior preserved"""
    if not ytm:
        log.warning("YTMusic not available")
        return []
    
    try:
        results = ytm.search(query, filter="songs", limit=limit)
        out = []
        
        for r in results:
            if "videoId" not in r:
                continue

            dur = r.get("duration", "0:00")
            sec = 0
            if ":" in dur:
                try:
                    parts = list(map(int, dur.split(":")))
                    if len(parts) == 2:
                        sec = parts[0] * 60 + parts[1]
                    elif len(parts) == 3:
                        sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
                except:
                    sec = 0

            thumbs = r.get("thumbnails", [])
            thumb = thumbs[-1]["url"] if thumbs else ""

            out.append({
                "videoId": r["videoId"],
                "title": r.get("title", ""),
                "artists": ", ".join(a["name"] for a in r.get("artists", [])),
                "thumbnail": thumb,
                "duration": dur,
                "duration_seconds": sec
            })
        
        return out
        
    except Exception as e:
        log.error(f"Search error: {e}")
        return []

# NEW ENHANCED FUNCTIONS
def get_search_suggestions(query: str) -> List[str]:
    """Get search suggestions from YTMusic"""
    if not ytm:
        return []
    
    try:
        return ytm.get_search_suggestions(query)
    except Exception as e:
        log.error(f"Search suggestions failed: {e}")
        return []

def search_artists(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search for artists"""
    if not ytm:
        return []
    
    try:
        results = ytm.search(query, filter="artists", limit=limit)
        artists = []
        
        for r in results:
            if "artistId" not in r:
                continue
                
            artists.append({
                "id": r["artistId"],
                "name": r.get("title", ""),
                "thumbnail": r.get("thumbnails", [{}])[-1].get("url", "") if r.get("thumbnails") else "",
                "confidence": 0.9  # Placeholder for actual confidence scoring
            })
        
        return artists
    except Exception as e:
        log.error(f"Artist search failed: {e}")
        return []

def get_artist(artist_id: str) -> Optional[Dict[str, Any]]:
    """Get artist details"""
    if not ytm:
        return None
    
    try:
        artist_data = ytm.get_artist(artist_id)
        
        # Extract relevant data
        result = {
            "id": artist_id,
            "name": artist_data.get("name", ""),
            "description": artist_data.get("description", ""),
            "thumbnails": artist_data.get("thumbnails", []),
            "songs": [],
            "albums": []
        }
        
        # Process songs
        if "songs" in artist_data and "results" in artist_data["songs"]:
            for song in artist_data["songs"]["results"]:
                if "videoId" in song:
                    result["songs"].append({
                        "videoId": song["videoId"],
                        "title": song.get("title", ""),
                        "duration": song.get("duration", ""),
                        "thumbnail": song.get("thumbnails", [{}])[-1].get("url", "") if song.get("thumbnails") else ""
                    })
        
        # Process albums
        if "albums" in artist_data and "results" in artist_data["albums"]:
            for album in artist_data["albums"]["results"]:
                result["albums"].append({
                    "id": album.get("browseId", ""),
                    "title": album.get("title", ""),
                    "year": album.get("year", ""),
                    "thumbnail": album.get("thumbnails", [{}])[-1].get("url", "") if album.get("thumbnails") else ""
                })
        
        return result
    except Exception as e:
        log.error(f"Get artist failed: {e}")
        return None

def get_watch_playlist(video_id: str, radio: bool = True) -> List[Dict[str, Any]]:
    """Get watch playlist/radio tracks"""
    if not ytm:
        return []
    
    try:
        playlist = ytm.get_watch_playlist(videoId=video_id, radio=radio)
        tracks = []
        
        if "tracks" in playlist:
            for track in playlist["tracks"]:
                if "videoId" not in track:
                    continue
                    
                tracks.append({
                    "videoId": track["videoId"],
                    "title": track.get("title", ""),
                    "artists": ", ".join(a["name"] for a in track.get("artists", [])),
                    "duration": track.get("duration", ""),
                    "album": track.get("album", {}).get("name", "") if track.get("album") else ""
                })
        
        return tracks
    except Exception as e:
        log.error(f"Watch playlist failed: {e}")
        return []

def get_charts(country: str = "IN") -> Dict[str, Any]:
    """Get charts for a country"""
    if not ytm:
        return {"tracks": [], "videos": [], "artists": []}
    
    try:
        charts = ytm.get_charts(country=country)
        return charts
    except Exception as e:
        log.error(f"Charts failed: {e}")
        return {"tracks": [], "videos": [], "artists": []}

def get_mood_categories() -> List[Dict[str, Any]]:
    """Get mood categories"""
    if not ytm:
        return []
    
    try:
        moods = ytm.get_mood_categories()
        return moods
    except Exception as e:
        log.error(f"Mood categories failed: {e}")
        return []

def get_mood_playlists(mood_id: str) -> List[Dict[str, Any]]:
    """Get playlists for a mood"""
    if not ytm:
        return []
    
    try:
        playlists = ytm.get_mood_playlists(mood_id)
        return playlists
    except Exception as e:
        log.error(f"Mood playlists failed: {e}")
        return []