from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.database import Base
from app.models.enums import OrderStatus, PaymentStatus, ReturnStatus


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    delivery_partner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    status = Column(Enum(OrderStatus), default=OrderStatus.PLACED, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    delivery_address = Column(String(255), nullable=False)

    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.mock_paid, nullable=False)
    return_status = Column(Enum(ReturnStatus), default=ReturnStatus.NONE, nullable=False)
    return_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("User", back_populates="orders", foreign_keys=[customer_id])
    restaurant = relationship("Restaurant", back_populates="orders", foreign_keys=[restaurant_id])
    delivery_partner = relationship("User", back_populates="assigned_orders", foreign_keys=[delivery_partner_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    ledger_entries = relationship("PaymentLedger", back_populates="order", cascade="all, delete-orphan")
    review = relationship("Review", back_populates="order", uselist=False)