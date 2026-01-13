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
        log.info("YTMusic initialized")
    except Exception as e:
        log.error(f"YTMusic init failed: {e}")
        ytm = None
    
    # Initialize Redis
    try:
        from redis.client import get_redis_client
        redis_client = get_redis_client()
        if redis_client:
            log.info("Redis initialized")
    except Exception as e:
        log.error(f"Redis init failed: {e}")
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
            from session.store import SessionStore
            store = SessionStore()
            await store.start_session(session_id, user_id)
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
            from session.store import SessionStore
            store = SessionStore()
            await store.record_event(session_id, event_type, video_id, user_id)
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
        from recommend.engine import RecommendationEngine
        engine = RecommendationEngine()
        return await engine.get_recommendations(current_video_id, user_id, limit)
    except Exception as e:
        log.error(f"Recommendations failed: {e}")
        from core.ytmusic_client import search_songs
        results = search_songs("popular", limit=limit)
        return {
            "tracks": results,
            "count": len(results),
            "generated_at": datetime.utcnow().isoformat()
        }

# Cache manifest
@app.post("/cache/manifest")
async def get_cache_manifest(user_id: str = None):
    try:
        from cache.manifest import CacheManifestGenerator
        generator = CacheManifestGenerator()
        return await generator.generate(user_id)
    except Exception as e:
        log.error(f"Cache manifest failed: {e}")
        return {
            "must_cache": [],
            "likely_next": [],
            "expires_at": int(datetime.utcnow().timestamp()) + 3600
        }