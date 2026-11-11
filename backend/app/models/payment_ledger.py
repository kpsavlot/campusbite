from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric 
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.database import Base
from app.models.enums import LedgerEntryType


class PaymentLedger(Base):
    __tablename__ = "payment_ledger"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    entry_type = Column(Enum(LedgerEntryType), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="ledger_entries")