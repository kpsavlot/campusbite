from fastapi import FastAPI, status, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from typing import Optional, List
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session, Query as sql_query
from sqlalchemy import or_, func

from datetime import date, datetime, timedelta

from app.db.database import engine, Base, get_db

from app.models.enums import UserRole, OrderStatus, PaymentStatus, LedgerEntryType
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.menu_item import MenuItem
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.payment_ledger import PaymentLedger

from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user, require_roles
from app.core.pagination import paginate

from app.schemas.auth import UserOut, UserRegister, TokenResponse, UserLogin
from app.schemas.restaurant import RestaurantPage, RestaurantOut
from app.schemas.menu import MenuItemPage, MenuItemCreate, MenuItemOut, MenuItemUpdate, AvailabilityUpdate
from app.schemas.order import OrderOut, OrderCreate, OrderPage, OrderStatusUpdate, UserBrief, AssignDelivery

from app.services.order_service import change_status

import logging
import time

# ----------- Configuring Logger -----------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("campusbite")


# ----------- Setup FastAPI ---------------

app = FastAPI(title="CampusBite API")
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# -------------- AUTH ---------------

@app.post(
    "/auth/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Auth"]
)
def register(
    payload: UserRegister,
    db: Session = Depends(get_db)
):
    if payload.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can self-register"
        )

    email = payload.email.lower()

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user = User(
        name = payload.name,
        email = payload.email,
        hashed_password = hash_password(payload.password),
        role = payload.role,
        phone = payload.phone,
        address = payload.address
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(
    payload: UserLogin,
    db: Session = Depends(get_db)
):
    email = payload.email.lower()
    user = db.query(User).filter(User.email == email).first()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token({'sub': str(user.id), 'role': user.role.value})

    return TokenResponse(access_token=token, user=user)

@app.get("/auth/me", response_model=UserOut, tags=["Auth"])
def me(current_user: User = Depends(get_current_user)):
    return current_user

# ------------ RESTAURANTS & MENU (browsing) -----------

@app.get(
    "/restaurants",
    response_model=RestaurantPage,
    tags=["Restaurants"],
    dependencies=[Depends(get_current_user)]
)
def list_restaurants(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Restaurant).filter(Restaurant.is_active == True)

    if search:
        pattern = f'%{search.strip()}%'
        query = query.filter(or_(Restaurant.name.ilike(pattern), Restaurant.cuisine.ilike(pattern)))

    query = query.order_by(Restaurant.id)

    return paginate(query, page, limit)

@app.get(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantOut,
    tags=["Restaurants"],
    dependencies=[Depends(get_current_user)]
)
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db)):
    restaurant = db.query(Restaurant).filter(Restaurant.id==restaurant_id, Restaurant.is_active==True).first()

    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )

    return restaurant

@app.get(
    "/restaurants/{restaurant_id}/menu",
    response_model=MenuItemPage,
    tags=["Restaurants"],
    dependencies=[Depends(get_current_user)]
)
def get_restaurant_menu(
    restaurant_id: int,
    search: Optional[str] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(Restaurant.id==restaurant_id, Restaurant.is_active==True).first()
    
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )

    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price cannot be greater than max_price"
        )

    query = db.query(MenuItem).filter(MenuItem.restaurant_id==restaurant_id)

    if search:
        query = query.filter(MenuItem.name.ilike(f"%{search.strip()}%"))
    if min_price is not None:
        query = query.filter(MenuItem.price >= min_price)
    if max_price is not None:
        query = query.filter(MenuItem.price <= max_price)

    query = query.order_by(MenuItem.id)

    return paginate(query, page, limit)



# --------------- OWNER: RESTAURANT & MENU MANAGEMENT ---------------

def get_owner_restaurant(owner: User, db: Session) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == owner.id).first()
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No restaurant found for this owner"
        )

    return restaurant

def get_owner_menu_item(item_id: int, restaurant: Restaurant, db: Session) -> MenuItem:
    item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.restaurant_id == restaurant.id).first()

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    return item

