from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.enums import UserRole
from typing import Optional


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    role: UserRole = UserRole.CUSTOMER
    phone: str = Field(min_length=13, max_length=13)
    address: Optional[str] = Field(default=None, max_length=255)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    phone: str
    address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
