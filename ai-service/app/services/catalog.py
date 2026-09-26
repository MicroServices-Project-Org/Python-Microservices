from app.cache import redis_cache
from app.clients.product_client import get_all_products
from app.config import settings


async def get_catalog() -> list[dict]:
    """
    Product catalog for LLM context, cache-aside (CACHE_CATALOG_TTL, invalidated on product-updated).
    An empty result (e.g. Product Service down) is not cached, so recovery is immediate.
    """
    key = await redis_cache.make_key("catalog")
    cached = await redis_cache.get_json(key, kind="catalog")
    if isinstance(cached, list):
        return cached

    products = await get_all_products()
    if products:
        await redis_cache.set_json(key, products, settings.CACHE_CATALOG_TTL)
    return products
