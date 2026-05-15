from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes import auth
from app.db.base import Base
from app.db.session import engine
from app.models import user  # noqa: F401
from app.services.redis_client import close_redis, get_redis


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await get_redis()
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="Orderflow Auth Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)


@app.get("/health")
async def health() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    redis = await get_redis()
    await redis.ping()
    return {"status": "ok", "service": "auth"}
