from app.llm.factory import llm_client
from app.clients.product_client import get_all_products, format_products_for_context


SYSTEM_PROMPT = """You are a product recommendation engine for our e-commerce store.
Given a product name and/or category, suggest 5 related products from our catalog
that a customer might also be interested in.

Respond in this exact JSON format and nothing else:
{{
  "recommendations": [
    {{"name": "Product Name", "reason": "Brief reason why this is recommended"}},
  ]
}}

Only recommend products that exist in our catalog. If the catalog has fewer than 5
relevant products, recommend as many as you can.

Here is our current product catalog:
{catalog}
"""


async def get_recommendations(product_name: str = "", category: str = "") -> str:
    """
    Generate product recommendations based on a product name and/or category.
    Returns LLM response with recommended products from the real catalog.
    """
    products = await get_all_products()
    catalog = format_products_for_context(products)
    system = SYSTEM_PROMPT.format(catalog=catalog)

    prompt = "Recommend 5 products"
    if product_name:
        prompt += f" similar to or complementary to '{product_name}'"
    if category:
        prompt += f" in or related to the '{category}' category"
    prompt += " from our catalog."

    response = await llm_client.generate(prompt=prompt, system_prompt=system)
    return response