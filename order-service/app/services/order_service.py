import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models.order import Order, OrderItem, OrderStatus
from app.schemas.order import OrderCreate, OrderStatusUpdate
from app.clients import inventory_client
from app.kafka.producer import publish_order_placed

def _generate_order_number() -> str:
    now = datetime.now(timezone.utc)
    return f"ORD-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

async def create_order(data: OrderCreate, db: AsyncSession) -> Order:
    # Step 1 — Check stock for all items
    for item in data.items:
        in_stock = await inventory_client.check_stock(item.product_id, item.quantity)
        if not in_stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for product: {item.product_name}"
            )

    # Step 2 — Calculate total
    total = sum(i.quantity * i.unit_price for i in data.items)

    # Step 3 — Save order
    order = Order(
        order_number=_generate_order_number(),
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        total_amount=round(total, 2),
        status=OrderStatus.CONFIRMED,
    )
    db.add(order)
    await db.flush()

    # Step 4 — Save order items
    for item in data.items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=round(item.quantity * item.unit_price, 2),
        )
        db.add(order_item)

    await db.flush()
    await db.refresh(order, ["items"])

    # Step 5 — Reduce stock in inventory
    for item in data.items:
        await inventory_client.reduce_stock(item.product_id, item.quantity)

    # Step 6 — Publish Kafka event (non-blocking)
    await publish_order_placed({
        "event_type": "ORDER_PLACED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "total_amount": order.total_amount,
        "items": [
            {
                "product_id": i.product_id,
                "product_name": i.product_name,
                "quantity": i.quantity,
                "price": i.unit_price
            } for i in order.items
        ]
    })

    return order

async def get_order(order_id: str, db: AsyncSession) -> Order:
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == oid)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return order

async def get_orders_by_email(email: str, db: AsyncSession) -> list[Order]:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.customer_email == email)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())

async def get_all_orders(db: AsyncSession) -> list[Order]:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())

async def update_order_status(order_id: str, data: OrderStatusUpdate, db: AsyncSession) -> Order:
    order = await get_order(order_id, db)
    order.status = data.status
    await db.flush()
    await db.refresh(order, ["items"])
    return order

async def cancel_order(order_id: str, db: AsyncSession) -> Order:
    order = await get_order(order_id, db)
    if order.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status {order.status}"
        )
    order.status = OrderStatus.CANCELLED
    await db.flush()
    await db.refresh(order, ["items"])
    return order