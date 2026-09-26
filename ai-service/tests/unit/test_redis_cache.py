import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import redis.asyncio as redis

from app.cache import redis_cache


class FakeRedis:
    """Minimal in-memory stand-in for the redis.asyncio calls the cache uses."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.ttls[key] = ex
        return True

    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])


class BrokenRedis:
    async def get(self, key):
        raise redis.ConnectionError("Connection refused")

    async def set(self, key, value, ex=None):
        raise redis.ConnectionError("Connection refused")

    async def incr(self, key):
        raise redis.ConnectionError("Connection refused")


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(redis_cache, "_get_redis", lambda: fake)
    return fake


MOCK_PRODUCTS = [
    {"id": "p1", "name": "iPhone 15 Pro", "price": 999.99, "category": "Electronics", "image_url": None},
    {"id": "p2", "name": "AirPods Pro", "price": 249.99, "category": "Electronics", "image_url": None},
]


# ─── redis_cache primitives ─────────────────────────────────────────────────

async def test_set_then_get_roundtrip(fake_redis):
    key = await redis_cache.make_key("rec", "iPhone", "")
    await redis_cache.set_json(key, [{"id": "p1"}], ttl=60)
    assert await redis_cache.get_json(key, kind="rec") == [{"id": "p1"}]
    assert fake_redis.ttls[key] == 60

async def test_keys_are_normalized(fake_redis):
    a = await redis_cache.make_key("suggest", "  Running  SHOES ")
    b = await redis_cache.make_key("suggest", "running shoes")
    assert a == b

async def test_keys_differ_by_kind_and_parts(fake_redis):
    keys = {
        await redis_cache.make_key("rec", "iPhone", ""),
        await redis_cache.make_key("rec", "", "iPhone"),
        await redis_cache.make_key("suggest", "iPhone"),
    }
    assert len(keys) == 3

async def test_invalidate_changes_every_key(fake_redis):
    before = await redis_cache.make_key("catalog")
    await redis_cache.set_json(before, ["x"], ttl=60)
    await redis_cache.invalidate()
    after = await redis_cache.make_key("catalog")
    assert before != after
    assert await redis_cache.get_json(after, kind="catalog") is None

async def test_missing_key_is_a_miss(fake_redis):
    assert await redis_cache.get_json("ai:v0:rec:nope", kind="rec") is None

async def test_corrupt_value_is_a_miss(fake_redis):
    fake_redis.store["ai:v0:catalog"] = "not json"
    assert await redis_cache.get_json("ai:v0:catalog", kind="catalog") is None

async def test_disabled_cache_is_noop():
    # conftest's autouse fixture makes _get_redis() return None
    assert await redis_cache.make_key("rec", "x") is None
    assert await redis_cache.get_json(None, kind="rec") is None
    await redis_cache.set_json(None, [1], ttl=60)
    await redis_cache.invalidate()

async def test_cache_disabled_setting(monkeypatch):
    monkeypatch.undo()  # drop conftest's patch so the real _get_redis runs
    monkeypatch.setattr(redis_cache.settings, "CACHE_ENABLED", False)
    assert redis_cache._get_redis() is None

async def test_redis_down_fails_soft_and_backs_off(monkeypatch):
    monkeypatch.undo()
    broken = BrokenRedis()
    monkeypatch.setattr(redis_cache, "_redis", broken)
    monkeypatch.setattr(redis_cache, "_down_until", 0.0)
    assert await redis_cache.make_key("rec", "x") is None   # error swallowed
    assert redis_cache._get_redis() is None                 # now backing off
    monkeypatch.setattr(redis_cache, "_down_until", 0.0)
    assert redis_cache._get_redis() is broken               # retried after backoff
    await redis_cache.set_json("k", [1], ttl=60)            # no exception
    await redis_cache.invalidate()                          # no exception
    monkeypatch.setattr(redis_cache, "_down_until", 0.0)
    assert await redis_cache.get_json("k", kind="rec") is None


# ─── catalog cache ──────────────────────────────────────────────────────────

@patch("app.services.catalog.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_catalog_fetched_once_then_cached(mock_fetch, fake_redis):
    from app.services.catalog import get_catalog
    assert await get_catalog() == MOCK_PRODUCTS
    assert await get_catalog() == MOCK_PRODUCTS
    mock_fetch.assert_awaited_once()

@patch("app.services.catalog.get_all_products", new_callable=AsyncMock, return_value=[])
async def test_empty_catalog_not_cached(mock_fetch, fake_redis):
    from app.services.catalog import get_catalog
    await get_catalog()
    await get_catalog()
    assert mock_fetch.await_count == 2

@patch("app.services.catalog.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_catalog_refetched_after_invalidate(mock_fetch, fake_redis):
    from app.services.catalog import get_catalog
    await get_catalog()
    await redis_cache.invalidate()
    await get_catalog()
    assert mock_fetch.await_count == 2


# ─── recommendation / suggestion caching ─────────────────────────────────────

REC_REPLY = '{"recommendations": [{"name": "AirPods Pro", "reason": "Pairs well"}]}'

@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_catalog", new_callable=AsyncMock)
async def test_recommendation_cache_hit_skips_llm_and_uses_current_price(mock_catalog, mock_llm, fake_redis):
    from app.services.recommendation import get_recommendations
    mock_catalog.return_value = MOCK_PRODUCTS
    mock_llm.generate = AsyncMock(return_value=REC_REPLY)
    first = await get_recommendations(product_name="iPhone")

    # Price changes in the catalog; the cached pick must show the new price
    mock_catalog.return_value = [{**MOCK_PRODUCTS[0]}, {**MOCK_PRODUCTS[1], "price": 199.99}]
    second = await get_recommendations(product_name="  iphone ")

    mock_llm.generate.assert_awaited_once()
    assert first[0]["price"] == 249.99
    assert second == [{**first[0], "price": 199.99}]

@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_catalog", new_callable=AsyncMock)
async def test_recommendation_cached_pick_dropped_when_product_deleted(mock_catalog, mock_llm, fake_redis):
    from app.services.recommendation import get_recommendations
    mock_catalog.return_value = MOCK_PRODUCTS
    mock_llm.generate = AsyncMock(return_value=REC_REPLY)
    await get_recommendations(product_name="iPhone")
    mock_catalog.return_value = [MOCK_PRODUCTS[0]]  # AirPods deleted
    assert await get_recommendations(product_name="iPhone") == []

@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_catalog", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_recommendation_cache_hit_drops_queried_product(mock_catalog, mock_llm, fake_redis):
    """Entries cached before the filter existed can hold the queried product; the hit path drops it."""
    from app.services.recommendation import get_recommendations
    key = await redis_cache.make_key("rec", "iPhone 15 Pro", "")
    await redis_cache.set_json(key, [{"id": "p1", "reason": "Same"}, {"id": "p2", "reason": "Pairs well"}], 60)
    mock_llm.generate = AsyncMock()
    result = await get_recommendations(product_name="iPhone 15 Pro")
    mock_llm.generate.assert_not_awaited()
    assert [r["id"] for r in result] == ["p2"]

@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_catalog", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_recommendation_empty_result_not_cached(mock_catalog, mock_llm, fake_redis):
    from app.services.recommendation import get_recommendations
    mock_llm.generate = AsyncMock(return_value='{"recommendations": [{"name": "Made Up"}]}')
    await get_recommendations(product_name="iPhone")
    await get_recommendations(product_name="iPhone")
    assert mock_llm.generate.await_count == 2

@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_catalog", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_recommendation_invalid_reply_not_cached(mock_catalog, mock_llm, fake_redis):
    from fastapi import HTTPException
    from app.services.recommendation import get_recommendations
    mock_llm.generate = AsyncMock(side_effect=["busy, try later", REC_REPLY])
    with pytest.raises(HTTPException):
        await get_recommendations(product_name="iPhone")
    assert (await get_recommendations(product_name="iPhone"))[0]["id"] == "p2"

@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_catalog", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_recommendation_cache_stores_only_ids_and_reasons(mock_catalog, mock_llm, fake_redis):
    import json
    from app.services.recommendation import get_recommendations
    mock_llm.generate = AsyncMock(return_value=REC_REPLY)
    await get_recommendations(product_name="iPhone")
    key = await redis_cache.make_key("rec", "iPhone", "")
    assert json.loads(fake_redis.store[key]) == [{"id": "p2", "reason": "Pairs well"}]

@patch("app.services.suggestion.llm_client")
@patch("app.services.suggestion.get_catalog", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_suggest_cache_hit_returns_same_result(mock_catalog, mock_llm, fake_redis):
    from app.services.suggestion import suggest_products
    mock_llm.generate = AsyncMock(return_value=(
        '{"matches": [{"name": "AirPods Pro", "match_reason": "gift"}],'
        ' "search_tags": ["gift"], "search_category": "Electronics"}'
    ))
    first = await suggest_products("Birthday gift")
    second = await suggest_products("birthday   gift")
    mock_llm.generate.assert_awaited_once()
    assert first == second
    assert second["matches"][0]["id"] == "p2"
    assert second["search_tags"] == ["gift"]


# ─── invalidator consumer ───────────────────────────────────────────────────

@patch("app.kafka.cache_invalidator.redis_cache.invalidate", new_callable=AsyncMock)
@patch("app.kafka.cache_invalidator.AIOKafkaConsumer")
async def test_invalidator_invalidates_per_event(mock_consumer_cls, mock_invalidate):
    import asyncio
    from app.kafka.cache_invalidator import start_cache_invalidator

    class OneShotConsumer:
        def __init__(self):
            self.start = AsyncMock()
            self.stop = AsyncMock()

        def __aiter__(self):
            async def gen():
                yield MagicMock()
                yield MagicMock()
                raise asyncio.CancelledError  # end the loop like a shutdown would
            return gen()

    consumer = OneShotConsumer()
    mock_consumer_cls.return_value = consumer
    with pytest.raises(asyncio.CancelledError):
        await start_cache_invalidator()
    assert mock_invalidate.await_count == 2
    consumer.stop.assert_awaited_once()
    assert mock_consumer_cls.call_args.kwargs["group_id"].endswith("-cache")
