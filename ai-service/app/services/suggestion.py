from app.llm.factory import llm_client
from app.clients.product_client import get_all_products, format_products_for_context


SYSTEM_PROMPT = """You are a smart product search engine for our e-commerce store.
A customer will describe what they're looking for in natural language.
Your job is to find matching products from our catalog.

Respond in this exact JSON format and nothing else:
{{
  "matches": [
    {{"name": "Product Name", "price": 99.99, "match_reason": "Why this matches the query"}}
  ],
  "search_tags": ["tag1", "tag2"],
  "search_category": "Best matching category"
}}

Only return products that actually exist in our catalog.
If nothing matches well, return an empty matches list with suggested search_tags.

Here is our current product catalog:
{catalog}
"""


async def suggest_products(query: str) -> str:
    """
    Natural language product search.
    Translates a query like "something warm for winter under $50"
    into matching products from the real catalog.
    """
    products = await get_all_products()
    catalog = format_products_for_context(products)
    system = SYSTEM_PROMPT.format(catalog=catalog)

    prompt = f"Customer is looking for: {query}"

    response = await llm_client.generate(prompt=prompt, system_prompt=system)
    return response