from fastapi import FastAPI, status, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.db.database import engine, Base, get_db
from app.schemas.auth import UserOut, UserRegister, TokenResponse, UserLogin
from app.models.enums import UserRole
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.menu_item import MenuItem
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user, require_roles
from app.core.pagination import paginate
from app.schemas.restaurant import RestaurantPage, RestaurantOut
from app.schemas.menu import MenuItemPage, MenuItemCreate, MenuItemOut, MenuItemUpdate, AvailabilityUpdate

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
