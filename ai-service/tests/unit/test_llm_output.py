from app.services.llm_output import parse_llm_json, build_catalog_index, match_products


CATALOG = [
    {"id": "p1", "name": "iPhone 15 Pro", "price": 999.99, "category": "Electronics", "image_url": None, "stock_quantity": 5},
    {"id": "p2", "name": "AirPods  Pro", "price": 249.99, "category": "Electronics", "image_url": "http://img/2"},
]


# ─── parse_llm_json ──────────────────────────────────────────────────────────

def test_parse_plain_json():
    assert parse_llm_json('{"a": 1}') == {"a": 1}

def test_parse_markdown_fenced_json():
    assert parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}

def test_parse_json_surrounded_by_prose():
    assert parse_llm_json('Here you go:\n{"a": {"b": 2}}\nHope that helps!') == {"a": {"b": 2}}

def test_parse_non_json_returns_none():
    assert parse_llm_json("Sorry, the AI service is temporarily busy.") is None

def test_parse_empty_returns_none():
    assert parse_llm_json("") is None

def test_parse_json_array_returns_none():
    assert parse_llm_json("[1, 2]") is None

def test_parse_broken_json_returns_none():
    assert parse_llm_json('{"a": 1,,}') is None


# ─── match_products ──────────────────────────────────────────────────────────

def test_match_uses_catalog_fields_only():
    index = build_catalog_index(CATALOG)
    result = match_products([{"name": "iPhone 15 Pro", "price": 1, "id": "fake", "reason": "r"}], index, "reason")
    assert result == [{"id": "p1", "name": "iPhone 15 Pro", "price": 999.99,
                       "category": "Electronics", "image_url": None, "reason": "r"}]

def test_match_is_case_and_whitespace_insensitive():
    index = build_catalog_index(CATALOG)
    result = match_products([{"name": "  airpods pro "}], index, "reason")
    assert [r["id"] for r in result] == ["p2"]
    assert result[0]["reason"] == ""

def test_match_drops_unknown_and_malformed_items():
    index = build_catalog_index(CATALOG)
    items = [{"name": "Made Up"}, "iPhone 15 Pro", {"reason": "no name"}, {"name": 5}, {"name": "iPhone 15 Pro"}]
    assert [r["id"] for r in match_products(items, index, "reason")] == ["p1"]

def test_match_deduplicates_keeping_llm_order():
    index = build_catalog_index(CATALOG)
    items = [{"name": "AirPods Pro"}, {"name": "iPhone 15 Pro"}, {"name": "airpods pro"}]
    assert [r["id"] for r in match_products(items, index, "reason")] == ["p2", "p1"]

def test_match_non_list_returns_empty():
    assert match_products({"name": "iPhone 15 Pro"}, build_catalog_index(CATALOG), "reason") == []

def test_catalog_index_first_duplicate_wins():
    index = build_catalog_index([{"id": "a", "name": "X"}, {"id": "b", "name": "x"}, {"id": "c"}])
    assert list(index) == ["x"]
    assert index["x"]["id"] == "a"
