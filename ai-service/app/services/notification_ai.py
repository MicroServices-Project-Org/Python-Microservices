from app.llm.factory import llm_client
from app.clients.product_client import get_all_products, format_products_for_context


SYSTEM_PROMPT = """You are an email copywriter for our e-commerce store.
Given a customer's order details, write a short, personalized follow-up email
that thanks them for their purchase and suggests 2-3 related products they might like.

Respond in this exact JSON format and nothing else:
{{
  "subject": "Email subject line",
  "body_html": "<html>...</html>"
}}

The body_html should be valid HTML with inline styles. Keep it concise, warm, and
professional. Include the customer's name and reference their purchased items.
Suggest only products that exist in our catalog.

Here is our current product catalog:
{catalog}
"""


async def personalize_notification(event: dict) -> dict:
    """
    Generate a personalized follow-up email based on order details.
    Returns dict with 'subject' and 'body_html' keys.
    """
    products = await get_all_products()
    catalog = format_products_for_context(products)
    system = SYSTEM_PROMPT.format(catalog=catalog)

    items_text = ", ".join(
        f"{item['product_name']} (x{item['quantity']})"
        for item in event.get("items", [])
    )

    prompt = (
        f"Customer: {event.get('customer_name', 'Customer')}\n"
        f"Order: {event.get('order_number', 'N/A')}\n"
        f"Items purchased: {items_text}\n"
        f"Total: ${event.get('total_amount', 0):.2f}\n\n"
        f"Write a personalized follow-up email for this customer."
    )

    response = await llm_client.generate(prompt=prompt, system_prompt=system)

    # Try to parse JSON from LLM response
    try:
        import json
        # Clean response — strip markdown code fences if present
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]  # Remove first line
            clean = clean.rsplit("```", 1)[0]  # Remove last fence
        result = json.loads(clean)
        return {
            "subject": result.get("subject", f"Thanks for your order {event.get('order_number', '')}"),
            "body_html": result.get("body_html", "<p>Thank you for your order!</p>"),
        }
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ Failed to parse AI notification response: {e}")
        return {
            "subject": f"Thanks for your order {event.get('order_number', '')}",
            "body_html": f"<p>Hi {event.get('customer_name', 'there')}, thank you for your order!</p>",
        }