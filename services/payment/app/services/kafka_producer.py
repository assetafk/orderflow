import json
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaProducer

from app.core.config import settings

_producer: AIOKafkaProducer | None = None


async def start_kafka_producer() -> None:
    global _producer
    if _producer is not None:
        return
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await _producer.start()


async def stop_kafka_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


def _build_event(
    event_type: str,
    order_id: int,
    user_id: int,
    payment_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "order_id": order_id,
        "user_id": user_id,
        "payment_id": payment_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    }


async def _publish(topic: str, event: dict[str, Any], order_id: int) -> None:
    if _producer is None:
        raise RuntimeError("Kafka producer is not started")
    await _producer.send_and_wait(
        topic,
        value=event,
        key=str(order_id).encode("utf-8"),
    )


async def publish_payment_completed(
    order_id: int,
    user_id: int,
    payment_id: str,
    payload: dict[str, Any] | None = None,
) -> None:
    event = _build_event(
        "payment.completed",
        order_id,
        user_id,
        payment_id,
        payload,
    )
    await _publish(
        settings.kafka_payment_completed_topic,
        event,
        order_id,
    )


async def publish_payment_failed(
    order_id: int,
    user_id: int,
    payment_id: str,
    payload: dict[str, Any] | None = None,
) -> None:
    event = _build_event(
        "payment.failed",
        order_id,
        user_id,
        payment_id,
        payload,
    )
    await _publish(
        settings.kafka_payment_failed_topic,
        event,
        order_id,
    )
