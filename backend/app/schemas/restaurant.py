from pydantic import BaseModel, ConfigDict
from typing import Optional, List


class RestaurantOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    cuisine: Optional[str] = None
    address: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class RestaurantPage(BaseModel):
    items: List[RestaurantOut]
    total: int
    page: int
    limit: int
    pages: int