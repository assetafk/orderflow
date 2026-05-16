from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+asyncpg://orderflow:orderflow@localhost:5432/orderflow"
    )
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_order_created_topic: str = "order.created"
    kafka_order_topic: str = "order.events"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"


settings = Settings()
