import asyncio
import random
import uuid
from datetime import UTC, datetime

from app.core.config import settings
from app.schemas.events import OrderCreatedEvent
from app.services.idempotency import (
    IdempotencyState,
    check_idempotency,
    mark_processed,
    release_lock,
)
from app.services.kafka_producer import (
    publish_payment_completed,
    publish_payment_failed,
)


class TransientPaymentError(Exception):
    """Simulated transient failure; safe to retry."""


class PaymentDeclinedError(Exception):
    """Simulated permanent payment failure."""


async def handle_order_created(event_data: dict) -> bool:
    """
    Process an order.created event.
    Returns True if the message was handled (commit offset),
    False if the consumer should retry later.
    """
    event = OrderCreatedEvent.model_validate(event_data)
    if event.event_type != "order.created":
        return True

    state = await check_idempotency(event.order_id)
    if state == IdempotencyState.ALREADY_PROCESSED:
        return True
    if state == IdempotencyState.IN_PROGRESS:
        return False

    payment_id = str(uuid.uuid4())
    try:
        try:
            success = await _process_with_retries(event)
        except TransientPaymentError:
            await publish_payment_failed(
                order_id=event.order_id,
                user_id=event.user_id,
                payment_id=payment_id,
                payload=_build_payment_payload(
                    event,
                    payment_id,
                    reason="max_retries_exceeded",
                ),
            )
            await mark_processed(event.order_id, "failed")
            return True

        if success:
            await publish_payment_completed(
                order_id=event.order_id,
                user_id=event.user_id,
                payment_id=payment_id,
                payload=_build_payment_payload(event, payment_id),
            )
            await mark_processed(event.order_id, "completed")
        else:
            await publish_payment_failed(
                order_id=event.order_id,
                user_id=event.user_id,
                payment_id=payment_id,
                payload=_build_payment_payload(
                    event,
                    payment_id,
                    reason="payment_declined",
                ),
            )
            await mark_processed(event.order_id, "failed")
    except Exception:
        await release_lock(event.order_id)
        raise

    return True


async def _process_with_retries(event: OrderCreatedEvent) -> bool:
    last_error: TransientPaymentError | None = None
    for attempt in range(settings.payment_max_retries + 1):
        try:
            return await _simulate_payment(event)
        except PaymentDeclinedError:
            return False
        except TransientPaymentError as exc:
            last_error = exc
            if attempt >= settings.payment_max_retries:
                break
            delay = settings.payment_retry_base_delay_seconds * (
                2**attempt
            )
            await asyncio.sleep(delay)

    if last_error is not None:
        raise last_error
    return False


async def _simulate_payment(event: OrderCreatedEvent) -> bool:
    await asyncio.sleep(settings.payment_simulation_delay_seconds)

    if random.random() < settings.payment_transient_failure_rate:
        raise TransientPaymentError("Simulated gateway timeout")

    total = event.payload.get("total_amount", "0")
    if str(total).endswith("99"):
        raise PaymentDeclinedError(
            "Amount ending in 99 is declined for testing",
        )

    if random.random() < settings.payment_failure_rate:
        raise PaymentDeclinedError("Simulated card decline")

    return True


def _build_payment_payload(
    event: OrderCreatedEvent,
    payment_id: str,
    *,
    reason: str | None = None,
) -> dict:
    payload = {
        "payment_id": payment_id,
        "total_amount": event.payload.get("total_amount"),
        "currency": event.payload.get("currency"),
        "processed_at": datetime.now(UTC).isoformat(),
    }
    if reason is not None:
        payload["reason"] = reason
    return payload