def ensure_unique_dish_name(
    name: str, restaurant: Restaurant, db: Session, exclude_item_id: Optional[int] = None
):
    query = db.query(MenuItem).filter(
        MenuItem.restaurant_id == restaurant.id,
        func.lower(MenuItem.name) == name.strip().lower(),
    )
    if exclude_item_id is not None:
        query = query.filter(MenuItem.id != exclude_item_id)

    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A dish with this name already exists in your menu",
        )


@app.get(
    "/owner/restaurant",
    response_model=RestaurantOut,
    tags=["Owner"]
)
def owner_restaurant(
    owner: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db)
):
    return get_owner_restaurant(owner, db)

@app.get(
    "/owner/menu",
    response_model=MenuItemPage,
    tags=["Owner"]
)
def owner_menu(
    owner: User = Depends(require_roles(UserRole.OWNER)),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    restaurant = get_owner_restaurant(owner, db)

    query = db.query(MenuItem).filter(MenuItem.restaurant_id == restaurant.id).order_by(MenuItem.id)

    return paginate(query, page, limit)

@app.post(
    "/owner/menu",
    response_model=MenuItemOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Owner"]
)
def owner_add_menu_item(
    payload: MenuItemCreate,
    owner: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db)
):
    restaurant = get_owner_restaurant(owner, db)
    ensure_unique_dish_name(payload.name, restaurant, db)

    item = MenuItem(restaurant_id=restaurant.id, **payload.model_dump())

    db.add(item)
    db.commit()
    db.refresh(item)

    return item

@app.put(
    "/owner/menu/{item_id}",
    response_model=MenuItemOut,
    tags=["Owner"]
)
def owner_update_menu_item(
    item_id: int,
    payload: MenuItemUpdate,
    owner: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db)
):
    restaurant = get_owner_restaurant(owner, db)
    item = get_owner_menu_item(item_id, restaurant, db)

    changes = payload.model_dump(exclude_unset=True)

    for required_field in ("name", "price", "is_available"):
        if required_field in changes and changes[required_field] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{required_field} cannot be null"
            )

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No fields provided to update"
        )

    if "name" in changes:
        ensure_unique_dish_name(changes["name"], restaurant, db, exclude_item_id=item.id)

    for field, value in changes.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)

    return item


@app.patch(
    "/owner/menu/{item_id}/availability",
    response_model=MenuItemOut,
    tags=["Owner"]
)
def owner_set_availability(
    item_id: int,
    payload: AvailabilityUpdate,
    owner: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db)
):
    restaurant = get_owner_restaurant(owner, db)
    item = get_owner_menu_item(item_id, restaurant, db)

    item.is_available = payload.is_available
    
    db.commit()
    db.refresh(item)

    return item

@app.middleware('http')
async def log_requests(request: Request, call_next):
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "%s %s -> unhandled error (%.2f ms)",
            request.method,
            request.url.path,
            duration_ms
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{duration_ms:.2f} ms"

    logger.info(
        "%s %s -> %s (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms
    )
    return response


# ---------------- ORDERS: CUSTOMER ----------------

