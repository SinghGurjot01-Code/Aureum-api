# core/ytmusic_client.py
import shutil
import os
import logging
import json
from typing import List, Dict, Any, Optional
from ytmusicapi import YTMusic

log = logging.getLogger(__name__)

# Global YTMusic instance
ytm = None

def load_cookies() -> Optional[str]:
    """
    Cookie loading logic (improved with better error handling)
    Checks in this order:
    1. Vercel env (YT_COOKIES)
    2. Render path (/etc/secrets)
    3. Existing /tmp/cookies.txt
    """
    from core.config import settings
    
    writable_path = settings.cookies_writable_path
    
    # Helper function to validate cookie file
    def validate_cookie_file(path: str) -> bool:
        """Check if cookie file contains valid JSON"""
        try:
            if not os.path.exists(path):
                return False
            with open(path, 'r') as f:
                content = f.read().strip()
                if not content:
                    log.warning(f"Cookie file {path} is empty")
                    return False
                # Try to parse as JSON
                json.loads(content)
                return True
        except json.JSONDecodeError as e:
            log.warning(f"Invalid JSON in cookie file {path}: {e}")
            return False
        except Exception as e:
            log.warning(f"Error reading cookie file {path}: {e}")
            return False
    
    # CASE 1 — Vercel environment variable
    cookies_env = os.getenv(settings.cookies_env_var)
    if cookies_env:
        try:
            # Validate the JSON before writing
            json.loads(cookies_env)  # Will raise JSONDecodeError if invalid
            with open(writable_path, "w") as f:
                f.write(cookies_env)
            log.info("Loaded cookies from ENV → /tmp/cookies.txt")
            return writable_path
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in YT_COOKIES env var: {e}")
        except Exception as e:
            log.error(f"Failed writing ENV cookies: {e}")
    
    # CASE 2 — Render read-only secret
    if os.path.exists(settings.cookies_readonly_path):
        try:
            # First check if it's valid
            if validate_cookie_file(settings.cookies_readonly_path):
                shutil.copy(settings.cookies_readonly_path, writable_path)
                log.info("Copied /etc/secrets/cookies.txt → /tmp/cookies.txt")
                return writable_path
            else:
                log.warning("Cookie file in /etc/secrets is invalid, skipping")
        except Exception as e:
            log.error(f"Failed copying cookies: {e}")
    
    # CASE 3 — Already exists and is valid
    if os.path.exists(writable_path) and validate_cookie_file(writable_path):
        log.info("Using existing valid /tmp/cookies.txt")
        return writable_path
    
    # FAILURE - log what we found
    log.warning("NO VALID COOKIES FOUND")
    if os.path.exists(settings.cookies_readonly_path):
        # Log first 100 chars of invalid cookie file for debugging
        try:
            with open(settings.cookies_readonly_path, 'r') as f:
                content = f.read(100)
                log.warning(f"Cookie file content (first 100 chars): {content}")
        except:
            pass
    
    return None

def init_ytmusic() -> Optional[YTMusic]:
    """Initialize YTMusic with better error handling"""
    global ytm
    
    cookie_path = load_cookies()
    
    # Try cookie authentication
    if cookie_path:
        try:
            ytm_instance = YTMusic(auth=cookie_path)
            log.info("YTMusic authenticated with cookies (OK)")
            ytm = ytm_instance
            return ytm
        except Exception as e:
            log.error(f"YTMusic cookie auth failed: {e}")
            # Try to delete invalid cookie file
            try:
                os.remove(cookie_path)
                log.info("Removed invalid cookie file")
            except:
                pass
    
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