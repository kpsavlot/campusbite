from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime

from app.models.enums import OrderStatus, PaymentStatus, ReturnStatus

class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int = Field(default=1, ge=1, le=20)

class OrderCreate(BaseModel):
    restaurant_id: int
    delivery_address: str = Field(min_length=1, max_length=255)
    items: List[OrderItemCreate] = Field(min_length=1, max_length=50)

    model_config=ConfigDict(str_strip_whitespace=True)

class OrderItemOut(BaseModel):
    menu_item_id: int
    name: str
    quantity: int
    unit_price: float

    model_config=ConfigDict(from_attributes=True)

class UserBrief(BaseModel):
    id: int
    name: str
    phone: str
    address: Optional[str]

    model_config=ConfigDict(from_attributes=True)

class OrderOut(BaseModel):
    id: int
    restaurant_id: int
    restaurant_name: str
    status: OrderStatus
    total_amount: float
    delivery_address: str
    payment_status: PaymentStatus
    return_status: ReturnStatus
    return_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemOut]
    customer: UserBrief
    delivery_partner: Optional[UserBrief] = None

    model_config=ConfigDict(from_attributes=True)

class OrderPage(BaseModel):
    items: List[OrderOut]
    total: int
    page: int
    limit: int
    pages: int

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

class AssignDelivery(BaseModel):
    delivery_partner_id: int