# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import yt_dlp
import os
import time
import hashlib
import logging

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aureum-api")

# ---------- FastAPI App ----------
app = FastAPI(title="Aureum Music API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # front-end from any domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Where your cookies live (Render secret file or local dev)
COOKIES_FILE = "/etc/secrets/cookies.txt"

# =====================================================
# COOKIE → SAPISIDHASH AUTH FOR YTMusic
# =====================================================
def load_cookies_as_headers(cookie_file: str) -> dict:
    """
    Parse a Netscape cookies.txt and build headers compatible
    with YouTube Music's SAPISIDHASH auth scheme.
    """
    if not os.path.exists(cookie_file):
        raise RuntimeError(f"cookies.txt not found at {cookie_file}")

    cookies = {}

    with open(cookie_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 7:
                name = parts[5]
                value = parts[6]
                cookies[name] = value

    sapisid = (
        cookies.get("SAPISID")
        or cookies.get("__Secure-3PAPISID")
        or cookies.get("__Secure-1PAPISID")
    )
    if not sapisid:
        raise RuntimeError("No SAPISID/__Secure-PAPISID cookie found for auth")

    origin = "https://music.youtube.com"
    timestamp = int(time.time())
    hash_str = f"{timestamp} {sapisid} {origin}".encode()
    sapisidhash = hashlib.sha1(hash_str).hexdigest()

    headers = {
        "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "Authorization": f"SAPISIDHASH {timestamp}_{sapisidhash}",
        "User-Agent": "Mozilla/5.0",
    }
    return headers


# =====================================================
# INIT YTMUSIC
# =====================================================
try:
    if os.path.exists(COOKIES_FILE):
        logger.info(f"Using cookies from {COOKIES_FILE} for YTMusic auth")
        headers_raw = load_cookies_as_headers(COOKIES_FILE)
        ytmusic = YTMusic(headers_raw=headers_raw)
        logger.info("YTMusic authenticated successfully")
    else:
        logger.warning("cookies.txt not found – using unauthenticated YTMusic()")
        ytmusic = YTMusic()
except Exception as e:
    logger.error(f"YTMusic auth failed, falling back to unauthenticated: {e}")
    ytmusic = YTMusic()


# =====================================================
# BASIC ROUTES
# =====================================================
@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Aureum Music API",
        "cookies_present": os.path.exists(COOKIES_FILE),
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# =====================================================
# SEARCH ENDPOINT
# =====================================================
@app.get("/search")
async def search_music(q: str, limit: int = 20):
    """
    Search songs via YouTube Music.
    """
    try:
        if not q or not q.strip():
            raise HTTPException(status_code=400, detail="Query 'q' is required")

        logger.info(f"Search request: {q} (limit={limit})")
        results = ytmusic.search(q, filter="songs", limit=limit)

        formatted = []
        for r in results:
            # duration string → seconds
            duration_sec = 0
            if r.get("duration"):
                t = r["duration"].split(":")
                try:
                    if len(t) == 2:
                        duration_sec = int(t[0]) * 60 + int(t[1])
                    elif len(t) == 3:
                        duration_sec = int(t[0]) * 3600 + int(t[1]) * 60 + int(t[2])
                except ValueError:
                    duration_sec = 0

            artists = [a["name"] for a in r.get("artists", [])]

            formatted.append(
                {
                    "videoId": r.get("videoId", "") or "",
                    "title": r.get("title", "Unknown"),
                    "artists": ", ".join(artists) if artists else "Unknown Artist",
                    "thumbnail": r.get("thumbnails", [{}])[-1].get("url", ""),
                    "duration": r.get("duration", "0:00"),
                    "duration_seconds": duration_sec,
                }
            )

        logger.info(f"Search returned {len(formatted)} tracks")
        return formatted

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Search failed")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# =====================================================
# STREAM ENDPOINT
# =====================================================
@app.get("/stream")
async def stream_music(videoId: str):
    """
    Get a streamable audio URL for a YouTube videoId.
    """
    try:
        if not videoId:
            raise HTTPException(status_code=400, detail="videoId is required")

        logger.info(f"Stream request for videoId={videoId}")

        # Strong 2025-proof format chain:
        # - Opus audio
        # - best audio
        # - fallback to muxed best video+audio if needed
        ydl_opts = {
            "format": (
                "ba[ext=webm][acodec=opus]/"
                "ba/bestaudio/best/"
                "bestvideo*+bestaudio/best"
            ),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
            "http_headers": {
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["web", "android"],
                }
            },
        }

        url = f"https://www.youtube.com/watch?v={videoId}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Step 1: direct URL
        audio_url = info.get("url")

        # Step 2: choose best format with audio
        if not audio_url and "formats" in info:
            formats = info.get("formats", [])
            audio_formats = [
                f
                for f in formats
                if f.get("acodec") and f.get("acodec") != "none" and f.get("url")
            ]
            if audio_formats:
                # sort by bitrate (abr) descending
                audio_formats.sort(key=lambda x: x.get("abr", 0) or 0, reverse=True)
                audio_url = audio_formats[0].get("url")

        if not audio_url:
            logger.error("No usable audio stream found")
            raise HTTPException(
                status_code=404,
                detail="No audio stream available for this video.",
            )

        logger.info(f"Stream ready: {info.get('title', 'Unknown title')}")
        return {
            "stream_url": audio_url,
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "thumbnail": info.get("thumbnail", ""),
            "videoId": videoId,
        }

    except HTTPException:
        raise
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp DownloadError: {e}")
        raise HTTPException(
            status_code=502,
            detail="YouTube rejected the request or no valid formats were found.",
        )
    except Exception as e:
        logger.exception("Stream extraction failed")
        raise HTTPException(status_code=500, detail=f"Stream extraction failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
