# Aureum Music Backend (Intelligence Engine)

## Overview
Production backend for Aureum Music, upgraded from search proxy to intelligence engine with:
- Context-aware recommendations
- Session tracking and analytics
- Smart offline cache prediction
- Enhanced search with fuzzy matching

## Preserved Behavior
- `/search` endpoint: 100% backward compatible
- Cookie handling: Same as before (Render + Vercel)
- Response shapes: Unchanged for existing endpoints
- No authentication required

## New Features
### 1. Session Tracking
- `POST /session/start` - Start new session
- `POST /session/event` - Record events (play, pause, skip)
- Stores in Redis with TTL

### 2. Context-Aware Recommendations
- `POST /recommend/contextual` - Get intelligent recommendations
- Considers: current track, recent activity, time of day, skip patterns
- Returns labeled tracks with scores

### 3. Offline Cache Prediction
- `POST /cache/manifest` - Generate cache prediction
- Returns: must_cache (essential tracks), likely_next (predicted tracks)
- Personalized for authenticated users, generic for anonymous

## Environment Variables
```bash
# Redis (required for new features)
REDIS_URL=redis://...
# or
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=...

# Existing cookie support
YT_COOKIES=...  # Vercel