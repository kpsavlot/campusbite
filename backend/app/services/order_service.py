from app.models.enums import UserRole
from app.models.order import Order, OrderStatus
from app.models.user import User

from fastapi import HTTPException, status


ALLOWED_TRANSITIONS = {
    OrderStatus.PLACED: {OrderStatus.ACCEPTED, OrderStatus.CANCELLED},
    OrderStatus.ACCEPTED: {OrderStatus.PREPARING},
    OrderStatus.PREPARING: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.ASSIGNED},
    OrderStatus.ASSIGNED: {OrderStatus.OUT_FOR_DELIVERY},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: {OrderStatus.REFUNDED},
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
}

TRANSITION_ROLES = {
    (OrderStatus.PLACED, OrderStatus.ACCEPTED): UserRole.OWNER,
    (OrderStatus.PLACED, OrderStatus.CANCELLED): UserRole.CUSTOMER,
    (OrderStatus.ACCEPTED, OrderStatus.PREPARING): UserRole.OWNER,
    (OrderStatus.PREPARING, OrderStatus.READY): UserRole.OWNER,
    (OrderStatus.READY, OrderStatus.ASSIGNED): UserRole.OWNER,
    (OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY): UserRole.DELIVERY,
    (OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED): UserRole.DELIVERY,
    (OrderStatus.DELIVERED, OrderStatus.REFUNDED): UserRole.OWNER,
}

def change_status(order: Order, new_status: OrderStatus, actor: User):
    current = order.status

    allowed_targets = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move order from {current.value} to {new_status.value}"
        )

    required_role = TRANSITION_ROLES[(current, new_status)]
    if actor.role != required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only a {required_role.value} can move an order from "
            f"{current.value} to {new_status.value}"
        )

    order.status = new_status
    return order


    