# redis/simple_client.py
import logging
from typing import Optional, Any, List
import json

log = logging.getLogger(__name__)

class SimpleRedisClient:
    """In-memory fallback when Redis is not available"""
    def __init__(self):
        self.data = {}
        self.lists = {}
        log.info("Using in-memory Redis fallback")
    
    async def get(self, key: str) -> Optional[str]:
        value = self.data.get(key)
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)
    
    async def set(self, key: str, value: Any, ex: int = None) -> bool:
        try:
            # Try to parse JSON if it looks like JSON
            if isinstance(value, str) and value.strip().startswith(('{', '[')):
                try:
                    self.data[key] = json.loads(value)
                except:
                    self.data[key] = value
            else:
                self.data[key] = value
            return True
        except Exception as e:
            log.debug(f"SimpleRedis set failed: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        if key in self.data:
            del self.data[key]
            return True
        if key in self.lists:
            del self.lists[key]
            return True
        return False
    
    async def ping(self) -> bool:
        return True
    
    async def close(self):
        self.data.clear()
        self.lists.clear()
        return True
    
    async def lpush(self, key: str, *values):
        if key not in self.lists:
            self.lists[key] = []
        for value in values:
            self.lists[key].insert(0, value)
        return len(self.lists[key])
    
    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        if key not in self.lists:
            return []
        lst = self.lists[key]
        if end == -1:
            end = len(lst)
        return lst[start:end+1]
    
    async def ltrim(self, key: str, start: int, end: int):
        if key in self.lists:
            if end == -1:
                end = len(self.lists[key]) - 1
            self.lists[key] = self.lists[key][start:end+1]
            return True
        return False
    
    async def expire(self, key: str, ttl: int):
        # In-memory doesn't support TTL
        return True
    
    async def exists(self, key: str) -> int:
        return 1 if key in self.data or key in self.lists else 0

# Global singleton
_simple_redis_client = None

def get_simple_redis_client() -> SimpleRedisClient:
    """Get simple Redis client (always works)"""
    global _simple_redis_client
    if _simple_redis_client is None:
        _simple_redis_client = SimpleRedisClient()
    return _simple_redis_client