from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class InventoryCreate(BaseModel):
    product_id: str
    product_name: str
    quantity: int = Field(..., ge=0)

class InventoryUpdate(BaseModel):
    product_name: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)

class StockReduceRequest(BaseModel):
    quantity: int = Field(..., gt=0, description="Quantity to reduce from stock")

class StockRestockRequest(BaseModel):
    quantity: int = Field(..., gt=0, description="Quantity to add to stock")

class InventoryResponse(BaseModel):
    id: UUID
    product_id: str
    product_name: str
    quantity: int
    reserved_qty: int
    available_qty: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True