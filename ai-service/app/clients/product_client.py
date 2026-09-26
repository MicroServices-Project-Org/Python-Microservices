import httpx
from app.config import settings


TIMEOUT = httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=5.0)
PAGE_SIZE = 100  # Product Service's max page_size
MAX_PAGES = 10   # Safety cap: at most 1000 products per fetch


async def get_all_products() -> list[dict]:
    """
    Fetch all products from the Product Service.
    /api/products is paginated (default page_size=10), so walk pages until `total` is reached.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            products: list[dict] = []
            for page in range(1, MAX_PAGES + 1):
                resp = await client.get(
                    f"{settings.PRODUCT_SERVICE_URL}/api/products",
                    params={"page": page, "page_size": PAGE_SIZE},
                )
                resp.raise_for_status()
                data = resp.json()

                # Handle both list and dict response formats
                if isinstance(data, list):
                    return data
                if not isinstance(data, dict):
                    return products

                # Try common wrapper keys
                batch = next((data[k] for k in ["products", "data", "items", "results"] if k in data), None)
                if batch is None:
                    # If it's a single product dict, wrap in list
                    return [data]

                products.extend(batch)
                total = data.get("total")
                if not batch or not isinstance(total, int) or len(products) >= total:
                    break
            return products
    except Exception as e:
        print(f"⚠️ Failed to fetch products: {e}")
        return []


async def search_products(query: str) -> list[dict]:
    """Search products from the Product Service."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{settings.PRODUCT_SERVICE_URL}/api/products/search",
                params={"q": query},
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                for key in ["products", "data", "items", "results"]:
                    if key in data:
                        return data[key]
                return [data]
            return []
    except Exception as e:
        print(f"⚠️ Failed to search products: {e}")
        return []


def format_products_for_context(products: list[dict]) -> str:
    """
    Formats product list into a text block for LLM context.
    Keeps it concise to stay within token limits.
    """
    if not products:
        return "No products available in the catalog."

    # Ensure products is a list
    if not isinstance(products, list):
        products = [products]

    lines = []
    for p in products[:50]:  # Limit to 50 products for token efficiency
        name = p.get("name", p.get("product_name", "Unknown"))
        price = p.get("price", "N/A")
        category = p.get("category", "N/A")
        tags = ", ".join(p.get("tags", []))
        desc = p.get("description", "")
        line = f"- {name} | ${price} | Category: {category}"
        if tags:
            line += f" | Tags: {tags}"
        if desc:
            line += f" | {desc}"
        lines.append(line)

    return "\n".join(lines)