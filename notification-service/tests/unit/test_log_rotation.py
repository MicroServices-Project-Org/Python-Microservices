# Identical in all six services, like app/logging_config.py itself.
import logging
import logging.handlers

import pytest

from app import logging_config


@pytest.fixture
def small_rotating_logs(tmp_path, monkeypatch):
    """Run the real setup_logging() into tmp_path with a tiny size limit, then restore the root logger."""
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logging_config, "LOG_MAX_BYTES", 2_000)
    monkeypatch.setattr(logging_config, "LOG_BACKUP_COUNT", 2)
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    logging_config.setup_logging("rotation-test")
    yield tmp_path
    for handler in root.handlers:
        handler.close()
    root.handlers, root.level = saved_handlers, saved_level


def test_file_handler_rotates(small_rotating_logs):
    handlers = [h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)]
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.handlers.RotatingFileHandler)


def test_disk_usage_is_capped(small_rotating_logs):
    log = logging.getLogger("app.rotation")
    for i in range(2_000):  # ~400 KB of log lines against a 2 KB x 3 file cap
        log.info("line %d %s", i, "x" * 100)
    files = sorted(p.name for p in small_rotating_logs.iterdir())
    assert files == ["rotation-test.log", "rotation-test.log.1", "rotation-test.log.2"]
    total = sum(p.stat().st_size for p in small_rotating_logs.iterdir())
    assert total <= 3 * (2_000 + 1_000)  # each file stops just past maxBytes (one record over at most)


def test_only_current_file_matches_promtail_glob(small_rotating_logs):
    # Promtail tails logs/*.log, so rotated backups must not match (or they'd be re-shipped)
    log = logging.getLogger("app.rotation")
    for i in range(500):
        log.info("line %d %s", i, "x" * 100)
    assert [p.name for p in small_rotating_logs.glob("*.log")] == ["rotation-test.log"]


def test_defaults():
    assert logging_config.LOG_MAX_BYTES == 10 * 1024 * 1024
    assert logging_config.LOG_BACKUP_COUNT == 3
