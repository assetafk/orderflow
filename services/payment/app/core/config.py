from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/1"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "payment-service"
    kafka_order_created_topic: str = "order.created"
    kafka_payment_completed_topic: str = "payment.completed"
    kafka_payment_failed_topic: str = "payment.failed"
    payment_max_retries: int = 3
    payment_retry_base_delay_seconds: float = 0.5
    payment_simulation_delay_seconds: float = 0.2
    payment_failure_rate: float = 0.1
    payment_transient_failure_rate: float = 0.15
    idempotency_ttl_seconds: int = 604_800


settings = Settings()
