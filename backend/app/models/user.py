from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.database import Base
from app.models.enums import UserRole

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    phone = Column(String(13), nullable=False)
    address = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # orders placed by this user (as a customer)
    orders = relationship("Order", back_populates="customer", foreign_keys="Order.customer_id")
    # orders assigned to this user (as a delivery partner)
    assigned_orders = relationship("Order", back_populates="delivery_partner", foreign_keys="Order.delivery_partner_id")
    # restaurants owned by this user (as a restaurant owner)
    restaurant = relationship("Restaurant", back_populates="owner", uselist=False)