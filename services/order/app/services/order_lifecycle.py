from app.models.order import OrderStatus

VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {
        OrderStatus.PAYMENT_PENDING,
        OrderStatus.FAILED,
    },
    OrderStatus.PAYMENT_PENDING: {
        OrderStatus.PAID,
        OrderStatus.FAILED,
    },
    OrderStatus.PAID: {
        OrderStatus.PROCESSING,
        OrderStatus.FAILED,
    },
    OrderStatus.PROCESSING: {
        OrderStatus.COMPLETED,
        OrderStatus.FAILED,
    },
    OrderStatus.COMPLETED: set(),
    OrderStatus.FAILED: set(),
}


def can_transition(
    current: OrderStatus,
    target: OrderStatus,
) -> bool:
    if current == target:
        return False
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed


def validate_transition(
    current: OrderStatus,
    target: OrderStatus,
) -> None:
    if not can_transition(current, target):
        allowed = VALID_TRANSITIONS.get(current, set())
        allowed_names = ", ".join(s.value for s in sorted(allowed, key=lambda x: x.value))
        raise ValueError(
            f"Cannot transition from '{current.value}' to '{target.value}'. "
            f"Allowed: {allowed_names or 'none (terminal state)'}",
        )
