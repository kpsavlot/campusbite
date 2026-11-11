from enum import Enum

class UserRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    OWNER = "OWNER"
    DELIVERY = "DELIVERY"

class OrderStatus(str, Enum):
    PLACED = "PLACED"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"
    ASSIGNED = "ASSIGNED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

class PaymentStatus(str, Enum):
    mock_paid = "mock_paid"
    refunded = "refunded"

class ReturnStatus(str, Enum):
    NONE = "NONE"
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class LedgerEntryType(str, Enum):
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"

