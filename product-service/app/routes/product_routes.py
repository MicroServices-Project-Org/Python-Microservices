from fastapi import APIRouter, Query, status
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductListResponse
from app.services import product_service

router = APIRouter()

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate):
    return await product_service.create_product(payload)

@router.get("", response_model=ProductListResponse)
async def get_all_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100)
):
    return await product_service.get_all_products(page, page_size)

@router.get("/search", response_model=list[ProductResponse])
async def search_products(q: str = Query(..., min_length=1)):
    return await product_service.search_products(q)

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    return await product_service.get_product(product_id)

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, payload: ProductUpdate):
    return await product_service.update_product(product_id, payload)

@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_product(product_id: str):
    return await product_service.delete_product(product_id)