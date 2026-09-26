# Identical in all six services, like app/logging_config.py itself.
import io
import logging

from app.logging_config import RepeatThrottleFilter


def make_logger(name, throttle, n_handlers=1):
    streams = [io.StringIO() for _ in range(n_handlers)]
    logger = logging.getLogger(name)
    logger.handlers = []
    for stream in streams:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.addFilter(throttle)
        logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, streams


def lines(stream):
    return stream.getvalue().splitlines()


def test_first_error_logged_repeats_dropped():
    logger, (out,) = make_logger("aiokafka.conn.t1", RepeatThrottleFilter(window=60))
    for i in range(100):
        logger.error("Unable connect to node with id %s: %s", 1, f"attempt {i}")
    assert lines(out) == ["Unable connect to node with id 1: attempt 0"]


def test_suppressed_count_reported_after_window(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("app.logging_config.time.monotonic", lambda: clock[0])
    logger, (out,) = make_logger("aiokafka.conn.t2", RepeatThrottleFilter(window=60))
    for _ in range(10):
        logger.error("Heartbeat failed: %s", "coordinator dead")
    clock[0] += 61
    logger.error("Heartbeat failed: %s", "coordinator dead")
    assert lines(out) == [
        "Heartbeat failed: coordinator dead",
        "Heartbeat failed: coordinator dead [9 similar messages suppressed since the last one]",
    ]


def test_different_messages_throttled_separately():
    logger, (out,) = make_logger("aiokafka.conn.t3", RepeatThrottleFilter(window=60))
    logger.error("Unable connect to node %s", 1)
    logger.error("Unable to update metadata from %s", 1)
    logger.error("Unable connect to node %s", 1)
    assert lines(out) == ["Unable connect to node 1", "Unable to update metadata from 1"]


def test_non_kafka_loggers_and_info_untouched():
    throttle = RepeatThrottleFilter(window=60)
    app_logger, (app_out,) = make_logger("app.kafka.consumer.t4", throttle)
    kafka_logger, (kafka_out,) = make_logger("aiokafka.t4", throttle)
    for _ in range(3):
        app_logger.error("Kafka consumer failed")
        kafka_logger.info("Joined group")
    assert len(lines(app_out)) == 3
    assert len(lines(kafka_out)) == 3


def test_every_handler_gets_the_same_decision():
    # One filter instance is shared by the stdout and file handlers in setup_logging
    logger, (stdout, logfile) = make_logger("aiokafka.t5", RepeatThrottleFilter(window=60), n_handlers=2)
    for _ in range(5):
        logger.error("Unable connect to node %s", 1)
    assert lines(stdout) == lines(logfile) == ["Unable connect to node 1"]


def test_tests_do_not_log_into_the_real_logs_dir():
    # tests/conftest.py points LOG_DIR at a temp dir, so pytest runs never write to
    # logs/<service>.log (which Promtail ships to Loki as if the service logged it)
    from app import logging_config
    assert logging_config.LOG_DIR != logging_config._PROJECT_ROOT / "logs"
