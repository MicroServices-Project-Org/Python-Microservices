import logging

from fastapi import HTTPException

from app.cache import redis_cache
from app.config import settings
from app.llm.factory import llm_client
from app.clients.product_client import format_products_for_context
from app.services.catalog import get_catalog
from app.services.llm_output import parse_llm_json, build_catalog_index, match_products, to_picks, hydrate_picks, exclude_named

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a product recommendation engine for our e-commerce store.
Given a product name and/or category, suggest 5 related products from our catalog
that a customer might also be interested in.

Respond in this exact JSON format and nothing else:
{{
  "recommendations": [
    {{"name": "Product Name", "reason": "Brief reason why this is recommended"}}
  ]
}}

Only recommend products that exist in our catalog, and use each product's exact name
as listed. If the catalog has fewer than 5 relevant products, recommend as many as you can.

Here is our current product catalog:
{catalog}
"""


async def get_recommendations(product_name: str = "", category: str = "") -> list[dict]:
    """
    Generate product recommendations based on a product name and/or category.
    Returns catalog products the LLM picked (id, name, price, category, image_url, reason).
    Products the LLM invented, and the queried product itself, are dropped. Raises 502 if the LLM reply isn't valid JSON.
    The LLM's picks (ids + reasons) are cached; product details always come from the current catalog.
    """
    products = await get_catalog()
    if not products:
        return []  # Nothing to recommend from; don't spend an LLM call

    key = await redis_cache.make_key("rec", product_name, category)
    cached = await redis_cache.get_json(key, kind="rec")
    if cached is not None:
        # Filtered here too: entries cached before this filter existed can still hold the product
        return exclude_named(hydrate_picks(cached, products, "reason"), product_name)

    catalog = format_products_for_context(products)
    system = SYSTEM_PROMPT.format(catalog=catalog)

    prompt = "Recommend 5 products"
    if product_name:
        prompt += f" similar to or complementary to '{product_name}'"
    if category:
        prompt += f" in or related to the '{category}' category"
    prompt += " from our catalog."
    if product_name:
        prompt += f" Do not recommend '{product_name}' itself."

    response = await llm_client.generate(prompt=prompt, system_prompt=system)
    data = parse_llm_json(response)
    if data is None:
        logger.error("Unparseable LLM recommendation reply: %.1000r", response)
        raise HTTPException(status_code=502, detail="AI service returned an invalid response. Please try again.")

    matched = match_products(data.get("recommendations", []), build_catalog_index(products), reason_key="reason")
    matched = exclude_named(matched, product_name)  # The prompt asks for this, but models don't always comply
    if matched:  # Don't pin an empty answer for 6h
        await redis_cache.set_json(key, to_picks(matched, "reason"), settings.CACHE_LLM_TTL)
    return matched
