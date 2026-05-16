from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.session import get_db
from app.models.order import Order, OrderStatus
from app.schemas.order import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdate,
)
from app.services.kafka_producer import publish_order_event
from app.services.order_lifecycle import validate_transition

router = APIRouter(prefix="/orders", tags=["orders"])


def _calculate_total(items: list) -> Decimal:
    total = Decimal("0")
    for item in items:
        line_total = Decimal(str(item["quantity"])) * Decimal(
            str(item["unit_price"]),
        )
        total += line_total
    return total.quantize(Decimal("0.01"))


def _serialize_items(items: list) -> list[dict]:
    return [
        {
            "product_id": item.product_id,
            "name": item.name,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
        }
        for item in items
    ]


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    body: OrderCreate,
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Order:
    items_data = _serialize_items(body.items)
    order = Order(
        user_id=user_id,
        status=OrderStatus.CREATED,
        items=items_data,
        total_amount=_calculate_total(items_data),
        currency=body.currency.upper(),
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)

    await publish_order_event(
        event_type="order.created",
        order_id=order.id,
        user_id=order.user_id,
        status=order.status.value,
        payload={
            "total_amount": str(order.total_amount),
            "currency": order.currency,
            "items": order.items,
        },
    )
    return order


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Order:
    order = await _get_user_order(db, order_id, user_id)
    return order


@router.get("", response_model=OrderListResponse)
async def list_orders(
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
) -> OrderListResponse:
    base_query = select(Order).where(Order.user_id == user_id)
    count_query = (
        select(func.count())
        .select_from(Order)
        .where(
            Order.user_id == user_id,
        )
    )

    if status_filter is not None:
        base_query = base_query.where(Order.status == status_filter)
        count_query = count_query.where(Order.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        base_query.order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset),
    )
    orders = result.scalars().all()

    return OrderListResponse(
        items=[OrderResponse.model_validate(o) for o in orders],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Order:
    order = await _get_user_order(db, order_id, user_id)
    previous_status = order.status

    try:
        validate_transition(previous_status, body.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    order.status = body.status
    await db.flush()
    await db.refresh(order)

    await publish_order_event(
        event_type="order.status_updated",
        order_id=order.id,
        user_id=order.user_id,
        status=order.status.value,
        payload={
            "previous_status": previous_status.value,
            "new_status": order.status.value,
        },
    )
    return order


async def _get_user_order(
    db: AsyncSession,
    order_id: int,
    user_id: int,
) -> Order:
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.user_id == user_id,
        ),
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return order
