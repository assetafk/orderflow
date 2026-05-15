import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from aiokafka import AIOKafkaProducer

from app.core.config import settings

_producer: AIOKafkaProducer | None = None


class DecimalEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


async def start_kafka_producer() -> None:
    global _producer
    if _producer is not None:
        return
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(
            v,
            cls=DecimalEncoder,
        ).encode("utf-8"),
    )
    await _producer.start()


async def stop_kafka_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


async def publish_order_event(
    event_type: str,
    order_id: int,
    user_id: int,
    status: str,
    payload: dict | None = None,
) -> None:
    if _producer is None:
        raise RuntimeError("Kafka producer is not started")

    event = {
        "event_type": event_type,
        "order_id": order_id,
        "user_id": user_id,
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    }
    await _producer.send_and_wait(
        settings.kafka_order_topic,
        value=event,
        key=str(order_id).encode("utf-8"),
    )
