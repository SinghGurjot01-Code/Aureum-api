# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ytmusicapi import YTMusic
import yt_dlp
import os
import shutil
import time
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AureumMusicAPI")

app = FastAPI(title="Aureum Music API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# COOKIE PATHS
# -----------------------------
READONLY_COOKIES = "/etc/secrets/cookies.txt"
WRITABLE_COOKIES = "/tmp/cookies.txt"


# -----------------------------
# COPY COOKIES TO WRITABLE DIR
# -----------------------------
def prepare_cookies():
    if not os.path.exists(READONLY_COOKIES):
        log.error("cookies.txt not found in Render Secrets")
        return None

    try:
        shutil.copy(READONLY_COOKIES, WRITABLE_COOKIES)
        log.info(f"Copied cookies → {WRITABLE_COOKIES}")
        return WRITABLE_COOKIES
    except Exception as e:
        log.error(f"Failed to copy cookies: {e}")
        return None


# -----------------------------
# YTMUSIC AUTH (NO headers_raw)
# -----------------------------
def init_ytmusic(cookies):
    try:
        return YTMusic(auth=cookies)
    except Exception as e:
        log.warning(f"YTMusic failed with cookies: {e}")

        try:
            return YTMusic()  # Unauthenticated fallback
        except:
            return None


# -----------------------------
# INITIALIZE AT STARTUP
# -----------------------------
cookies_path = prepare_cookies()
ytmusic = init_ytmusic(cookies_path)


@app.get("/")
def root():
    return {
        "service": "Aureum Music API",
        "status": "online",
        "cookies_loaded": cookies_path is not None,
        "ytmusic_status": "ready" if ytmusic else "unavailable"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy" if ytmusic else "degraded",
        "cookies": cookies_path is not None
    }


# -----------------------------
# SEARCH ENDPOINT
# -----------------------------
@app.get("/search")
async def search(q: str, limit: int = 20):
    if not q.strip():
        raise HTTPException(400, "Missing search query")

    try:
        results = ytmusic.search(q, filter="songs", limit=limit)
        out = []

        for r in results:
            if "videoId" not in r:
                continue

            # duration parsing
            sec = 0
            if r.get("duration"):
                parts = r["duration"].split(":")
                if len(parts) == 2:
                    sec = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

            artists = [a["name"] for a in r.get("artists", [])]

            out.append({
                "videoId": r["videoId"],
                "title": r.get("title", ""),
                "artists": ", ".join(artists),
                "thumbnail": r.get("thumbnails", [{}])[-1].get("url", ""),
                "duration": r.get("duration", "0:00"),
                "duration_seconds": sec
            })

        return out

    except Exception as e:
        raise HTTPException(500, f"Search failed: {e}")


# -----------------------------
# UNIVERSAL STREAM EXTRACTOR
# (PLAYS **ALL** AUDIO TYPES)
# -----------------------------
@app.get("/stream")
async def stream(videoId: str):
    if not videoId:
        raise HTTPException(400, "Missing videoId")

    url = f"https://www.youtube.com/watch?v={videoId}"

    cookiefile = WRITABLE_COOKIES if os.path.exists(WRITABLE_COOKIES) else None

    # 100% bulletproof fallback chain
    FORMAT_CHAIN = (
        "251/"                              # best opus (preferred)
        "ba[ext=webm][acodec=opus]/"        # any opus
        "bestaudio[ext=m4a]/"               # m4a fallback
        "bestaudio/"                        # fallback
        "best/"                             # anything playable
        "worstaudio"                        # last resort
    )

    ydl_opts = {
        "format": FORMAT_CHAIN,
        "cookiefile": cookiefile,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "ignore_no_formats_error": True,

        "http_headers": {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9"
        },

        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android"]
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise HTTPException(404, "Video not found")

        audio_url = info.get("url")

        # Manual fallback search
        if not audio_url and "formats" in info:
            formats = info["formats"]

            # Layer 1: exact 251
            fm_251 = [f for f in formats if f.get("format_id") == "251" and f.get("url")]
            if fm_251:
                audio_url = fm_251[0]["url"]

            # Layer 2: opus formats
            if not audio_url:
                opus_formats = [
                    f for f in formats
                    if f.get("acodec", "").startswith("opus") and f.get("url")
                ]
                if opus_formats:
                    opus_formats.sort(key=lambda x: x.get("abr", 0) or 0, reverse=True)
                    audio_url = opus_formats[0]["url"]

            # Layer 3: audio-only
            if not audio_url:
                audio_only = [
                    f for f in formats
                    if f.get("vcodec") == "none" and f.get("url")
                ]
                if audio_only:
                    audio_only.sort(key=lambda x: x.get("abr", 0) or 0, reverse=True)
                    audio_url = audio_only[0]["url"]

            # Layer 4: any audio available
            if not audio_url:
                with_audio = [
                    f for f in formats
                    if f.get("acodec") != "none" and f.get("url")
                ]
                if with_audio:
                    with_audio.sort(key=lambda x: x.get("abr", 0) or 0, reverse=True)
                    audio_url = with_audio[0]["url"]

        if not audio_url:
            raise HTTPException(404, "No playable audio stream found")

        return {
            "videoId": videoId,
            "stream_url": audio_url,
            "title": info.get("title", ""),
            "duration": info.get("duration", 0),
            "thumbnail": info.get("thumbnail", "")
        }

    except Exception as e:
        raise HTTPException(500, f"Stream extraction failed: {e}")


# -----------------------------
# RUN LOCALLY
# -----------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)