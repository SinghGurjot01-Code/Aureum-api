# core/ytmusic_client.py
import os
import logging
from typing import List, Dict, Any, Optional
from ytmusicapi import YTMusic

log = logging.getLogger(__name__)

# Global YTMusic instance
ytm = None

def load_cookies() -> Optional[str]:
    """
    Load cookies from Render secrets
    Only checks /etc/secrets/cookies.txt
    """
    from core.config import settings
    
    source_path = settings.cookies_path
    temp_path = settings.cookies_temp_path
    
    if not os.path.exists(source_path):
        log.warning(f"No cookie file found at {source_path}")
        return None
    
    try:
        # Read the cookie file
        with open(source_path, 'r') as f:
            content = f.read().strip()
        
        if not content:
            log.warning("Cookie file is empty")
            return None
        
        # Copy to temp location (ytmusicapi needs writable location)
        with open(temp_path, 'w') as f:
            f.write(content)
        
        log.info(f"Loaded cookies from {source_path}")
        return temp_path
        
    except Exception as e:
        log.error(f"Failed to load cookies: {e}")
        return None

def init_ytmusic() -> Optional[YTMusic]:
    """Initialize YTMusic"""
    global ytm
    
    # Try with cookies first
    cookie_path = load_cookies()
    if cookie_path:
        try:
            ytm_instance = YTMusic(auth=cookie_path)
            log.info("YTMusic authenticated with cookies")
            ytm = ytm_instance
            return ytm
        except Exception as e:
            log.warning(f"Cookie auth failed: {e}")
            # Continue to fallback
    
    # Fallback: unauthenticated
    try:
        ytm_instance = YTMusic()
        log.info("YTMusic initialized without cookies")
        ytm = ytm_instance
        return ytm
    except Exception as e:
        log.error(f"YTMusic initialization failed: {e}")
        return None

def search_songs(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search songs - original preserved behavior
    """
    if not ytm:
        log.warning("YTMusic not initialized")
        return []
    
    try:
        results = ytm.search(query, filter="songs", limit=limit)
        out = []
        
        for r in results:
            if "videoId" not in r:
                continue

            # Parse duration
            dur = r.get("duration", "0:00")
            sec = 0
            if ":" in dur:
                try:
                    parts = list(map(int, dur.split(":")))
                    if len(parts) == 2:
                        sec = parts[0] * 60 + parts[1]
                    elif len(parts) == 3:
                        sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
                except (ValueError, TypeError):
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