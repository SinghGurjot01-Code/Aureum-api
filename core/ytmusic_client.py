# core/ytmusic_client.py
import shutil
import os
import logging
from typing import List, Dict, Any, Optional
from ytmusicapi import YTMusic

log = logging.getLogger(__name__)

# Global YTMusic instance (same as original)
ytm = None

def load_cookies() -> Optional[str]:
    """
    Cookie loading logic (preserved from original)
    Checks in this order:
    1. Vercel env (YT_COOKIES)
    2. Render path (/etc/secrets)
    3. Existing /tmp/cookies.txt
    """
    from core.config import settings
    
    # CASE 1 — Vercel environment variable
    cookies_env = os.getenv(settings.cookies_env_var)
    if cookies_env:
        try:
            with open(settings.cookies_writable_path, "w") as f:
                f.write(cookies_env)
            log.info("Loaded cookies from ENV → /tmp/cookies.txt")
            return settings.cookies_writable_path
        except Exception as e:
            log.error(f"Failed writing ENV cookies: {e}")

    # CASE 2 — Render read-only secret
    if os.path.exists(settings.cookies_readonly_path):
        try:
            shutil.copy(settings.cookies_readonly_path, settings.cookies_writable_path)
            log.info("Copied /etc/secrets/cookies.txt → /tmp/cookies.txt")
            return settings.cookies_writable_path
        except Exception as e:
            log.error(f"Failed copying cookies: {e}")

    # CASE 3 — Already exists
    if os.path.exists(settings.cookies_writable_path):
        log.info("Using existing /tmp/cookies.txt")
        return settings.cookies_writable_path

    # FAILURE
    log.warning("NO COOKIES FOUND (YT_COOKIES env + /etc/secrets missing)")
    return None

def init_ytmusic() -> Optional[YTMusic]:
    """Initialize YTMusic (preserved logic)"""
    global ytm
    
    cookie_path = load_cookies()
    
    # Try cookie authentication
    try:
        if cookie_path:
            ytm_instance = YTMusic(auth=cookie_path)
            log.info("YTMusic authenticated with cookies (OK)")
            ytm = ytm_instance
            return ytm
    except Exception as e:
        log.error(f"YTMusic cookie auth failed: {e}")

    # Fallback: unauthenticated
    try:
        ytm_instance = YTMusic()
        log.info("YTMusic initialized without cookies (Fallback)")
        ytm = ytm_instance
        return ytm
    except Exception as e:
        log.error(f"YTMusic initialization failed completely: {e}")
        return None

def search_songs(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search songs (preserved behavior)
    Enhanced with fuzzy matching and fallback expansion
    """
    if not ytm:
        log.warning("YTMusic not initialized - returning empty results")
        return []
    
    try:
        # Original search
        results = ytm.search(query, filter="songs", limit=limit)
        out = []
        
        for r in results:
            if "videoId" not in r:
                continue

            # Parse duration safely (preserved)
            dur = r.get("duration", "0:00")
            sec = 0
            if ":" in dur:
                parts = list(map(int, dur.split(":")))
                if len(parts) == 2:
                    sec = parts[0] * 60 + parts[1]
                elif len(parts) == 3:
                    sec = parts[0] * 3600 + parts[1] * 60 + parts[2]

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
        
        # Enhanced: If results are poor, try fuzzy matching
        if len(out) < 3 and len(query) > 2:
            out = _enhance_search_with_fallback(query, limit, out)
        
        return out
        
    except Exception as e:
        log.error(f"Search error: {e}")
        return []

def _enhance_search_with_fallback(query: str, limit: int, original_results: List[Dict]) -> List[Dict]:
    """Enhanced search with fuzzy matching and artist fallback"""
    try:
        from rapidfuzz import fuzz
        
        # Try artist-based expansion
        artist_results = ytm.search(query, filter="artists", limit=3)
        if artist_results:
            top_artist = artist_results[0].get("artist", "")
            if top_artist:
                # Search for popular tracks by this artist
                artist_songs = ytm.search(top_artist, filter="songs", limit=5)
                
                # Add unique results
                existing_ids = {r["videoId"] for r in original_results}
                for song in artist_songs:
                    if "videoId" in song and song["videoId"] not in existing_ids:
                        # Format same as original
                        dur = song.get("duration", "0:00")
                        sec = 0
                        if ":" in dur:
                            parts = list(map(int, dur.split(":")))
                            if len(parts) == 2:
                                sec = parts[0] * 60 + parts[1]
                        
                        thumbs = song.get("thumbnails", [])
                        thumb = thumbs[-1]["url"] if thumbs else ""
                        
                        original_results.append({
                            "videoId": song["videoId"],
                            "title": song.get("title", ""),
                            "artists": ", ".join(a["name"] for a in song.get("artists", [])),
                            "thumbnail": thumb,
                            "duration": dur,
                            "duration_seconds": sec
                        })
                        
                        if len(original_results) >= limit:
                            break
    except Exception as e:
        log.debug(f"Search enhancement failed: {e}")
    
    return original_results[:limit]