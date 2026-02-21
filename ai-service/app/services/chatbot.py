from app.llm.factory import llm_client
from app.clients.product_client import get_all_products, format_products_for_context


SYSTEM_PROMPT = """You are a helpful shopping assistant for our e-commerce store.
You help customers find products, answer questions about items, compare products,
and make purchase suggestions based on their needs and budget.

Be friendly, concise, and helpful. If you don't know something specific about a product,
say so rather than making it up. Always reference actual products from our catalog when possible.

Here is our current product catalog:
{catalog}
"""


async def chat(message: str, history: list[dict] = None) -> str:
    """
    Shopping assistant chatbot.
    Fetches real product data and uses it as context for the LLM.
    """
    products = await get_all_products()
    catalog = format_products_for_context(products)
    system = SYSTEM_PROMPT.format(catalog=catalog)

    # Build conversation context from history
    conversation = ""
    if history:
        for msg in history[-10:]:  # Keep last 10 messages for context
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conversation += f"{role}: {content}\n"

    conversation += f"user: {message}"

    response = await llm_client.generate(prompt=conversation, system_prompt=system)
    return response