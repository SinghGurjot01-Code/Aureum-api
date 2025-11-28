from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
from ytmusicapi import YTMusic
import os
import json
import shutil
from datetime import datetime
import hashlib
import time
from typing import Optional

app = FastAPI(title="Aureum Music API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths / constants
COOKIES_SOURCE = "/etc/secrets/cookies.txt"   # Render Secret File (read-only)
COOKIES_DEST = "/tmp/cookies.txt"             # Writable copy
AUTH_FILE = "/tmp/ytmusic_auth.json"          # Headers JSON for YTMusic(auth=...)

# Global YTMusic instance
ytmusic_instance: Optional[YTMusic] = None


def copy_cookies_to_tmp() -> Optional[str]:
    """Copy cookies from Render secrets into /tmp so they are readable/writable."""
    if not os.path.exists(COOKIES_SOURCE):
        print(f"[AUTH] cookies.txt not found at {COOKIES_SOURCE}")
        return None

    try:
        if not os.path.exists(COOKIES_DEST):
            shutil.copy(COOKIES_SOURCE, COOKIES_DEST)
            print(f"[AUTH] Cookies copied to {COOKIES_DEST}")
        else:
            print(f"[AUTH] Using existing {COOKIES_DEST}")
        return COOKIES_DEST
    except Exception as e:
        print(f"[AUTH] Failed to copy cookies: {e}")
        return None


def build_auth_json_from_cookies(cookie_path: str) -> Optional[str]:
    """
    Read Netscape cookies.txt, build SAPISIDHASH headers,
    and write them as JSON for YTMusic(auth=...).
    """
    try:
        cookies = {}

        with open(cookie_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]

        sapisid = (
            cookies.get("SAPISID")
            or cookies.get("__Secure-1PAPISID")
            or cookies.get("__Secure-3PAPISID")
        )

        if not sapisid:
            print("[AUTH] No SAPISID / __Secure-1PAPISID / __Secure-3PAPISID in cookies")
            return None

        origin = "https://music.youtube.com"
        timestamp = int(time.time())
        sig = hashlib.sha1(f"{timestamp} {sapisid} {origin}".encode()).hexdigest()

        headers = {
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
            "Authorization": f"SAPISIDHASH {timestamp}_{sig}",
            "User-Agent": "Mozilla/5.0",
        }

        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(headers, f)

        print(f"[AUTH] Wrote YTMusic auth JSON to {AUTH_FILE}")
        return AUTH_FILE

    except Exception as e:
        print(f"[AUTH] Failed to build auth JSON: {e}")
        return None


def setup_auth() -> Optional[YTMusic]:
    """Initialize YTMusic with cookies if possible, else fall back."""
    # 1) Copy cookies into /tmp
    cookie_dest = copy_cookies_to_tmp()

    # 2) Try full authenticated mode (SAPISIDHASH auth.json)
    if cookie_dest:
        auth_json = build_auth_json_from_cookies(cookie_dest)
        if auth_json:
            try:
                ytmusic = YTMusic(auth=auth_json)
                print("[AUTH] YTMusic initialized with auth JSON (authenticated)")
                return ytmusic
            except Exception as e:
                print(f"[AUTH] Failed with auth JSON: {e}")

        # 3) Fallback: try directly with cookie file (may fail, but harmless)
        try:
            ytmusic = YTMusic(auth=cookie_dest)
            print("[AUTH] YTMusic initialized with cookie file (legacy behaviour)")
            return ytmusic
        except Exception as e:
            print(f"[AUTH] Failed with cookie file: {e}")

    # 4) Last fallback: unauthenticated YTMusic (still works for many tracks)
    try:
        print("[AUTH] Falling back to unauthenticated YTMusic()")
        ytmusic = YTMusic()
        return ytmusic
    except Exception as e:
        print(f"[AUTH] Final YTMusic() fallback failed: {e}")
        return None


def get_ytmusic() -> Optional[YTMusic]:
    """Get or initialize the YTMusic instance."""
    global ytmusic_instance
    if ytmusic_instance is None:
        ytmusic_instance = setup_auth()
    return ytmusic_instance


@app.on_event("startup")
async def startup_event():
    """Initialize YTMusic on startup."""
    get_ytmusic()


@app.get("/")
async def root():
    ytmusic = get_ytmusic()
    return {
        "message": "Aureum Music API",
        "status": "running",
        "ytmusic_authenticated": ytmusic is not None,
    }


@app.get("/health")
async def health():
    ytmusic = get_ytmusic()
    status = "healthy" if ytmusic is not None else "degraded"
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "ytmusic_available": ytmusic is not None,
    }


