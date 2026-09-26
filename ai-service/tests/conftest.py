# Tests run against the defaults in app/config.py (what CI sees), not your local .env.
# pytest loads this before any test module, so every later `from app.config import settings`
# gets this instance. Shell env vars still apply, e.g. `AUTH_ENABLED=true pytest`.
import app.config

app.config.settings = app.config.Settings(_env_file=None)


import pytest


@pytest.fixture(autouse=True)
def no_real_redis(monkeypatch):
    """Tests never touch a real Redis: the cache is a no-op unless a test swaps in a fake."""
    from app.cache import redis_cache
    monkeypatch.setattr(redis_cache, "_get_redis", lambda: None)
