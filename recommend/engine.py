# recommend/engine.py

import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from core import ytmusic_client
from redis.client import get_redis_client

log = logging.getLogger(__name__)


class RecommendationEngine:
    def __init__(self):
        # Redis MUST NOT be initialized here (async)
        self._redis = None

    async def _get_redis(self):
        """
        Lazy async Redis initialization.
        Safe to call multiple times.
        """
        if self._redis is None:
            try:
                self._redis = await get_redis_client()
            except Exception as e:
                log.debug(f"Redis unavailable: {e}")
                self._redis = None
        return self._redis

    async def _get_intent(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Determine user intent.
        Placeholder for future behavioral logic.
        """
        return "neutral"

    async def _apply_intent_ordering(
        self,
        tracks: List[Dict[str, Any]],
        intent: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Apply intent-based score adjustments.
        """
        if intent == "artist-loop" and context.get("current_artist"):
            current_artist = context["current_artist"].lower()
            for track in tracks:
                if current_artist in track.get("artists", "").lower():
                    track["score"] = track.get("score", 0) + 0.3

        elif intent == "explore":
            seen_artists = set()
            for track in tracks:
                artists = track.get("artists", "")
                if artists and artists not in seen_artists:
                    track["score"] = track.get("score", 0) + 0.2
                    seen_artists.add(artists)

        return sorted(tracks, key=lambda x: x.get("score", 0), reverse=True)

    async def get_recommendations(
        self,
        current_video_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        try:
            intent = await self._get_intent(user_id, session_id)

            redis = await self._get_redis()

            # -----------------------------
            # Load recent user activity
            # -----------------------------
            recent_tracks: List[str] = []

            if user_id and redis:
                try:
                    raw = await redis.lrange(f"activity:{user_id}", 0, 9)
                    for item in raw:
                        try:
                            data = json.loads(item)
                            if "video_id" in data:
                                recent_tracks.append(data["video_id"])
                        except Exception:
                            continue
                except Exception as e:
                    log.debug(f"Activity fetch failed: {e}")

            context: Dict[str, Any] = {
                "has_history": bool(recent_tracks)
            }

            tracks: List[Dict[str, Any]] = []

            # -----------------------------
            # Recommendation sources
            # -----------------------------
            if current_video_id:
                watch_tracks = ytmusic_client.get_watch_playlist(
                    current_video_id,
                    radio=True
                )
                if watch_tracks:
                    tracks = watch_tracks[:limit]
                    context["source"] = "radio"
                else:
                    tracks = ytmusic_client.search_songs(
                        "similar music",
                        limit=limit
                    )
                    context["source"] = "search"

            elif recent_tracks:
                try:
                    last_track = recent_tracks[0]
                    watch_tracks = ytmusic_client.get_watch_playlist(
                        last_track,
                        radio=True
                    )
                    if watch_tracks:
                        tracks = watch_tracks[:limit]
                        context["source"] = "history_radio"
                    else:
                        tracks = ytmusic_client.search_songs(
                            "popular",
                            limit=limit
                        )
                        context["source"] = "popular"
                except Exception:
                    tracks = ytmusic_client.search_songs(
                        "popular",
                        limit=limit
                    )
                    context["source"] = "popular_fallback"

            else:
                charts = ytmusic_client.get_charts("IN")
                if charts and charts.get("tracks"):
                    tracks = [
                        {
                            "videoId": t.get("videoId", ""),
                            "title": t.get("title", ""),
                            "artists": ", ".join(
                                a["name"] for a in t.get("artists", [])
                            ),
                            "duration": t.get("duration", ""),
                            "thumbnail": (
                                t.get("thumbnails", [{}])[-1].get("url", "")
                                if t.get("thumbnails")
                                else ""
                            )
                        }
                        for t in charts["tracks"][:limit]
                    ]
                    context["source"] = "charts"
                else:
                    tracks = ytmusic_client.search_songs(
                        "trending music",
                        limit=limit
                    )
                    context["source"] = "search_fallback"

            # -----------------------------
            # Label + score
            # -----------------------------
            labeled_tracks: List[Dict[str, Any]] = []

            for i, track in enumerate(tracks):
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

            if current_video_id and tracks:
                context["current_artist"] = tracks[0].get("artists", "")

            ordered = await self._apply_intent_ordering(
                labeled_tracks,
                intent,
                context
            )

            return {
                "tracks": ordered[:limit],
                "context": {
                    **context,
                    "intent": intent,
                    "has_history": bool(recent_tracks),
                    "has_current": current_video_id is not None
                },
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            log.error(f"Recommendation failed: {e}")
            return {
                "tracks": [],
                "context": {
                    "intent": "neutral",
                    "source": "error"
                },
                "generated_at": datetime.utcnow().isoformat()
            }
