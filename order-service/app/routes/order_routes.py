from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate
from app.services import order_service

router = APIRouter()

@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)):
    return await order_service.create_order(payload, db)

@router.get("", response_model=list[OrderResponse])
async def get_all_orders(db: AsyncSession = Depends(get_db)):
    return await order_service.get_all_orders(db)

@router.get("/user/{email}", response_model=list[OrderResponse])
async def get_orders_by_email(email: str, db: AsyncSession = Depends(get_db)):
    return await order_service.get_orders_by_email(email, db)

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    return await order_service.get_order(order_id, db)

@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db)
):
    return await order_service.update_order_status(order_id, payload, db)

@router.patch("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(order_id: str, db: AsyncSession = Depends(get_db)):
    return await order_service.cancel_order(order_id, db)