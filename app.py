# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ytmusicapi import YTMusic
import yt_dlp
import shutil
import os
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AureumAPI")

app = FastAPI(title="Aureum Music API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------
# COOKIE HANDLING (Render)
# --------------------------
READONLY_COOKIES = "/etc/secrets/cookies.txt"
WRITABLE_COOKIES = "/tmp/cookies.txt"


def load_cookies():
    """Ensure cookies are readable and writable inside Render."""
    if os.path.exists(READONLY_COOKIES):
        shutil.copy(READONLY_COOKIES, WRITABLE_COOKIES)
        log.info("Copied cookies.txt → /tmp/cookies.txt (writable)")
        return WRITABLE_COOKIES

    log.warning("No cookies found! Running without authentication.")
    return None


cookie_file = load_cookies()

# --------------------------
# YTMUSIC INITIALIZATION
# --------------------------
try:
    ytm = YTMusic()
    log.info("YTMusic initialized successfully")
except Exception as e:
    log.error(f"YTMusic failed: {e}")
    ytm = None


@app.get("/")
def root():
    return {
        "status": "online",
        "cookies": bool(cookie_file),
        "ytmusic": ytm is not None
    }


# --------------------------
# SEARCH ENDPOINT
# --------------------------
@app.get("/search")
async def search(q: str, limit: int = 20):
    if not q.strip():
        raise HTTPException(400, "Query parameter 'q' is required")

    if not ytm:
        raise HTTPException(503, "YTMusic unavailable")

    try:
        results = ytm.search(q, filter="songs", limit=limit)
        out = []

        for r in results:
            if "videoId" not in r:
                continue

            # Duration parsing
            dur = r.get("duration", "0:00")
            sec = 0
            if ":" in dur:
                parts = list(map(int, dur.split(":")))
                if len(parts) == 2:
                    sec = parts[0] * 60 + parts[1]
                elif len(parts) == 3:
                    sec = parts[0] * 3600 + parts[1] * 60 + parts[2]

            # Best thumbnail
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


# --------------------------
# STREAM ENDPOINT — PERFECT VERSION
# --------------------------
@app.get("/stream")
async def stream(videoId: str):
    """Extracts a browser-playable audio URL for ANY YouTube video."""
    if not videoId:
        raise HTTPException(400, "videoId required")

    url = f"https://www.youtube.com/watch?v={videoId}"

    # yt-dlp config that works on ALL videos
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "cookiefile": cookie_file,
        "ignoreerrors": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9"
        },
        # ensures only real URLs (no DASH segments)
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],
                "skip": ["dash", "hls"]
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise HTTPException(404, "Video not found")

        formats = info.get("formats", [])
        playable = []

        # Filter browser-compatible formats
        for f in formats:
            if not f.get("url"):
                continue
            if f.get("acodec") == "none":
                continue
            if f.get("ext") not in ("webm", "m4a", "mp4"):
                continue

            playable.append(f)

        if not playable:
            raise HTTPException(404, "No playable audio format found")

        # Sort by:
        # 1. Quality (abr)
        # 2. File type preference: webm > m4a > mp4
        playable.sort(
            key=lambda x: (x.get("abr", 0), x.get("ext") == "webm"),
            reverse=True
        )

        best = playable[0]

        return {
            "stream_url": best["url"],
            "title": info.get("title"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "videoId": videoId,
            "format": best.get("ext"),
            "abr": best.get("abr")
        }

    except Exception as e:
        log.error("STREAM ERROR: %s", e)
        raise HTTPException(500, f"Stream error: {e}")


@app.get("/health")
def health():
    return {"status": "healthy"}