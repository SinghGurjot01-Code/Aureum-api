# redis/client.py
import logging
import os
from typing import Optional, Any, List

log = logging.getLogger(__name__)

# Global Redis client
redis_client = None

class DummyRedis:
    """Dummy Redis client that does nothing but doesn't crash"""
    def __init__(self):
        self.data = {}
        self.lists = {}
    
    async def get(self, key: str) -> Optional[str]:
        return self.data.get(key)
    
    async def set(self, key: str, value: Any, ex: int = None) -> bool:
        self.data[key] = value
        return True
    
    async def delete(self, key: str) -> bool:
        if key in self.data:
            del self.data[key]
            return True
        return False
    
    async def close(self):
        self.data.clear()
        self.lists.clear()
    
    async def lpush(self, key: str, *values) -> int:
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
            end = len(lst) - 1
        return lst[start:end+1]
    
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        if key in self.lists:
            if end == -1:
                end = len(self.lists[key]) - 1
            self.lists[key] = self.lists[key][start:end+1]
            return True
        return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        # Dummy client doesn't support TTL
        return True

def get_redis_client() -> Any:
    """Get Redis client that never crashes"""
    global redis_client
    
    if redis_client:
        return redis_client
    
    # Try multiple Redis import strategies
    redis_module = None
    redis_available = False
    
    # Strategy 1: Try import directly
    try:
        import redis
        redis_module = redis
        redis_available = True
        log.info("Redis module imported successfully")
    except ImportError:
        log.warning("Redis package not installed")
        redis_available = False
    
    # If Redis is not available or import failed, use dummy
    if not redis_available:
        redis_client = DummyRedis()
        log.info("Using dummy Redis client")
        return redis_client
    
    # Try to create Redis connection
    try:
        # Get Redis URL from environment
        redis_url = os.getenv("REDIS_URL")
        
        if redis_url:
            # Try from_url method
            if hasattr(redis_module, 'from_url'):
                client = redis_module.from_url(redis_url, decode_responses=True)
                log.info(f"Connected to Redis via URL: {redis_url[:50]}...")
            else:
                # Older redis versions might not have from_url
                raise AttributeError("redis.from_url not available")
        else:
            # Use host/port configuration
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            password = os.getenv("REDIS_PASSWORD")
            db = int(os.getenv("REDIS_DB", "0"))
            
            # Check if it's Redis or StrictRedis
            if hasattr(redis_module, 'Redis'):
                client_class = redis_module.Redis
            elif hasattr(redis_module, 'StrictRedis'):
                client_class = redis_module.StrictRedis
            else:
                raise AttributeError("No Redis client class found")
            
            client = client_class(
                host=host,
                port=port,
                password=password,
                db=db,
                decode_responses=True
            )
            log.info(f"Connected to Redis at {host}:{port}")
        
        # Test connection
        try:
            client.ping()
        except AttributeError:
            # Some clients might not have ping
            pass
        
        # Wrap sync client with async methods if needed
        class RedisWrapper:
            def __init__(self, client):
                self.client = client
            
            async def get(self, key):
                return self.client.get(key)
            
            async def set(self, key, value, ex=None):
                return self.client.set(key, value, ex=ex)
            
            async def delete(self, key):
                return self.client.delete(key)
            
            async def close(self):
                self.client.close()
            
            async def lpush(self, key, *values):
                return self.client.lpush(key, *values)
            
            async def lrange(self, key, start, end):
                return self.client.lrange(key, start, end)
            
            async def ltrim(self, key, start, end):
                return self.client.ltrim(key, start, end)
            
            async def expire(self, key, ttl):
                return self.client.expire(key, ttl)
        
        redis_client = RedisWrapper(client)
        log.info("Redis client initialized successfully")
        
    except Exception as e:
        log.error(f"Redis connection failed: {e}")
        redis_client = DummyRedis()
        log.info("Fell back to dummy Redis client")
    
    return redis_client