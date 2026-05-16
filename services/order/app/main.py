from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes import orders
from app.db.base import Base
from app.db.session import engine
from app.models import order  # noqa: F401
from app.services.kafka_producer import (
    start_kafka_producer,
    stop_kafka_producer,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await start_kafka_producer()
    yield
    await stop_kafka_producer()
    await engine.dispose()


app = FastAPI(
    title="Orderflow Order Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(orders.router)


@app.get("/health")
async def health() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "service": "order"}
