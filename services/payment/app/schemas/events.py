from typing import Any

from pydantic import BaseModel, Field


class OrderCreatedEvent(BaseModel):
    event_type: str
    order_id: int
    user_id: int
    status: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


class PaymentEvent(BaseModel):
    event_type: str
    order_id: int
    user_id: int
    payment_id: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)