# ------------------- SEARCH -------------------
@app.get("/search")
async def search(q: str, limit: int = 20):
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    try:
        ytmusic = get_ytmusic()
        if ytmusic is None:
            # Return mock data if YTMusic is not available
            return get_mock_search_results(q, limit)

        results = ytmusic.search(q, filter="songs", limit=limit)

        formatted_results = []
        for item in results:
            if "videoId" not in item:
                continue

            artists = []
            if "artists" in item:
                artists = [artist.get("name", "") for artist in item["artists"]]

            duration = item.get("duration", "0:00")
            duration_seconds = 0
            if duration and ":" in duration:
                parts = duration.split(":")
                try:
                    if len(parts) == 2:
                        duration_seconds = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        duration_seconds = (
                            int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        )
                except ValueError:
                    duration_seconds = 0

            thumbnail = ""
            if item.get("thumbnails"):
                thumbnails = sorted(
                    item["thumbnails"], key=lambda x: x.get("width", 0), reverse=True
                )
                if thumbnails:
                    thumbnail = thumbnails[0].get("url", "")

            formatted_results.append(
                {
                    "videoId": item.get("videoId", ""),
                    "title": item.get("title", ""),
                    "artists": ", ".join(artists) if artists else "",
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "duration_seconds": duration_seconds,
                }
            )

        return JSONResponse(content=formatted_results)

    except Exception as e:
        print(f"Search error: {e}")
        return get_mock_search_results(q, limit)


def get_mock_search_results(q: str, limit: int):
    """Return mock search results when YTMusic is unavailable or errors."""
    mock_tracks = [
        {
            "videoId": "mock1",
            "title": f"{q} - Sample Track 1",
            "artists": "Sample Artist",
            "thumbnail": "",
            "duration": "3:45",
            "duration_seconds": 225,
        },
        {
            "videoId": "mock2",
            "title": f"{q} - Sample Track 2",
            "artists": "Sample Artist 2",
            "thumbnail": "",
            "duration": "4:20",
            "duration_seconds": 260,
        },
    ]
    return mock_tracks[:limit]


# ------------------- STREAM -------------------
@app.get("/stream")
async def stream(videoId: str):
    if not videoId:
        raise HTTPException(status_code=400, detail="Video ID is required")

    # For mock tracks, return a mock stream URL
    if videoId.startswith("mock"):
        return {
            "videoId": videoId,
            "stream_url": "https://www.soundjay.com/music/summer-walk-01.mp3",
            "title": "Sample Track",
            "duration": 180,
            "thumbnail": "",
        }

    try:
        cookiefile = COOKIES_DEST if os.path.exists(COOKIES_DEST) else None

        # Prefer 251 (webm/opus) then other opus audio, then best audio
        ydl_opts = {
            "format": "251/bestaudio[ext=webm][acodec=opus]/bestaudio/best",
            "cookiefile": cookiefile,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/115.0.0.0 Safari/537.36"
                )
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["web", "android"],
                }
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={videoId}", download=False
            )

        if not info:
            raise HTTPException(status_code=404, detail="Video not found")

        audio_url = info.get("url")

        # Fallback: search formats if direct url missing
        if not audio_url and "formats" in info:
            formats = info["formats"]

            # 1) try explicit 251
            preferred_251 = [
                f for f in formats if f.get("format_id") == "251" and f.get("url")
            ]
            if preferred_251:
                audio_url = preferred_251[0]["url"]
            else:
                # 2) other opus webm
                opus_formats = [
                    f
                    for f in formats
                    if f.get("acodec", "").startswith("opus")
                    and f.get("url")
                ]
                if opus_formats:
                    opus_formats.sort(
                        key=lambda x: x.get("abr", 0) or 0, reverse=True
                    )
                    audio_url = opus_formats[0]["url"]
                else:
                    # 3) any audio
                    audio_formats = [
                        f
                        for f in formats
                        if f.get("acodec") != "none" and f.get("url")
                    ]
                    if audio_formats:
                        audio_formats.sort(
                            key=lambda x: x.get("abr", 0) or 0, reverse=True
                        )
                        audio_url = audio_formats[0]["url"]

        if not audio_url:
            raise HTTPException(
                status_code=404, detail="No audio stream found for this video"
            )

        return {
            "videoId": videoId,
            "stream_url": audio_url,
            "title": info.get("title", ""),
            "duration": info.get("duration", 0),
            "thumbnail": info.get("thumbnail", ""),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Stream extraction error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Stream extraction failed: {str(e)}"
        )


# ------------------- HOME -------------------
@app.get("/home")
async def get_home():
    """Get home page content like YouTube Music."""
    try:
        ytmusic = get_ytmusic()
        if ytmusic is None:
            return get_mock_home_data()

        home_data = ytmusic.get_home(limit=6)

        formatted_sections = []
        for section in home_data:
            if "contents" in section:
                items = []
                for content in section["contents"]:
                    if "title" in content:
                        items.append(
                            {
                                "title": content.get("title", ""),
                                "browseId": content.get("browseId", ""),
                                "playlistId": content.get("playlistId", ""),
                                "thumbnails": content.get("thumbnails", []),
                            }
                        )

                if items:
                    formatted_sections.append(
                        {"title": section.get("title", ""), "items": items[:6]}
                    )

        return JSONResponse(content=formatted_sections)

    except Exception as e:
        print(f"Home data error: {e}")
        return get_mock_home_data()


def get_mock_home_data():
    """Return mock home data when YTMusic is unavailable."""
    return [
        {
            "title": "Quick picks",
            "items": [
                {"title": "Popular Hits", "thumbnails": []},
                {"title": "New Releases", "thumbnails": []},
                {"title": "Chill Vibes", "thumbnails": []},
            ],
        }
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)