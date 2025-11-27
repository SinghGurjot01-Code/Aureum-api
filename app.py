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
    """Copy cookies and generate auth file"""
    try:
        # Copy cookies file
        if os.path.exists(COOKIES_SOURCE):
            shutil.copy(COOKIES_SOURCE, COOKIES_DEST)
            print("Cookies copied successfully")
        else:
            print(f"Warning: Cookies file not found at {COOKIES_SOURCE}")
        
        # Generate SAPISIDHASH
        sapisid = None
        if os.path.exists(COOKIES_DEST):
            with open(COOKIES_DEST, 'r') as f:
                for line in f:
                    if 'SAPISID' in line:
                        parts = line.strip().split('\t')
                        if len(parts) >= 7:
                            sapisid = parts[6]
                            break
        
        if sapisid:
            timestamp = str(int(time.time()))
            hash_input = f"{timestamp} {sapisid} https://music.youtube.com"
            sapisidhash = hashlib.sha1(hash_input.encode()).hexdigest()
            
            auth_data = {
                "header": f"SAPISIDHASH {timestamp}_{sapisidhash}",
                "origin": "https://music.youtube.com"
            }
            
            with open(AUTH_FILE, 'w') as f:
                json.dump(auth_data, f)
            print("Auth file generated successfully")
        else:
            print("Warning: SAPISID not found in cookies")
            
    except Exception as e:
        print(f"Auth setup error: {e}")

# Initialize auth on startup
@app.on_event("startup")
async def startup_event():
    setup_auth()

def get_ytmusic():
    """Get YTMusic instance with auth"""
    try:
        if os.path.exists(AUTH_FILE):
            return YTMusic(auth=AUTH_FILE)
        return YTMusic()
    except Exception as e:
        print(f"YTMusic init error: {e}")
        return YTMusic()

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/search")
async def search(q: str, limit: int = 20):
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    
    try:
        ytmusic = get_ytmusic()
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
            
            # Get the best thumbnail (highest resolution)
            thumbnail = ""
            if item.get('thumbnails'):
                # Sort by width to get the highest resolution
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
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/stream")
async def stream(videoId: str):
    if not videoId:
        raise HTTPException(status_code=400, detail="Video ID is required")
    
    try:
        ydl_opts = {
            'format': 'ba[ext=webm][acodec=opus]/bestaudio/best/bestaudio[ext=m4a]/worstaudio/best',
            'cookiefile': COOKIES_DEST if os.path.exists(COOKIES_DEST) else None,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'player_client': ["web", "android"],
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
        raise HTTPException(status_code=500, detail=f"Stream extraction failed: {str(e)}")

@app.get("/home")
async def get_home():
    """Get home page content like YouTube Music"""
    try:
        ytmusic = get_ytmusic()
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
                        'items': items[:6]  # Limit to 6 items per section
                    })
        
        return JSONResponse(content=formatted_sections)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Home data failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
