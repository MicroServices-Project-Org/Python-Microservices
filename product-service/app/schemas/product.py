from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float = Field(..., gt=0)
    category: str
    tags: List[str] = []
    image_url: Optional[str] = None
    stock_quantity: int = Field(..., ge=0)

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None
    stock_quantity: Optional[int] = Field(None, ge=0)

class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    price: float
    category: str
    tags: List[str]
    image_url: Optional[str]
    stock_quantity: int
    created_at: datetime
    updated_at: datetime

class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    total: int
    page: int
    page_size: int