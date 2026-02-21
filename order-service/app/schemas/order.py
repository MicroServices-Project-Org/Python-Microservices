from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.order import OrderStatus

class OrderItemCreate(BaseModel):
    product_id: str
    product_name: str
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)

class OrderCreate(BaseModel):
    customer_name: str
    customer_email: str
    items: list[OrderItemCreate] = Field(..., min_length=1)

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

class OrderItemResponse(BaseModel):
    id: UUID
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float

    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    customer_name: str
    customer_email: str
    total_amount: float
    status: OrderStatus
    items: list[OrderItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)