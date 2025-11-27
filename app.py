# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ytmusicapi import YTMusic
import yt_dlp
import os
from typing import List, Optional
import json

app = FastAPI(title="Aureum Music API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ytmusicapi with cookies file
def initialize_ytmusic():
    cookies_file = "/etc/secrets/cookies.txt"
    
    if os.path.exists(cookies_file):
        try:
            print("Loading cookies from file...")
            return YTMusic(auth=cookies_file)
        except Exception as e:
            print(f"Failed to load cookies from file: {e}")
            print("Falling back to default YTMusic initialization...")
    
    # Fallback to default initialization
    return YTMusic()

# Initialize ytmusic
ytmusic = initialize_ytmusic()

@app.get("/")
async def root():
    return {"message": "Aureum Music API - Premium Streaming Service"}

@app.get("/search")
async def search_music(q: str, limit: int = 20):
    """
    Search for music using YouTube Music API
    """
    try:
        if not q or len(q.strip()) == 0:
            raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
        
        search_results = ytmusic.search(q, filter="songs", limit=limit)
        
        formatted_results = []
        for result in search_results:
            # Extract duration if available
            duration_seconds = 0
            if 'duration' in result and result['duration']:
                time_parts = result['duration'].split(':')
                if len(time_parts) == 2:
                    duration_seconds = int(time_parts[0]) * 60 + int(time_parts[1])
                elif len(time_parts) == 3:
                    duration_seconds = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
            
            # Get artist names
            artists = []
            if 'artists' in result:
                artists = [artist['name'] for artist in result['artists']]
            
            formatted_result = {
                "videoId": result.get('videoId', ''),
                "title": result.get('title', 'Unknown Title'),
                "artists": ", ".join(artists) if artists else "Unknown Artist",
                "thumbnail": result.get('thumbnails', [{}])[-1].get('url', '') if result.get('thumbnails') else '',
                "duration": result.get('duration', '0:00'),
                "duration_seconds": duration_seconds
            }
            formatted_results.append(formatted_result)
        
        return JSONResponse(content=formatted_results)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/stream")
async def get_stream_url(videoId: str):
    """
    Get streamable audio URL for a YouTube video ID
    """
    try:
        if not videoId:
            raise HTTPException(status_code=400, detail="videoId parameter is required")
        
        cookies_file = "/etc/secrets/cookies.txt"
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'noplaylist': True,
        }
        
        # Add cookies to yt-dlp if available
        if os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file
            print("Using cookies for yt-dlp stream extraction")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get video info without downloading
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={videoId}",
                download=False
            )
            
            # Find the best audio URL
            audio_url = None
            if 'url' in info:
                audio_url = info['url']
            elif 'formats' in info:
                # Look for audio formats and pick the best one
                audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                if audio_formats:
                    # Sort by bitrate and get the highest quality
                    audio_formats.sort(key=lambda x: x.get('abr', 0) or 0, reverse=True)
                    audio_url = audio_formats[0]['url']
            
            if not audio_url:
                raise HTTPException(status_code=404, detail="No audio stream found")
            
            # Get additional track info
            duration = info.get('duration', 0)
            title = info.get('title', 'Unknown Title')
            thumbnail = info.get('thumbnail', '')
            
            return {
                "stream_url": audio_url,
                "title": title,
                "duration": duration,
                "thumbnail": thumbnail,
                "videoId": videoId
            }
    
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm you're not a bot" in error_msg:
            raise HTTPException(
                status_code=403, 
                detail="YouTube requires authentication. Please ensure cookies.txt is properly formatted and contains valid YouTube session cookies."
            )
        raise HTTPException(status_code=500, detail=f"Stream URL extraction failed: {error_msg}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Aureum Music API"}

@app.get("/cookies-status")
async def cookies_status():
    """
    Check if cookies are properly loaded
    """
    cookies_file = "/etc/secrets/cookies.txt"
    cookies_exists = os.path.exists(cookies_file)
    
    # Check cookies file content
    cookies_content = None
    if cookies_exists:
        try:
            with open(cookies_file, 'r') as f:
                cookies_content = f.read()
        except Exception as e:
            cookies_content = f"Error reading file: {e}"
    
    try:
        # Test if YTMusic is working with current auth
        test_search = ytmusic.search("test", limit=1)
        ytmusic_working = True
        ytmusic_error = None
    except Exception as e:
        ytmusic_working = False
        ytmusic_error = str(e)
    
    # Test yt-dlp with cookies
    ytdlp_working = False
    ytdlp_error = None
    try:
        test_ydl_opts = {'quiet': True, 'no_warnings': True}
        if cookies_exists:
            test_ydl_opts['cookiefile'] = cookies_file
        
        with yt_dlp.YoutubeDL(test_ydl_opts) as ydl:
            # Try to get info for a simple video
            info = ydl.extract_info("https://www.youtube.com/watch?v=GC3d_sY-qwM", download=False)
            ytdlp_working = True
    except Exception as e:
        ytdlp_error = str(e)
    
    return {
        "cookies_file_exists": cookies_exists,
        "cookies_file_path": cookies_file,
        "cookies_file_size": len(cookies_content) if cookies_content else 0,
        "ytmusic_working": ytmusic_working,
        "ytmusic_error": ytmusic_error,
        "ytdlp_working": ytdlp_working,
        "ytdlp_error": ytdlp_error,
        "cookies_preview": cookies_content[:500] + "..." if cookies_content and len(cookies_content) > 500 else cookies_content
    }

@app.get("/test-stream")
async def test_stream():
    """
    Test endpoint to check if streaming works with a known video
    """
    test_video_id = "GC3d_sY-qwM"  # YouTube's test video
    try:
        cookies_file = "/etc/secrets/cookies.txt"
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }
        
        if os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={test_video_id}",
                download=False
            )
            
            audio_url = None
            if 'url' in info:
                audio_url = info['url']
            elif 'formats' in info:
                audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                if audio_formats:
                    audio_formats.sort(key=lambda x: x.get('abr', 0) or 0, reverse=True)
                    audio_url = audio_formats[0]['url']
            
            return {
                "success": True,
                "video_id": test_video_id,
                "has_audio_url": audio_url is not None,
                "title": info.get('title'),
                "duration": info.get('duration'),
                "cookies_used": os.path.exists(cookies_file)
            }
    
    except Exception as e:
        return {
            "success": False,
            "video_id": test_video_id,
            "error": str(e),
            "cookies_used": os.path.exists("/etc/secrets/cookies.txt")
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
