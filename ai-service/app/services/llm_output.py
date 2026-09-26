"""
Parse and validate structured LLM output against the real catalog.

The LLM is told to answer in JSON and to pick only catalog products, but it can
wrap JSON in markdown fences, add prose, or invent products. Everything returned
to callers goes through here, so product data (id, price, ...) always comes from
the catalog, never from the LLM.
"""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Product fields returned to callers, taken from the catalog entry
PRODUCT_FIELDS = ("id", "name", "price", "category", "image_url")


def parse_llm_json(text: str) -> Optional[dict]:
    """Extract a JSON object from an LLM reply. Returns None if there isn't one."""
    if not text:
        return None
    clean = text.strip()
    # Strip markdown code fences (```json ... ```)
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else ""
        clean = clean.rsplit("```", 1)[0]
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} in case the model added prose around it
        start, end = clean.find("{"), clean.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(clean[start:end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().casefold()


def build_catalog_index(products: list[dict]) -> dict[str, dict]:
    """Map normalized product name → catalog product. First product wins on duplicate names."""
    index: dict[str, dict] = {}
    for p in products:
        name = p.get("name")
        if isinstance(name, str) and name.strip():
            index.setdefault(_normalize(name), p)
    return index


def match_products(items: list, index: dict[str, dict], reason_key: str) -> list[dict]:
    """
    Keep only LLM-picked items that name a real catalog product.
    Returns catalog fields plus the LLM's reason, deduplicated, in the LLM's order.
    """
    matched: list[dict] = []
    seen: set[str] = set()
    if not isinstance(items, list):
        return matched

    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        key = _normalize(item["name"])
        product = index.get(key)
        if product is None:
            logger.warning("Dropping LLM-suggested product not in catalog: %r", item["name"])
            continue
        if key in seen:
            continue
        seen.add(key)
        entry = {field: product.get(field) for field in PRODUCT_FIELDS}
        reason = item.get(reason_key)
        entry[reason_key] = reason if isinstance(reason, str) else ""
        matched.append(entry)
    return matched
