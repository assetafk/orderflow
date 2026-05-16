import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.services.kafka_consumer import (
    start_kafka_consumer,
    stop_kafka_consumer,
)
from app.services.kafka_producer import (
    start_kafka_producer,
    stop_kafka_producer,
)
from app.services.redis_client import close_redis, get_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await get_redis()
    await start_kafka_producer()
    await start_kafka_consumer()
    logger.info("Payment service started")
    yield
    await stop_kafka_consumer()
    await stop_kafka_producer()
    await close_redis()
    logger.info("Payment service stopped")


app = FastAPI(
    title="Orderflow Payment Service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    redis = await get_redis()
    await redis.ping()
    return {"status": "ok", "service": "payment"}
