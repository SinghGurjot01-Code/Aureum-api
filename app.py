# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import uuid

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AureumAPI")

# Initialize at startup
ytm = None
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ytm, redis_client
    
    # Startup
    log.info("Starting Aureum Music API")
    
    # Initialize YTMusic
    try:
        from core.ytmusic_client import init_ytmusic
        ytm = init_ytmusic()
        if ytm:
            log.info("YTMusic initialized")
        else:
            log.warning("YTMusic failed to initialize")
    except Exception as e:
        log.error(f"YTMusic init error: {e}")
        ytm = None
    
    # Initialize Redis (always works - uses dummy if needed)
    try:
        from redis.client import get_redis_client
        redis_client = get_redis_client()
        log.info("Redis client ready")
    except Exception as e:
        log.error(f"Redis init error: {e}")
        redis_client = None
    
    yield
    
    # Shutdown
    log.info("Shutting down")
    if redis_client:
        try:
            await redis_client.close()
        except:
            pass

app = FastAPI(
    title="Aureum Music API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root
@app.get("/")
def root():
    return {
        "status": "online",
        "version": "2.0.0",
        "service": "Aureum Music API",
        "ytmusic": ytm is not None,
        "redis": redis_client is not None
    }

# Health
@app.get("/health")
def health():
    return {
        "status": "healthy" if ytm else "degraded",
        "ytmusic": ytm is not None,
        "redis": redis_client is not None
    }

# Original search endpoint (preserved)
@app.get("/search")
async def search(q: str, limit: int = 20):
    if not q or not q.strip():
        raise HTTPException(400, "Missing search query")
    
    if not ytm:
        raise HTTPException(503, "Service unavailable")
    
    try:
        from core.ytmusic_client import search_songs
        return search_songs(q, limit)
    except Exception as e:
        log.error(f"Search failed: {e}")
        return []

# Session endpoints
@app.post("/session/start")
async def session_start(user_id: str = None):
    session_id = str(uuid.uuid4())
    
    if redis_client:
        try:
            data = {
                "id": session_id,
                "user_id": user_id,
                "created": datetime.utcnow().isoformat()
            }
            await redis_client.set(f"session:{session_id}", str(data), ex=86400)
            return {"session_id": session_id, "status": "started"}
        except Exception as e:
            log.error(f"Session start failed: {e}")
    
    return {"session_id": session_id, "status": "created"}

@app.post("/session/event")
async def session_event(
    session_id: str,
    event_type: str,
    video_id: str = None,
    user_id: str = None
):
    if redis_client:
        try:
            data = {
                "session_id": session_id,
                "event_type": event_type,
                "video_id": video_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            key = f"event:{session_id}:{datetime.utcnow().timestamp()}"
            await redis_client.set(key, str(data), ex=604800)
            
            # Update user activity
            if user_id and video_id:
                activity_key = f"activity:{user_id}"
                await redis_client.lpush(activity_key, str({
                    "video_id": video_id,
                    "event_type": event_type,
                    "timestamp": datetime.utcnow().isoformat()
                }))
                await redis_client.ltrim(activity_key, 0, 49)
            return {"status": "recorded"}
        except Exception as e:
            log.error(f"Session event failed: {e}")
    
    return {"status": "received"}

# Recommendations
@app.post("/recommend/contextual")
async def get_recommendations(
    current_video_id: str = None,
    user_id: str = None,
    limit: int = 20
):
    if not ytm:
        return {"tracks": [], "reason": "service_unavailable"}
    
    try:
        from core.ytmusic_client import search_songs
        
        # Simple recommendation logic
        if current_video_id:
            results = search_songs("music", limit=limit)
        elif user_id and redis_client:
            # Try to get user's recent activity
            try:
                activity_key = f"activity:{user_id}"
                activities = await redis_client.lrange(activity_key, 0, 4)
                if activities:
                    results = search_songs("similar music", limit=limit)
                else:
                    results = search_songs("popular", limit=limit)
            except:
                results = search_songs("popular", limit=limit)
        else:
            results = search_songs("trending", limit=limit)
        
        # Add labels
        labeled_tracks = []
        for i, track in enumerate(results):
            label = "Recommended"
            if i == 0:
                label = "Top Pick"
            elif i < 3:
                label = "Trending"
            
            labeled_tracks.append({
                **track,
                "label": label,
                "score": 1.0 - (i * 0.05)
            })
        
        return {
            "tracks": labeled_tracks,
            "count": len(results),
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        log.error(f"Recommendations failed: {e}")
        return {"tracks": []}

# Cache manifest endpoint
@app.post("/cache/manifest")
async def get_cache_manifest(user_id: str = None):
    if not ytm:
        return {"must_cache": [], "likely_next": []}
    
    try:
        from core.ytmusic_client import search_songs
        
        # Get popular tracks
        popular = search_songs("popular music", limit=10)
        
        # Get trending tracks
        trending = search_songs("trending", limit=10)
        
        return {
            "must_cache": popular[:5],
            "likely_next": trending[:10],
            "expires_at": int(datetime.utcnow().timestamp()) + 86400
        }
    except Exception as e:
        log.error(f"Cache manifest failed: {e}")
        return {"must_cache": [], "likely_next": []}