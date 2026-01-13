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

def netscape_to_json(netscape_content: str) -> Optional[str]:
    """
    Convert Netscape format cookies to ytmusicapi JSON format
    Netscape format:
    # Netscape HTTP Cookie File
    .youtube.com	TRUE	/	TRUE	1730000000	CONSENT	YES+
    """
    try:
        cookies = []
        lines = netscape_content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            if len(parts) >= 7:
                domain = parts[0].strip()
                # Handle subdomain flag
                if domain.startswith('.'):
                    host_only = False
                    domain = domain[1:]  # Remove leading dot
                else:
                    host_only = True
                
                path = parts[2].strip()
                secure = parts[3].strip().lower() == 'true'
                expiration = float(parts[4].strip()) if parts[4].strip() else None
                name = parts[5].strip()
                value = parts[6].strip()
                
                cookie_obj = {
                    "domain": domain,
                    "expirationDate": expiration,
                    "hostOnly": host_only,
                    "httpOnly": False,  # Can't determine from Netscape format
                    "name": name,
                    "path": path,
                    "sameSite": "no_restriction",
                    "secure": secure,
                    "session": expiration is None,
                    "storeId": "0",
                    "value": value
                }
                cookies.append(cookie_obj)
        
        if cookies:
            return json.dumps(cookies)
        return None
    except Exception as e:
        log.error(f"Failed to convert Netscape cookies: {e}")
        return None

def load_cookies() -> Optional[str]:
    """
    Cookie loading logic with Netscape format support
    Checks in this order:
    1. Vercel env (YT_COOKIES)
    2. Render path (/etc/secrets)
    3. Existing /tmp/cookies.txt
    """
    from core.config import settings
    
    writable_path = settings.cookies_writable_path
    
    def validate_and_prepare_cookie_file(source_path: str, target_path: str) -> bool:
        """Validate cookie file and convert if needed"""
        try:
            if not os.path.exists(source_path):
                return False
            
            with open(source_path, 'r') as f:
                content = f.read().strip()
            
            if not content:
                log.warning(f"Cookie file {source_path} is empty")
                return False
            
            # Try to parse as JSON first
            try:
                json.loads(content)
                # Valid JSON - just copy it
                shutil.copy(source_path, target_path)
                log.info(f"Copied valid JSON cookies from {source_path}")
                return True
            except json.JSONDecodeError:
                # Not JSON, try Netscape format
                log.info(f"Cookie file is not JSON, trying Netscape format")
                
                # Check if it looks like Netscape format
                if content.startswith('# Netscape HTTP Cookie File') or '\t' in content:
                    json_content = netscape_to_json(content)
                    if json_content:
                        with open(target_path, 'w') as f:
                            f.write(json_content)
                        log.info(f"Converted Netscape cookies from {source_path} to JSON")
                        return True
                    else:
                        log.warning(f"Failed to convert Netscape cookies from {source_path}")
                        return False
                else:
                    log.warning(f"Cookie file {source_path} is neither JSON nor Netscape format")
                    return False
                    
        except Exception as e:
            log.error(f"Error processing cookie file {source_path}: {e}")
            return False
    
    # CASE 1 — Vercel environment variable
    cookies_env = os.getenv(settings.cookies_env_var)
    if cookies_env:
        try:
            # First try as JSON
            json.loads(cookies_env)
            with open(writable_path, "w") as f:
                f.write(cookies_env)
            log.info("Loaded cookies from ENV → /tmp/cookies.txt")
            return writable_path
        except json.JSONDecodeError:
            # Try as Netscape format
            json_content = netscape_to_json(cookies_env)
            if json_content:
                with open(writable_path, "w") as f:
                    f.write(json_content)
                log.info("Converted Netscape cookies from ENV → /tmp/cookies.txt")
                return writable_path
            else:
                log.error("Invalid cookies in YT_COOKIES env var (neither JSON nor Netscape)")
        except Exception as e:
            log.error(f"Failed writing ENV cookies: {e}")
    
    # CASE 2 — Render read-only secret
    if os.path.exists(settings.cookies_readonly_path):
        if validate_and_prepare_cookie_file(settings.cookies_readonly_path, writable_path):
            return writable_path
        else:
            log.warning("Cookie file in /etc/secrets is invalid, skipping")
    
    # CASE 3 — Already exists and is valid
    if os.path.exists(writable_path):
        try:
            with open(writable_path, 'r') as f:
                content = f.read().strip()
            if content:
                # Quick validation
                json.loads(content)
                log.info("Using existing valid /tmp/cookies.txt")
                return writable_path
        except:
            pass
    
    # FAILURE
    log.warning("NO VALID COOKIES FOUND - using unauthenticated mode")
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