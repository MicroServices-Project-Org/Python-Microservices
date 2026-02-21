from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from app.database import get_db
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductListResponse

def _serialize(doc: dict) -> ProductResponse:
    """Convert MongoDB document to ProductResponse."""
    doc["id"] = str(doc.pop("_id"))
    return ProductResponse(**doc)

async def create_product(data: ProductCreate) -> ProductResponse:
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        **data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
    result = await db.products.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)

async def get_product(product_id: str) -> ProductResponse:
    db = get_db()
    try:
        oid = ObjectId(product_id)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")

    doc = await db.products.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found")
    return _serialize(doc)

async def get_all_products(page: int = 1, page_size: int = 10) -> ProductListResponse:
    db = get_db()
    skip = (page - 1) * page_size
    total = await db.products.count_documents({})
    cursor = db.products.find().skip(skip).limit(page_size)
    products = [_serialize(doc) async for doc in cursor]
    return ProductListResponse(products=products, total=total, page=page, page_size=page_size)

async def search_products(q: str) -> List[ProductResponse]:
    db = get_db()
    query = {
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
            {"tags": {"$in": [q.lower()]}}
        ]
    }
    cursor = db.products.find(query)
    return [_serialize(doc) async for doc in cursor]

async def update_product(product_id: str, data: ProductUpdate) -> ProductResponse:
    db = get_db()
    try:
        oid = ObjectId(product_id)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")

    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    if "price" in updates:
        updates["price"] = float(updates["price"])
    updates["updated_at"] = datetime.now(timezone.utc)

    result = await db.products.find_one_and_update(
        {"_id": oid},
        {"$set": updates},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found")
    return _serialize(result)

async def delete_product(product_id: str) -> dict:
    db = get_db()
    try:
        oid = ObjectId(product_id)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")

    result = await db.products.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found")
    return {"message": f"Product {product_id} deleted successfully"}