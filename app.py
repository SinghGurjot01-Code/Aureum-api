# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import shutil
import os
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AureumAPI")

app = FastAPI(title="Aureum Music API (Stable Version)")

# ---------------------------------------------------
# CORS
# ---------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------
# COOKIE HANDLING (Render Safe)
# /etc/secrets/cookies.txt → /tmp/cookies.txt
# ---------------------------------------------------
READONLY = "/etc/secrets/cookies.txt"
WRITABLE = "/tmp/cookies.txt"

def load_cookies():
    if os.path.exists(READONLY):
        try:
            shutil.copy(READONLY, WRITABLE)
            log.info("Copied cookies.txt → /tmp/cookies.txt")
            return WRITABLE
        except Exception as e:
            log.error(f"Failed copying cookies: {e}")
    else:
        log.warning("cookies.txt not found in /etc/secrets")

    return None

cookie_path = load_cookies()

# ---------------------------------------------------
# YTMUSIC INITIALIZATION WITH COOKIES
# ---------------------------------------------------
def init_ytmusic():
    try:
        if cookie_path:
            ytm = YTMusic(auth=cookie_path)
            log.info("YTMusic authenticated with cookies (OK)")
            return ytm
    except Exception as e:
        log.error(f"YTMusic cookie auth failed: {e}")

    # fallback
    try:
        ytm = YTMusic()
        log.info("YTMusic initialized without cookies (Fallback)")
        return ytm
    except:
        log.error("YTMusic could not initialize at all")
        return None

ytm = init_ytmusic()

# ---------------------------------------------------
# ROOT
# ---------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "online",
        "cookies_loaded": cookie_path is not None,
        "ytmusic_ready": ytm is not None,
        "message": "Use /search and play with Hidden YouTube Player."
    }

# ---------------------------------------------------
# SEARCH ENDPOINT (Perfect & Stable)
# ---------------------------------------------------
@app.get("/search")
async def search(q: str, limit: int = 20):
    if not q.strip():
        raise HTTPException(400, "Missing ?q")

    if not ytm:
        raise HTTPException(503, "YTMusic unavailable")

    try:
        results = ytm.search(q, filter="songs", limit=limit)
        out = []

        for r in results:
            if "videoId" not in r:
                continue

            # parse duration safely
            dur = r.get("duration", "0:00")
            sec = 0
            if ":" in dur:
                parts = list(map(int, dur.split(":")))
                if len(parts) == 2:
                    sec = parts[0]*60 + parts[1]
                elif len(parts) == 3:
                    sec = parts[0]*3600 + parts[1]*60 + parts[2]

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
        log.error("SEARCH ERROR: %s", e)
        raise HTTPException(500, f"Search failed: {e}")

# ---------------------------------------------------
# HEALTH
# ---------------------------------------------------
@app.get("/health")
def health():
    return {"status": "healthy", "ytmusic": ytm is not None}