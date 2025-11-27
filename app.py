from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
from ytmusicapi import YTMusic
import os
import json
import shutil
from datetime import datetime
import requests
import hashlib
import time
from typing import Optional
import urllib.parse

app = FastAPI(title="Aureum Music API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
COOKIES_SOURCE = "/etc/secrets/cookies.txt"
COOKIES_DEST = "/tmp/cookies.txt"
AUTH_FILE = "/tmp/ytmusic_auth.json"

def setup_auth():
    """Copy cookies and setup authentication"""
    try:
        # Copy cookies file
        if os.path.exists(COOKIES_SOURCE):
            shutil.copy(COOKIES_SOURCE, COOKIES_DEST)
            print("Cookies copied successfully")
            
            # Try to initialize YTMusic with cookies file
            try:
                ytmusic = YTMusic(auth=COOKIES_DEST)
                print("YTMusic initialized with cookies file")
                return ytmusic
            except Exception as e:
                print(f"Failed to initialize with cookies: {e}")
        else:
            print(f"Warning: Cookies file not found at {COOKIES_SOURCE}")
        
        # Fallback: Try to use raw headers method
        try:
            print("Trying to initialize YTMusic without auth...")
            ytmusic = YTMusic()
            return ytmusic
        except Exception as e:
            print(f"Failed to initialize YTMusic: {e}")
            return None
            
    except Exception as e:
        print(f"Auth setup error: {e}")
        return None

# Global YTMusic instance
ytmusic_instance = None

def get_ytmusic():
    """Get YTMusic instance"""
    global ytmusic_instance
    if ytmusic_instance is None:
        ytmusic_instance = setup_auth()
    return ytmusic_instance

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    get_ytmusic()

@app.get("/")
async def root():
    return {"message": "Aureum Music API", "status": "running"}

@app.get("/health")
async def health():
    ytmusic = get_ytmusic()
    status = "healthy" if ytmusic is not None else "degraded"
    return {
        "status": status, 
        "timestamp": datetime.utcnow().isoformat(),
        "ytmusic_available": ytmusic is not None
    }

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
            if 'videoId' not in item:
                continue
                
            artists = []
            if 'artists' in item:
                artists = [artist.get('name', '') for artist in item['artists']]
            
            duration = item.get('duration', '0:00')
            duration_seconds = 0
            if duration and ':' in duration:
                parts = duration.split(':')
                if len(parts) == 2:
                    duration_seconds = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    duration_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            
            # Get the best thumbnail
            thumbnail = ""
            if item.get('thumbnails'):
                thumbnails = sorted(item['thumbnails'], key=lambda x: x.get('width', 0), reverse=True)
                thumbnail = thumbnails[0].get('url', '') if thumbnails else ""
            
            formatted_results.append({
                "videoId": item.get('videoId', ''),
                "title": item.get('title', ''),
                "artists": ", ".join(artists) if artists else "",
                "thumbnail": thumbnail,
                "duration": duration,
                "duration_seconds": duration_seconds
            })
        
        return JSONResponse(content=formatted_results)
    
    except Exception as e:
        print(f"Search error: {e}")
        # Return mock data on error
        return get_mock_search_results(q, limit)

def get_mock_search_results(q: str, limit: int):
    """Return mock search results when YTMusic is unavailable"""
    mock_tracks = [
        {
            "videoId": "mock1",
            "title": f"{q} - Sample Track 1",
            "artists": "Sample Artist",
            "thumbnail": "",
            "duration": "3:45",
            "duration_seconds": 225
        },
        {
            "videoId": "mock2", 
            "title": f"{q} - Sample Track 2",
            "artists": "Sample Artist 2",
            "thumbnail": "",
            "duration": "4:20",
            "duration_seconds": 260
        }
    ]
    return mock_tracks[:limit]

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
            "thumbnail": ""
        }
    
    try:
        ydl_opts = {
            'format': 'ba[ext=webm][acodec=opus]/bestaudio/best/bestaudio[ext=m4a]/worstaudio/best',
            'cookiefile': COOKIES_DEST if os.path.exists(COOKIES_DEST) else None,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'player_client': ["web", "android"],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={videoId}",
                download=False
            )
            
            if not info:
                raise HTTPException(status_code=404, detail="Video not found")
            
            # Get the best audio URL
            audio_url = None
            if 'url' in info:
                audio_url = info['url']
            elif 'formats' in info:
                for format in info['formats']:
                    if format.get('acodec') != 'none' and format.get('vcodec') == 'none':
                        audio_url = format.get('url')
                        if audio_url:
                            break
            
            if not audio_url:
                raise HTTPException(status_code=404, detail="No audio stream found")
            
            return {
                "videoId": videoId,
                "stream_url": audio_url,
                "title": info.get('title', ''),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', '')
            }
            
    except Exception as e:
        print(f"Stream extraction error: {e}")
        raise HTTPException(status_code=500, detail=f"Stream extraction failed: {str(e)}")

@app.get("/home")
async def get_home():
    """Get home page content like YouTube Music"""
    try:
        ytmusic = get_ytmusic()
        if ytmusic is None:
            return get_mock_home_data()
        
        home_data = ytmusic.get_home(limit=6)
        
        formatted_sections = []
        for section in home_data:
            if 'contents' in section:
                items = []
                for content in section['contents']:
                    if 'title' in content:
                        item = {
                            'title': content.get('title', ''),
                            'browseId': content.get('browseId', ''),
                            'playlistId': content.get('playlistId', ''),
                            'thumbnails': content.get('thumbnails', [])
                        }
                        items.append(item)
                
                if items:
                    formatted_sections.append({
                        'title': section.get('title', ''),
                        'items': items[:6]
                    })
        
        return JSONResponse(content=formatted_sections)
    
    except Exception as e:
        print(f"Home data error: {e}")
        return get_mock_home_data()

def get_mock_home_data():
    """Return mock home data when YTMusic is unavailable"""
    return [
        {
            "title": "Quick picks",
            "items": [
                {
                    "title": "Popular Hits",
                    "thumbnails": []
                },
                {
                    "title": "New Releases", 
                    "thumbnails": []
                },
                {
                    "title": "Chill Vibes",
                    "thumbnails": []
                }
            ]
        }
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
