import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from app.core.config import settings
from app.services.payment_processor import (
    TransientPaymentError,
    handle_order_created,
)

logger = logging.getLogger(__name__)

_consumer: AIOKafkaConsumer | None = None
_consumer_task: asyncio.Task | None = None


async def start_kafka_consumer() -> None:
    global _consumer, _consumer_task
    if _consumer_task is not None:
        return

    _consumer = AIOKafkaConsumer(
        settings.kafka_order_created_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    await _consumer.start()
    _consumer_task = asyncio.create_task(_consume_loop())


async def stop_kafka_consumer() -> None:
    global _consumer, _consumer_task
    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None

    if _consumer is not None:
        await _consumer.stop()
        _consumer = None


async def _consume_loop() -> None:
    assert _consumer is not None
    while True:
        try:
            batch = await _consumer.getmany(timeout_ms=1000, max_records=10)
            for _tp, messages in batch.items():
                for message in messages:
                    await _handle_message(message)
        except asyncio.CancelledError:
            raise
        except KafkaError:
            logger.exception("Kafka consumer error")
            await asyncio.sleep(1)


async def _handle_message(message) -> None:
    assert _consumer is not None
    try:
        handled = await handle_order_created(message.value)
    except TransientPaymentError:
        logger.warning(
            "Transient payment error for order %s; will retry",
            message.value.get("order_id"),
        )
        handled = False
    except Exception:
        logger.exception(
            "Unexpected error processing order %s",
            message.value.get("order_id"),
        )
        handled = False

    if handled:
        await _consumer.commit({message.topic_partition: message.offset + 1})
