from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List


class MenuItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None
    price: float = Field(gt=0)
    category: Optional[str] = None
    is_available: bool = True

    model_config=ConfigDict(str_strip_whitespace=True)

class MenuItemOut(BaseModel):
    id: int
    restaurant_id: int
    name: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None
    is_available: bool

    model_config=ConfigDict(from_attributes=True)

class MenuItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    category: Optional[str] = Field(default=None, max_length=100)
    is_available: Optional[bool] = None

    model_config=ConfigDict(str_strip_whitespace=True)

class AvailabilityUpdate(BaseModel):
    is_available: bool

class MenuItemPage(BaseModel):
    items: List[MenuItemOut]
    total: int
    page: int
    limit: int
    pages: int