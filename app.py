# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import ytmusicapi
import yt_dlp
import os

app = FastAPI(title="Aureum Music API")

# -------------------------------
# CORS CONFIG
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# COOKIE FILE HANDLING
# -------------------------------
COOKIES_PATH = "/etc/secrets/cookies.txt"

if not os.path.exists(COOKIES_PATH):
    raise RuntimeError(
        f"cookies.txt not found at {COOKIES_PATH}. "
        f"Upload cookies.txt in Render → Secret Files."
    )

# Correct initialization (cookiefile= — not JSON)
try:
    ytmusic = ytmusicapi.YTMusic(cookiefile=COOKIES_PATH)
except Exception as e:
    raise RuntimeError(f"Failed to initialize YTMusic with cookies: {str(e)}")

# -------------------------------
# ROUTES
# -------------------------------
@app.get("/")
async def root():
    return {"message": "Aureum Music API - Premium Streaming Service"}


# -------------------------------
# SEARCH ENDPOINT
# -------------------------------
@app.get("/search")
async def search_music(q: str, limit: int = 20):
    """
    Search music on YouTube Music
    """
    try:
        if not q.strip():
            raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

        search_results = ytmusic.search(q, filter="songs", limit=limit)

        formatted_results = []
        for r in search_results:
            # Parse duration
            duration_sec = 0
            if r.get("duration"):
                parts = r["duration"].split(":")
                if len(parts) == 2:
                    duration_sec = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    duration_sec = (
                        int(parts[0]) * 3600
                        + int(parts[1]) * 60
                        + int(parts[2])
                    )

            # Parse artists
            artists = [a["name"] for a in r.get("artists", [])]

            formatted_results.append({
                "videoId": r.get("videoId", ""),
                "title": r.get("title", "Unknown Title"),
                "artists": ", ".join(artists) if artists else "Unknown Artist",
                "thumbnail": r.get("thumbnails", [{}])[-1].get("url", ""),
                "duration": r.get("duration", "0:00"),
                "duration_seconds": duration_sec
            })

        return JSONResponse(content=formatted_results)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# -------------------------------
# STREAM ENDPOINT
# -------------------------------
@app.get("/stream")
async def get_stream_url(videoId: str):
    """
    Get streamable audio URL for a videoId
    """
    try:
        if not videoId:
            raise HTTPException(status_code=400, detail="videoId is required")

        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "cookiefile": COOKIES_PATH,   # required for age/region locked content
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={videoId}",
                download=False
            )

            # Best audio URL
            audio_url = None

            if "url" in info:
                audio_url = info["url"]
            else:
                audio_formats = [
                    f for f in info.get("formats", [])
                    if f.get("acodec") != "none" and f.get("vcodec") == "none"
                ]
                if audio_formats:
                    audio_formats.sort(key=lambda x: x.get("abr", 0) or 0, reverse=True)
                    audio_url = audio_formats[0].get("url")

            if not audio_url:
                raise HTTPException(status_code=404, detail="No audio stream found")

            return {
                "stream_url": audio_url,
                "title": info.get("title"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "videoId": videoId
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream URL extraction failed: {str(e)}")


# -------------------------------
# HEALTH CHECK
# -------------------------------
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Aureum API"}


# -------------------------------
# DEV MODE
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
