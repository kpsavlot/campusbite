from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    cuisine = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

    owner = relationship("User", back_populates="restaurant")
    menu_items = relationship("MenuItem", back_populates="restaurant")
    orders = relationship("Order", back_populates="restaurant", foreign_keys="Order.restaurant_id")
