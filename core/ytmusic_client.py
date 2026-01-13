# core/ytmusic_client.py
import os
import json
import logging
from typing import List, Dict, Any
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