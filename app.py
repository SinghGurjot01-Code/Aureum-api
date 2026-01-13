# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import uuid

# Set up logging first
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AureumAPI")

# Initialize with defaults
ytm = None
redis_client = None

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("Starting Aureum Music API")
    
    global ytm, redis_client
    
    # Initialize YTMusic
    try:
        from core.ytmusic_client import init_ytmusic
        ytm = init_ytmusic()
        if ytm:
            log.info("YTMusic initialized")
        else:
            log.warning("YTMusic initialization failed")
    except Exception as e:
        log.error(f"YTMusic import failed: {e}")
        ytm = None
    
    # Initialize Redis
    try:
        from redis.client import get_redis_client
        redis_client = get_redis_client()
        if redis_client:
            log.info("Redis client initialized")
        else:
            log.warning("Redis client initialization failed")
    except Exception as e:
        log.error(f"Redis import failed: {e}")
        redis_client = None
    
    yield
    
    # Shutdown
    log.info("Shutting down Aureum Music API")
    if redis_client:
        try:
            await redis_client.close()
        except:
            pass

app = FastAPI(
    title="Aureum Music API",
    description="Backend for Aureum Music",
    version="2.0.0",
    lifespan=lifespan
)

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
# HEALTH & ROOT
# ---------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "online",
        "version": "2.0.0",
        "message": "Aureum Music API",
        "endpoints": {
            "/search": "GET - Search for songs",
            "/session/start": "POST - Start session",
            "/session/event": "POST - Record event",
            "/recommend/contextual": "POST - Get recommendations",
            "/cache/manifest": "POST - Get cache manifest"
        }
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "ytmusic_ready": ytm is not None,
        "redis_ready": redis_client is not None,
        "version": "2.0.0"
    }

# ---------------------------------------------------
# SEARCH ENDPOINT (Original - Preserved)
# ---------------------------------------------------
@app.get("/search")
async def search(q: str, limit: int = 20):
    """Original search endpoint - fully backward compatible"""
    if not q.strip():
        raise HTTPException(400, "Missing ?q")
    
    if ytm is None:
        raise HTTPException(503, "Search service unavailable")
    
    try:
        from core.ytmusic_client import search_songs
        results = search_songs(q, limit)
        return results
    except Exception as e:
        log.error(f"SEARCH ERROR: {e}")
        return []

# ---------------------------------------------------
# SESSION TRACKING ENDPOINTS
# ---------------------------------------------------
@app.post("/session/start")
async def session_start(user_id: str = None, device_info: str = None, location: str = None):
    """Start a new listening session"""
    session_id = str(uuid.uuid4())
    
    if redis_client:
        try:
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "device_info": device_info,
                "location": location,
                "started_at": datetime.utcnow().isoformat()
            }
            await redis_client.set(f"session:{session_id}", str(session_data), ex=86400)
            return {"session_id": session_id, "status": "started"}
        except Exception as e:
            log.error(f"Session start error: {e}")
    
    return {"session_id": session_id, "status": "started_fallback"}

@app.post("/session/event")
async def session_event(
    session_id: str,
    event_type: str,
    video_id: str = None,
    user_id: str = None
):
    """Record a session event"""
    if redis_client:
        try:
            event_data = {
                "session_id": session_id,
                "event_type": event_type,
                "video_id": video_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            event_key = f"event:{session_id}:{datetime.utcnow().timestamp()}"
            await redis_client.set(event_key, str(event_data), ex=604800)
            
            # Also update recent activity
            if user_id and video_id:
                activity_key = f"activity:{user_id}"
                await redis_client.lpush(activity_key, str({
                    "video_id": video_id,
                    "event_type": event_type,
                    "timestamp": datetime.utcnow().isoformat()
                }))
                await redis_client.ltrim(activity_key, 0, 49)  # Keep last 50
            
            return {"status": "recorded"}
        except Exception as e:
            log.error(f"Session event error: {e}")
    
    return {"status": "recorded_fallback"}

# ---------------------------------------------------
# CONTEXT-AWARE RECOMMENDATIONS (Simplified)
# ---------------------------------------------------
@app.post("/recommend/contextual")
async def contextual_recommendations(
    current_video_id: str = None,
    user_id: str = None,
    limit: int = 20
):
    """Get context-aware recommendations"""
    
    # Fallback recommendations based on current video
    recommendations = []
    
    if current_video_id and ytm:
        try:
            # Get artist from current video (simplified)
            from core.ytmusic_client import search_songs
            # Search for similar
            results = search_songs("music", limit=limit)
            for i, track in enumerate(results):
                label = "Recommended"
                if i == 0:
                    label = "Popular now"
                elif i < 3:
                    label = "Trending"
                
                recommendations.append({
                    **track,
                    "label": label,
                    "score": 1.0 - (i * 0.05)
                })
        except Exception as e:
            log.error(f"Recommendation error: {e}")
    
    return {
        "tracks": recommendations,
        "labels": [t.get("label", "") for t in recommendations if t.get("label")],
        "context": {"source": "fallback"},
        "generated_at": datetime.utcnow().isoformat()
    }

# ---------------------------------------------------
# OFFLINE CACHE PREDICTION (Simplified)
# ---------------------------------------------------
@app.post("/cache/manifest")
async def cache_manifest(user_id: str = None):
    """Generate cache prediction"""
    
    must_cache = []
    likely_next = []
    
    if ytm:
        try:
            from core.ytmusic_client import search_songs
            # Get popular tracks
            popular = search_songs("popular", limit=5)
            must_cache = popular
            
            # Get trending tracks
            trending = search_songs("trending", limit=10)
            likely_next = trending
        except Exception as e:
            log.error(f"Cache manifest error: {e}")
    
    return {
        "must_cache": must_cache[:5],
        "likely_next": likely_next[:10],
        "expires_at": int(datetime.utcnow().timestamp()) + 86400  # 24 hours
    }