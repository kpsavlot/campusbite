from fastapi import FastAPI, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session

from app.db.database import engine, Base, get_db
from app.schemas.auth import UserOut, UserRegister, TokenResponse, UserLogin
from app.models.enums import UserRole
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.core.deps import get_current_user

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
