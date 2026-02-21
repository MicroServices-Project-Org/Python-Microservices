from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.inventory import (
    InventoryCreate, InventoryUpdate, InventoryResponse,
    StockReduceRequest, StockRestockRequest
)
from app.services import inventory_service

router = APIRouter()

@router.post("", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory(payload: InventoryCreate, db: AsyncSession = Depends(get_db)):
    return await inventory_service.create_inventory(payload, db)

@router.get("", response_model=list[InventoryResponse])
async def get_all_inventory(db: AsyncSession = Depends(get_db)):
    return await inventory_service.get_all_inventory(db)

@router.get("/{product_id}", response_model=InventoryResponse)
async def get_inventory(product_id: str, db: AsyncSession = Depends(get_db)):
    return await inventory_service.get_inventory(product_id, db)

@router.get("/{product_id}/check")
async def check_stock(
    product_id: str,
    quantity: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db)
):
    """Used by Order Service to verify stock availability."""
    in_stock = await inventory_service.check_stock(product_id, quantity, db)
    return {"product_id": product_id, "requested": quantity, "in_stock": in_stock}

@router.patch("/{product_id}/reduce", response_model=InventoryResponse)
async def reduce_stock(
    product_id: str,
    payload: StockReduceRequest,
    db: AsyncSession = Depends(get_db)
):
    return await inventory_service.reduce_stock(product_id, payload.quantity, db)

@router.patch("/{product_id}/restock", response_model=InventoryResponse)
async def restock(
    product_id: str,
    payload: StockRestockRequest,
    db: AsyncSession = Depends(get_db)
):
    return await inventory_service.restock(product_id, payload.quantity, db)

@router.put("/{product_id}", response_model=InventoryResponse)
async def update_inventory(
    product_id: str,
    payload: InventoryUpdate,
    db: AsyncSession = Depends(get_db)
):
    return await inventory_service.update_inventory(product_id, payload, db)

@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_inventory(product_id: str, db: AsyncSession = Depends(get_db)):
    return await inventory_service.delete_inventory(product_id, db)