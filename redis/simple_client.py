# redis/simple_client.py
import logging
from typing import Optional, Any
import json

log = logging.getLogger(__name__)

class SimpleRedisClient:
    """In-memory fallback when Redis is not available"""
    def __init__(self):
        self.data = {}
        log.info("Using in-memory Redis fallback")
    
    async def get(self, key: str) -> Optional[str]:
        value = self.data.get(key)
        if isinstance(value, dict):
            return json.dumps(value)
        return value
    
    async def set(self, key: str, value: Any, ex: int = None) -> bool:
        self.data[key] = value
        return True
    
    async def delete(self, key: str) -> bool:
        if key in self.data:
            del self.data[key]
            return True
        return False
    
    async def ping(self) -> bool:
        return True
    
    async def close(self):
        self.data.clear()
        return True
    
    async def lpush(self, key: str, value: str):
        if key not in self.data:
            self.data[key] = []
        self.data[key].insert(0, value)
        return len(self.data[key])
    
    async def lrange(self, key: str, start: int, end: int):
        if key not in self.data:
            return []
        lst = self.data[key]
        return lst[start:end+1] if end != -1 else lst[start:]
    
    async def ltrim(self, key: str, start: int, end: int):
        if key in self.data:
            self.data[key] = self.data[key][start:end+1] if end != -1 else self.data[key][start:]
            return True
        return False
    
    async def expire(self, key: str, ttl: int):
        # In-memory doesn't support TTL
        return True

# Global singleton
_simple_redis_client = None

def get_simple_redis_client() -> SimpleRedisClient:
    """Get simple Redis client (always works)"""
    global _simple_redis_client
    if _simple_redis_client is None:
        _simple_redis_client = SimpleRedisClient()
    return _simple_redis_client