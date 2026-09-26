import json
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import HTTPException, status
from app.models.inventory import Inventory
from app.models.processed_event import ProcessedEvent
from app.schemas.inventory import InventoryCreate, InventoryUpdate

logger = logging.getLogger(__name__)

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


def parse_cancelled_order(raw: bytes) -> tuple[str, list[tuple[str, int]]]:
    """
    Read an order-cancelled event into (order_number, [(product_id, quantity), ...]).
    Raises ValueError if it isn't a usable event, so the consumer can skip it.
    """
    event = json.loads(raw)
    order_number = event.get("order_number") if isinstance(event, dict) else None
    items = event.get("items") if isinstance(event, dict) else None
    if not isinstance(order_number, str) or not order_number or not isinstance(items, list):
        raise ValueError("missing order_number or items")
    parsed = []
    for item in items:
        product_id = item.get("product_id") if isinstance(item, dict) else None
        quantity = item.get("quantity") if isinstance(item, dict) else None
        if not isinstance(product_id, str) or type(quantity) is not int or quantity <= 0:
            raise ValueError(f"bad item: {item!r}")
        parsed.append((product_id, quantity))
    return order_number, parsed


async def restock_cancelled_order(order_number: str, items: list[tuple[str, int]], db: AsyncSession) -> Optional[int]:
    """
    Give back the stock of a cancelled order. Idempotent: the order is recorded in
    processed_events in the same transaction as the stock updates, so a redelivered
    event restocks nothing. Returns how many items were restocked, or None if this
    order was already processed.
    """
    claimed = await db.execute(
        pg_insert(ProcessedEvent)
        .values(event_key=f"{order_number}_ORDER_CANCELLED")
        .on_conflict_do_nothing()
        .returning(ProcessedEvent.event_key)
    )
    if claimed.scalar_one_or_none() is None:
        return None

    restocked = 0
    for product_id, quantity in items:
        # Single UPDATE (not read-modify-write) so a concurrent reduce_stock can't be overwritten
        result = await db.execute(
            update(Inventory)
            .where(Inventory.product_id == product_id)
            .values(quantity=Inventory.quantity + quantity)
        )
        if result.rowcount == 0:
            logger.warning("Order %s cancelled, but product %s has no inventory row; not restocked",
                           order_number, product_id)
        else:
            restocked += 1
    return restocked