@app.post(
    "/order",
    response_model=OrderOut,
    tags=["Orders"]
)
def place_order(
    payload: OrderCreate,
    customer: User = Depends(require_roles(UserRole.CUSTOMER)),
    db: Session = Depends(get_db)
):
    # 1. restaurant must exist and be active
    restaurant = db.query(Restaurant).filter(Restaurant.id == payload.restaurant_id, Restaurant.is_active == True).first()

    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # 2. merge duplicate lines (same dish listed twice -> add quantities)
    quantities: dict[int, int] = {}
    for line in payload.items:
        quantities[line.menu_item_id] = quantities.get(line.menu_item_id, 0) + line.quantity

    if any(qty > 20 for qty in quantities.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum quantites per dish is 20"
        )

    dishes = db.query(MenuItem).filter(MenuItem.id.in_(list(quantities.keys()))).all()
    dish_by_id = {dish.id: dish for dish in dishes}

    missing = set(quantities.keys()) - set(dish_by_id.keys())

    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Menu item(s) not found: {sorted(missing)}"
        )

    for dish in dishes:
        if dish.restaurant_id != restaurant.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{dish.name} does not belong to this restaurant"
            )

        if not dish.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{dish.name} is currently unavailable"
            )

    # 4. compute the total on the server, from database prices
    total = Decimal("0.00")

    for dish_id, qty in quantities.items():
        unit_price = Decimal(str(dish_by_id[dish_id].price))
        total += unit_price * qty
    total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    
    # 5. order + order items + ledger entry, saved in ONE transaction

    try:
        order = Order(
            customer_id=customer.id,
            restaurant_id=restaurant.id,
            status=OrderStatus.PLACED,
            total_amount=total,
            delivery_address=payload.delivery_address,
            payment_status=PaymentStatus.mock_paid,
        )
        db.add(order)
        db.flush()  # gives the order an id without committing

        for dish_id, qty in quantities.items():
            dish = dish_by_id[dish_id]
            db.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=dish.id,
                    quantity=qty,
                    unit_price=dish.price,  # price snapshot
                )
            )

        db.add(
            PaymentLedger(
                order_id=order.id,
                entry_type=LedgerEntryType.PAYMENT,
                amount=total,
                status="success",
            )
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    return order


# ---------------- ORDERS: CUSTOMER (list, detail, cancel) ----------------

def apply_order_filters(
        query: sql_query,
        status_filter: Optional[OrderStatus],
        from_date: Optional[date],
        to_date: Optional[date]
):
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date cannot be after to_date"
        )

    if status_filter is not None:
        query = query.filter(Order.status == status_filter)
    if from_date is not None:
        start = datetime.combine(from_date, datetime.min.time())
        query = query.filter(Order.created_at >= start)
    if to_date is not None:
        end = datetime.combine(to_date + timedelta(days=1), datetime.min.time())
        query = query.filter(Order.created_at < end)

    return query

def get_customer_order(
        order_id: int,
        customer: User,
        db: Session
) -> Order:
    order = db.query(Order).filter(Order.id == order_id, Order.customer_id == customer.id).first()

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    return order

@app.get(
    "/orders",
    response_model=OrderPage,
    tags=["Orders"]
)
def list_my_orders(
    status_fileter: Optional[OrderStatus] = Query(None, alias="status"),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    customer: User = Depends(require_roles(UserRole.CUSTOMER)),
    db: Session = Depends(get_db)
):
    query = db.query(Order).filter(Order.customer_id == customer.id)
    query = apply_order_filters(query, status_fileter, from_date, to_date)
    query = query.order_by(Order.created_at.desc(), Order.id.desc())
    return paginate(query, page, limit)

@app.get(
    "/orders/{order_id}",
    response_model=OrderOut,
    tags=["Orders"]
)
def get_my_order(
    order_id: int,
    customer: User = Depends(require_roles(UserRole.CUSTOMER)),
    db: Session = Depends(get_db)
):
    return get_customer_order(order_id, customer, db)

@app.post(
    "/oders/{order_id}/cancel",
    response_model=OrderOut,
    tags=["Orders"]
)
def cancel_my_order(
    order_id: int,
    customer: User = Depends(require_roles(UserRole.CUSTOMER)),
    db: Session = Depends(get_db)
):
    order = get_customer_order(order_id, customer, db)
    change_status(order, OrderStatus.CANCELLED, customer)

    db.commit()
    db.refresh(order)

    return order

# -------------- ORDER: OWNER ----------------

ALLOWED_OWNER_TARGETS = {
    OrderStatus.ACCEPTED,
    OrderStatus.PREPARING,
    OrderStatus.READY
}

def get_owner_order(
        order_id: int,
        restaurant: Restaurant,
        db: Session
) -> Order:
    order = db.query(Order).filter(Order.id == order_id, Order.restaurant_id == restaurant.id).first()

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    return order


@app.get(
    "/owner/orders",
    response_model=OrderPage,
    tags=["Owner"]
)
def owner_list_orders(
    status_filte: Optional[OrderStatus] = Query(None, alias="status"),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    owner: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db)
):
    restaurant = get_owner_restaurant(owner, db)
    query = db.query(Order).filter(Order.restaurant_id == restaurant.id)
    query = apply_order_filters(query, status_filte, from_date, to_date)
    query = query.order_by(Order.created_at.desc(), Order.id.desc())

    return paginate(query, page, limit)

