import redis.asyncio as redis

from app.core.config import settings

_redis: redis.Redis | None = None

REFRESH_TOKEN_PREFIX = "refresh_token:"


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def store_refresh_token(
    jti: str,
    user_id: int,
    ttl_seconds: int,
) -> None:
    client = await get_redis()
    key = f"{REFRESH_TOKEN_PREFIX}{jti}"
    await client.setex(key, ttl_seconds, str(user_id))


async def get_refresh_token_user_id(jti: str) -> int | None:
    client = await get_redis()
    key = f"{REFRESH_TOKEN_PREFIX}{jti}"
    value = await client.get(key)
    return int(value) if value is not None else None


async def revoke_refresh_token(jti: str) -> None:
    client = await get_redis()
    key = f"{REFRESH_TOKEN_PREFIX}{jti}"
    await client.delete(key)
