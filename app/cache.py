import os
import json
from typing import Any, Optional, Callable
from functools import wraps
import redis.asyncio as redis
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "local.env"))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

VALKEY_URL = os.getenv("VALKEY_URL", "redis://localhost:6379/0")

# Global Valkey connection pool
_valkey_pool = redis.ConnectionPool.from_url(VALKEY_URL, decode_responses=True)

def get_valkey_client() -> redis.Redis:
    """Returns an asynchronous Valkey (Redis compatible) client."""
    return redis.Redis(connection_pool=_valkey_pool)

async def close_valkey_pool():
    """Close the Valkey connection pool gracefully."""
    await _valkey_pool.disconnect()

async def get_cache(key: str) -> Optional[Any]:
    """Retrieve and deserialize a JSON-encoded value from Valkey."""
    client = get_valkey_client()
    try:
        data = await client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"Valkey cache read error for key {key}: {e}")
    return None

async def set_cache(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """Serialize and store a value in Valkey with a TTL."""
    client = get_valkey_client()
    try:
        serialized = json.dumps(value)
        await client.setex(key, ttl_seconds, serialized)
        return True
    except Exception as e:
        print(f"Valkey cache write error for key {key}: {e}")
    return False

def cached_async(ttl_seconds: int = 300):
    """
    Decorator for async functions to cache their results in Valkey.
    Includes function name and arguments in the cache key.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Construct a unique cache key based on the function name and arguments
            key_parts = [func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_result = await get_cache(cache_key)
            if cached_result is not None:
                return cached_result
                
            # If not in cache, execute the function
            result = await func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                 await set_cache(cache_key, result, ttl_seconds)
                 
            return result
        return wrapper
    return decorator
