import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.dialects import postgresql

from app.services.inventory_service import parse_cancelled_order, restock_cancelled_order
from app.kafka import consumer


def event_bytes(**overrides) -> bytes:
    event = {
        "event_type": "ORDER_CANCELLED",
        "order_number": "ORD-1",
        "items": [
            {"product_id": "prod-001", "product_name": "iPhone 15 Pro", "quantity": 2, "price": 999.99},
            {"product_id": "prod-002", "product_name": "AirPods Pro", "quantity": 1, "price": 249.99},
        ],
    }
    event.update(overrides)
    return json.dumps(event).encode()


def make_db(claimed: bool, rowcounts=(1, 1)):
    """AsyncSession mock: first execute is the processed_events insert, then one UPDATE per item."""
    insert_result = MagicMock()
    insert_result.scalar_one_or_none.return_value = "ORD-1_ORDER_CANCELLED" if claimed else None
    update_results = [MagicMock(rowcount=n) for n in rowcounts]
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[insert_result, *update_results])
    return db


def sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


# ─── parse_cancelled_order ───────────────────────────────────────────────────

def test_parse_valid_event():
    assert parse_cancelled_order(event_bytes()) == ("ORD-1", [("prod-001", 2), ("prod-002", 1)])

@pytest.mark.parametrize("raw", [
    b"not json",
    b"\xff\xfe",
    b"[]",
    event_bytes(order_number=None),
    event_bytes(order_number=""),
    event_bytes(items="prod-001"),
    event_bytes(items=[{"product_id": "prod-001"}]),
    event_bytes(items=[{"product_id": "prod-001", "quantity": 0}]),
    event_bytes(items=[{"product_id": "prod-001", "quantity": -1}]),
    event_bytes(items=[{"product_id": "prod-001", "quantity": "2"}]),
    event_bytes(items=[{"product_id": "prod-001", "quantity": True}]),
    event_bytes(items=[{"product_id": 7, "quantity": 1}]),
    event_bytes(items=["prod-001"]),
])
def test_parse_rejects_malformed_events(raw):
    with pytest.raises(ValueError):
        parse_cancelled_order(raw)


# ─── restock_cancelled_order ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restock_claims_event_then_adds_each_item():
    db = make_db(claimed=True)
    assert await restock_cancelled_order("ORD-1", [("prod-001", 2), ("prod-002", 1)], db) == 2

    insert_stmt, upd1, upd2 = (c.args[0] for c in db.execute.await_args_list)
    assert "INSERT INTO processed_events" in sql(insert_stmt)
    assert "ON CONFLICT DO NOTHING" in sql(insert_stmt)
    assert insert_stmt.compile().params["event_key"] == "ORD-1_ORDER_CANCELLED"
    # Atomic increment, not a read-modify-write
    assert "SET quantity=(inventory.quantity +" in sql(upd1)
    assert upd1.compile().params == {"quantity_1": 2, "product_id_1": "prod-001"}
    assert upd2.compile().params == {"quantity_1": 1, "product_id_1": "prod-002"}

@pytest.mark.asyncio
async def test_restock_duplicate_event_changes_nothing():
    db = make_db(claimed=False)
    assert await restock_cancelled_order("ORD-1", [("prod-001", 2)], db) is None
    assert db.execute.await_count == 1  # only the insert attempt, no UPDATE

@pytest.mark.asyncio
async def test_restock_unknown_product_is_logged_and_others_still_restocked(caplog):
    db = make_db(claimed=True, rowcounts=(0, 1))
    assert await restock_cancelled_order("ORD-1", [("gone", 2), ("prod-002", 1)], db) == 1
    assert db.execute.await_count == 3
    assert "product gone has no inventory row" in caplog.text


# ─── consumer ────────────────────────────────────────────────────────────────

def mock_session_factory(db):
    """AsyncSessionLocal() → async context manager yielding db, with db.begin() also a context manager."""
    begin = MagicMock()
    begin.__aenter__ = AsyncMock()
    begin.__aexit__ = AsyncMock(return_value=False)
    db.begin = MagicMock(return_value=begin)
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=db)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=session_cm), begin

@pytest.mark.asyncio
@patch("app.kafka.consumer.restock_cancelled_order", new_callable=AsyncMock, return_value=2)
async def test_handle_restocks_inside_a_transaction(mock_restock):
    db = AsyncMock()
    factory, begin = mock_session_factory(db)
    with patch("app.kafka.consumer.AsyncSessionLocal", factory):
        await consumer._handle_order_cancelled(event_bytes())
    mock_restock.assert_awaited_once_with("ORD-1", [("prod-001", 2), ("prod-002", 1)], db)
    begin.__aenter__.assert_awaited_once()
    begin.__aexit__.assert_awaited_once()

@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [b"garbage", None])
@patch("app.kafka.consumer.restock_cancelled_order", new_callable=AsyncMock)
async def test_handle_skips_malformed_and_tombstone_events(mock_restock, raw):
    factory = MagicMock()
    with patch("app.kafka.consumer.AsyncSessionLocal", factory):
        await consumer._handle_order_cancelled(raw)  # must not raise
    factory.assert_not_called()
    mock_restock.assert_not_awaited()


class FakeConsumer:
    def __init__(self, values):
        self.values = values
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.commit = AsyncMock()

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for v in self.values:
            yield MagicMock(value=v)

@pytest.mark.asyncio
async def test_consume_commits_after_each_handled_event():
    fake = FakeConsumer([b"a", b"b"])
    handled = []

    async def handle(raw):
        assert fake.commit.await_count == len(handled)  # not committed before it's handled
        handled.append(raw)

    with patch("app.kafka.consumer.AIOKafkaConsumer", return_value=fake) as ctor, \
         patch("app.kafka.consumer._handle_order_cancelled", side_effect=handle):
        await consumer._consume()
    assert handled == [b"a", b"b"]
    assert fake.commit.await_count == 2
    assert ctor.call_args.kwargs["enable_auto_commit"] is False
    fake.stop.assert_awaited_once()

@pytest.mark.asyncio
async def test_consume_does_not_commit_when_restock_fails():
    fake = FakeConsumer([b"a"])
    with patch("app.kafka.consumer.AIOKafkaConsumer", return_value=fake), \
         patch("app.kafka.consumer._handle_order_cancelled", side_effect=ConnectionError("db down")):
        with pytest.raises(ConnectionError):
            await consumer._consume()
    fake.commit.assert_not_awaited()
    fake.stop.assert_awaited_once()

@pytest.mark.asyncio
async def test_start_consumer_retries_after_failure():
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    with patch("app.kafka.consumer._consume", new_callable=AsyncMock, side_effect=ConnectionError("kafka down")) as mock_consume, \
         patch("app.kafka.consumer.asyncio.sleep", side_effect=fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            await consumer.start_consumer()
    assert mock_consume.await_count == 2
    assert sleeps == [consumer.RETRY_SECONDS, consumer.RETRY_SECONDS]
