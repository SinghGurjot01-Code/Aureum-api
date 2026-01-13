# Aureum Music Backend

FastAPI backend for Aureum Music with intelligence features.

## Features
- Search songs (YouTube Music)
- Session tracking (Redis)
- Context-aware recommendations
- Smart cache prediction

## Endpoints
- `GET /` - Root
- `GET /health` - Health check
- `GET /search?q=...` - Search songs
- `POST /session/start` - Start session
- `POST /session/event` - Record event
- `POST /recommend/contextual` - Get recommendations
- `POST /cache/manifest` - Get cache prediction

## Environment Variables
- `REDIS_URL` - Redis connection URL (optional)
- Cookie file at `/etc/secrets/cookies.txt` (optional)

## Deployment on Render
1. Set environment variables
2. Add cookie file to Render secrets if needed
3. Deploy!

## File Structure
- `app.py` - Main FastAPI app
- `core/` - Core functionality
- `redis/` - Redis client
- `session/` - Session tracking
- `recommend/` - Recommendation engine
- `cache/` - Cache prediction
- `models/` - Pydantic models