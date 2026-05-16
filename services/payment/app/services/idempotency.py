from enum import Enum

from app.core.config import settings
from app.services.redis_client import get_redis

PROCESSED_PREFIX = "payment:processed:"
LOCK_PREFIX = "payment:lock:"


class IdempotencyState(str, Enum):
    ACQUIRED = "acquired"
    ALREADY_PROCESSED = "already_processed"
    IN_PROGRESS = "in_progress"


async def check_idempotency(order_id: int) -> IdempotencyState:
    client = await get_redis()
    processed_key = f"{PROCESSED_PREFIX}{order_id}"
    existing = await client.get(processed_key)
    if existing is not None:
        return IdempotencyState.ALREADY_PROCESSED

    lock_key = f"{LOCK_PREFIX}{order_id}"
    acquired = await client.set(
        lock_key,
        "1",
        nx=True,
        ex=300,
    )
    if not acquired:
        return IdempotencyState.IN_PROGRESS
    return IdempotencyState.ACQUIRED


async def mark_processed(order_id: int, outcome: str) -> None:
    client = await get_redis()
    processed_key = f"{PROCESSED_PREFIX}{order_id}"
    await client.set(
        processed_key,
        outcome,
        ex=settings.idempotency_ttl_seconds,
    )
    await client.delete(f"{LOCK_PREFIX}{order_id}")


async def release_lock(order_id: int) -> None:
    client = await get_redis()
    await client.delete(f"{LOCK_PREFIX}{order_id}")