@app.get(
    "/owner/orders/{order_id}",
    response_model=OrderOut,
    tags=["Owner"]
)
def owner_get_order(
    order_id: int,
    owner: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db)
):
    restaurant = get_owner_restaurant(owner, db)
    return get_owner_order(order_id, restaurant, db)

@app.patch(
    "/owner/orders/{order_id}/status",
    response_model=OrderOut,
    tags=["Owner"]
)
def owner_update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    owner: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db)
):
    restaurant = get_owner_restaurant(owner, db)
    order = get_owner_order(order_id, restaurant, db)

    if payload.status not in ALLOWED_OWNER_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owners can only set ACCEPTED, PREPARING or READY here"
        )

    change_status(order, payload.status, owner)
    db.commit()
    db.refresh(order)
    return order

@app.get(
    "/owner/delivery-partners",
    response_model= List[UserBrief],
    tags=["Owner"]
)
def owner_list_delivery_partners(
    owner: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db)
):
    return db.query(User).filter(User.role == UserRole.DELIVERY).order_by(User.name).all()

@app.post(
    "/owner/orders/{order_id}/assign",
    response_model=OrderOut,
    tags=["Owner"]
)
def owner_assign_delivery_partner(
    order_id: int,
    payload: AssignDelivery,
    owner: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db)
):
    restaurant = get_owner_restaurant(owner, db)
    order = get_owner_order(order_id, restaurant, db)

    partner = (
        db.query(User)
        .filter(
            User.id == payload.delivery_partner_id,
            User.role == UserRole.DELIVERY
        ).first()
    )

    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery partner not found"
        )

    change_status(order, OrderStatus.ASSIGNED, owner)
    order.delivery_partner_id = payload.delivery_partner_id

    db.commit()
    db.refresh(order)

    return order



# ---------------- ORDERS: DELIVERY PARTNER ----------------

DELIVERY_ALLOWED_TARGETS = {
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
}

ACTIVE_DELIVERY_STATUSES = [OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY]
HISTORY_STATUSES = [OrderStatus.DELIVERED, OrderStatus.REFUNDED]

def get_delivery_order(
        order_id: int,
        partner: User,
        db: Session
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.delivery_partner_id == partner.id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    return order

@app.get(
    "/delivery/orders",
    response_model=OrderPage    ,
    tags=["Delivery"]
)
def delivery_list_orders(
    status_filter: OrderStatus = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    partner: User = Depends(require_roles(UserRole.DELIVERY)),
    db: Session = Depends(get_db)
):
    query = (
        db.query(Order)
        .filter(Order.delivery_partner_id == partner.id)
    )

    if status_filter is not None:
        query = query.filter(Order.status == status_filter)
    else:
        query = query.filter(Order.status.in_(ACTIVE_DELIVERY_STATUSES))

    query = query.order_by(Order.updated_at.desc(), Order.id.desc())

    return paginate(query, page, limit)

@app.patch(
    "/delivery/orders/{order_id}/status",
    response_model=OrderOut,
    tags=["Delivery"]
)
def delivery_update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    partner: User = Depends(require_roles(UserRole.DELIVERY)),
    db: Session = Depends(get_db)
):
    order = get_delivery_order(order_id, partner, db)

    if payload.status not in DELIVERY_ALLOWED_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delivery partners can only set OUT_FOR_DELIVERY or DELIVERED"
        )

    change_status(order, payload.status, partner)
    db.commit()
    db.refresh(order)

    return order

@app.get(
    "/delivery/history",
    response_model=OrderPage,
    tags=["Delivery"]
)
def delivery_history(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    partner: User = Depends(require_roles(UserRole.DELIVERY)),
    db: Session = Depends(get_db)
):
    query = (
        db.query(Order)
        .filter(
            Order.delivery_partner_id == partner.id,
            Order.status.in_(HISTORY_STATUSES)
        )
        .order_by(Order.updated_at.desc(), Order.id.desc())
    )

    return paginate(query, page, limit)



