from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.inventory import Inventory
from app.schemas.inventory import InventoryCreate, InventoryUpdate

async def create_inventory(data: InventoryCreate, db: AsyncSession) -> Inventory:
    # Check if product_id already exists
    existing = await db.execute(
        select(Inventory).where(Inventory.product_id == data.product_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Inventory for product {data.product_id} already exists"
        )
    item = Inventory(**data.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item

async def get_inventory(product_id: str, db: AsyncSession) -> Inventory:
    result = await db.execute(
        select(Inventory).where(Inventory.product_id == product_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory for product {product_id} not found"
        )
    return item

async def get_all_inventory(db: AsyncSession) -> list[Inventory]:
    result = await db.execute(select(Inventory))
    return list(result.scalars().all())

async def check_stock(product_id: str, required_qty: int, db: AsyncSession) -> bool:
    """Used by Order Service to verify stock before placing an order."""
    item = await get_inventory(product_id, db)
    return item.available_qty >= required_qty

async def reduce_stock(product_id: str, quantity: int, db: AsyncSession) -> Inventory:
    """Reduce available stock when an order is placed."""
    item = await get_inventory(product_id, db)
    if item.available_qty < quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock. Available: {item.available_qty}, Requested: {quantity}"
        )
    item.quantity -= quantity
    await db.flush()
    await db.refresh(item)
    return item

async def restock(product_id: str, quantity: int, db: AsyncSession) -> Inventory:
    """Add stock to an existing inventory item."""
    item = await get_inventory(product_id, db)
    item.quantity += quantity
    await db.flush()
    await db.refresh(item)
    return item

async def update_inventory(product_id: str, data: InventoryUpdate, db: AsyncSession) -> Inventory:
    item = await get_inventory(product_id, db)
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    for key, val in updates.items():
        setattr(item, key, val)
    await db.flush()
    await db.refresh(item)
    return item

async def delete_inventory(product_id: str, db: AsyncSession) -> dict:
    item = await get_inventory(product_id, db)
    await db.delete(item)
    return {"message": f"Inventory for product {product_id} deleted successfully"}