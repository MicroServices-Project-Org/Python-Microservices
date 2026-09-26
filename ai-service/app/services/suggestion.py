import logging

from fastapi import HTTPException

from app.cache import redis_cache
from app.config import settings
from app.llm.factory import llm_client
from app.clients.product_client import format_products_for_context
from app.services.catalog import get_catalog
from app.services.llm_output import parse_llm_json, build_catalog_index, match_products, to_picks, hydrate_picks

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a smart product search engine for our e-commerce store.
A customer will describe what they're looking for in natural language.
Your job is to find matching products from our catalog.

Respond in this exact JSON format and nothing else:
{{
  "matches": [
    {{"name": "Product Name", "match_reason": "Why this matches the query"}}
  ],
  "search_tags": ["tag1", "tag2"],
  "search_category": "Best matching category"
}}

Only return products that actually exist in our catalog, using each product's exact name as listed.
If nothing matches well, return an empty matches list with suggested search_tags.

Here is our current product catalog:
{catalog}
"""


async def suggest_products(query: str) -> dict:
    """
    Natural language product search.
    Translates a query like "something warm for winter under $50"
    into matching products from the real catalog.
    Returns {"matches": [...], "search_tags": [...], "search_category": str | None}.
    Prices come from the catalog, not the LLM. Raises 502 if the LLM reply isn't valid JSON.
    The LLM's picks are cached per normalized query; product details come from the current catalog.
    """
    products = await get_catalog()
    if not products:
        return {"matches": [], "search_tags": [], "search_category": None}

    key = await redis_cache.make_key("suggest", query)
    cached = await redis_cache.get_json(key, kind="suggest")
    if isinstance(cached, dict):
        return {
            "matches": hydrate_picks(cached.get("picks"), products, "match_reason"),
            "search_tags": cached.get("search_tags") or [],
            "search_category": cached.get("search_category"),
        }

    catalog = format_products_for_context(products)
    system = SYSTEM_PROMPT.format(catalog=catalog)

    prompt = f"Customer is looking for: {query}"

    response = await llm_client.generate(prompt=prompt, system_prompt=system)
    data = parse_llm_json(response)
    if data is None:
        logger.error("Unparseable LLM suggestion reply: %.200r", response)
        raise HTTPException(status_code=502, detail="AI service returned an invalid response. Please try again.")

    tags = data.get("search_tags")
    search_category = data.get("search_category")
    result = {
        "matches": match_products(data.get("matches", []), build_catalog_index(products), reason_key="match_reason"),
        "search_tags": [t for t in tags if isinstance(t, str)] if isinstance(tags, list) else [],
        "search_category": search_category if isinstance(search_category, str) and search_category else None,
    }
    if result["matches"]:  # Don't pin an empty answer for 6h
        await redis_cache.set_json(key, {
            "picks": to_picks(result["matches"], "match_reason"),
            "search_tags": result["search_tags"],
            "search_category": result["search_category"],
        }, settings.CACHE_LLM_TTL)
    return result
