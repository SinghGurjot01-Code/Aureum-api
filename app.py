# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

# Import modules
from core import config
from core.ytmusic_client import init_ytmusic, search_songs
from redis.client import get_redis_client
from session.store import SessionStore
from recommend.engine import RecommendationEngine
from cache.manifest import CacheManifestGenerator
from models.schemas import (
    SessionStartRequest, SessionEventRequest,
    RecommendationRequest, RecommendationResponse,
    CacheManifestResponse
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AureumAPI")

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("Starting Aureum Music API")
    
    # Initialize Redis connection
    redis_client = get_redis_client()
    if redis_client:
        log.info("Redis connection initialized")
    else:
        log.warning("Redis connection failed - running in fallback mode")
    
    # Initialize YTMusic
    ytm = init_ytmusic()
    if not ytm:
        log.warning("YTMusic initialization failed")
    
    yield
    
    # Shutdown
    log.info("Shutting down Aureum Music API")
    if redis_client:
        await redis_client.close()

app = FastAPI(
    title="Aureum Music API (Intelligence Engine)",
    description="Backend intelligence engine for music recommendations and context-aware features",
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
# HEALTH & ROOT (Preserved)
# ---------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "online",
        "version": "2.0.0",
        "message": "Aureum Music Intelligence Engine",
        "features": [
            "search",
            "session_tracking",
            "contextual_recommendations",
            "offline_cache_prediction"
        ]
    }

@app.get("/health")
def health():
    from core.ytmusic_client import ytm
    from redis.client import redis_client
    
    return {
        "status": "healthy",
        "ytmusic_ready": ytm is not None,
        "redis_ready": redis_client is not None,
        "version": "2.0.0"
    }

# ---------------------------------------------------
# SEARCH ENDPOINT (Preserved - No Changes)
# ---------------------------------------------------
@app.get("/search")
async def search(q: str, limit: int = 20):
    """Original search endpoint - fully backward compatible"""
    if not q.strip():
        raise HTTPException(400, "Missing ?q")
    
    try:
        results = search_songs(q, limit)
        return results
    except Exception as e:
        log.error(f"SEARCH ERROR: {e}")
        # Return empty array instead of crashing (fail safe)
        return []

# ---------------------------------------------------
# SESSION TRACKING ENDPOINTS (NEW)
# ---------------------------------------------------
@app.post("/session/start")
async def session_start(request: SessionStartRequest):
    """Start a new listening session"""
    try:
        session_store = SessionStore()
        session_id = await session_store.start_session(
            user_id=request.user_id,
            device_info=request.device_info,
            location=request.location
        )
        return {"session_id": session_id, "status": "started"}
    except Exception as e:
        log.error(f"Session start error: {e}")
        # Generate fallback session ID
        import uuid
        return {"session_id": str(uuid.uuid4()), "status": "fallback"}

@app.post("/session/event")
async def session_event(request: SessionEventRequest):
    """Record a session event (play, pause, skip, etc.)"""
    try:
        session_store = SessionStore()
        await session_store.record_event(
            session_id=request.session_id,
            event_type=request.event_type,
            video_id=request.video_id,
            timestamp=request.timestamp,
            user_id=request.user_id,
            additional_data=request.additional_data
        )
        return {"status": "recorded"}
    except Exception as e:
        log.error(f"Session event error: {e}")
        return {"status": "failed", "error": "event_not_recorded"}

# ---------------------------------------------------
# CONTEXT-AWARE RECOMMENDATIONS (NEW)
# ---------------------------------------------------
@app.post("/recommend/contextual")
async def contextual_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    """Get context-aware recommendations"""
    try:
        engine = RecommendationEngine()
        recommendations = await engine.get_contextual_recommendations(
            current_track=request.current_track,
            recent_activity=request.recent_activity,
            user_id=request.user_id,
            taste_profile=request.taste_profile,
            limit=request.limit
        )
        return recommendations
    except Exception as e:
        log.error(f"Recommendation error: {e}")
        # Return empty recommendations instead of error
        return RecommendationResponse(
            tracks=[],
            labels=[],
            context={},
            generated_at=datetime.utcnow().isoformat()
        )

# ---------------------------------------------------
# OFFLINE CACHE PREDICTION (NEW)
# ---------------------------------------------------
@app.post("/cache/manifest")
async def cache_manifest(user_id: str = None) -> CacheManifestResponse:
    """Generate intelligent offline cache prediction"""
    try:
        generator = CacheManifestGenerator()
        manifest = await generator.generate_manifest(user_id)
        return manifest
    except Exception as e:
        log.error(f"Cache manifest error: {e}")
        # Return empty manifest instead of error
        return CacheManifestResponse(
            must_cache=[],
            likely_next=[],
            expires_at=int(datetime.utcnow().timestamp()) + 3600  # 1 hour fallback
        )