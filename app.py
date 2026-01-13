# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from datetime import datetime

# Import modules
from core import config
from core.ytmusic_client import init_ytmusic, search_songs

# Try to import Redis client, but don't crash if it fails
try:
    from redis.client import get_redis_client
    REDIS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Redis import failed: {e}. Running without Redis.")
    REDIS_AVAILABLE = False

try:
    from session.store import SessionStore
    SESSION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Session import failed: {e}. Running without session tracking.")
    SESSION_AVAILABLE = False

try:
    from recommend.engine import RecommendationEngine
    from cache.manifest import CacheManifestGenerator
    RECOMMENDATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Recommendation import failed: {e}. Running without recommendations.")
    RECOMMENDATION_AVAILABLE = False

try:
    from models.schemas import (
        SessionStartRequest, SessionEventRequest,
        RecommendationRequest, RecommendationResponse,
        CacheManifestResponse
    )
    MODELS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Models import failed: {e}")
    MODELS_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AureumAPI")

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("Starting Aureum Music API")
    
    # Initialize YTMusic
    ytm = init_ytmusic()
    if not ytm:
        log.warning("YTMusic initialization failed")
    
    # Initialize Redis if available
    if REDIS_AVAILABLE:
        redis_client = get_redis_client()
        if redis_client:
            log.info("Redis connection initialized")
        else:
            log.warning("Redis connection failed - running in fallback mode")
    
    yield
    
    # Shutdown
    log.info("Shutting down Aureum Music API")

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
        "features": {
            "search": True,
            "session_tracking": SESSION_AVAILABLE,
            "recommendations": RECOMMENDATION_AVAILABLE,
            "redis_available": REDIS_AVAILABLE
        }
    }

@app.get("/health")
def health():
    from core.ytmusic_client import ytm
    
    return {
        "status": "healthy",
        "ytmusic_ready": ytm is not None,
        "redis_ready": REDIS_AVAILABLE,
        "version": "2.0.0",
        "features": {
            "session_tracking": SESSION_AVAILABLE,
            "recommendations": RECOMMENDATION_AVAILABLE
        }
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
# SESSION TRACKING ENDPOINTS (NEW - Conditional)
# ---------------------------------------------------
if SESSION_AVAILABLE and MODELS_AVAILABLE:
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
else:
    # Provide fallback endpoints if imports failed
    @app.post("/session/start")
    async def session_start_fallback():
        import uuid
        return {"session_id": str(uuid.uuid4()), "status": "fallback_no_redis"}

    @app.post("/session/event")
    async def session_event_fallback():
        return {"status": "recorded_fallback", "warning": "redis_not_available"}

# ---------------------------------------------------
# CONTEXT-AWARE RECOMMENDATIONS (NEW - Conditional)
# ---------------------------------------------------
if RECOMMENDATION_AVAILABLE and MODELS_AVAILABLE:
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
else:
    @app.post("/recommend/contextual")
    async def contextual_recommendations_fallback():
        return {
            "tracks": [],
            "labels": [],
            "context": {},
            "generated_at": datetime.utcnow().isoformat()
        }

# ---------------------------------------------------
# OFFLINE CACHE PREDICTION (NEW - Conditional)
# ---------------------------------------------------
if RECOMMENDATION_AVAILABLE and MODELS_AVAILABLE:
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
else:
    @app.post("/cache/manifest")
    async def cache_manifest_fallback():
        return {
            "must_cache": [],
            "likely_next": [],
            "expires_at": int(datetime.utcnow().timestamp()) + 3600
        }