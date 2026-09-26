# Tests run against the defaults in app/config.py (what CI sees), not your local .env.
# pytest loads this before any test module, so every later `from app.config import settings`
# gets this instance. Shell env vars still apply, e.g. `AUTH_ENABLED=true pytest`.
import atexit
import os
import shutil
import tempfile

# Keep test logs out of logs/<service>.log: importing app.main runs setup_logging(), which
# appends to that file, and Promtail ships it to Loki as if the running service logged it.
# logging_config reads LOG_DIR at import, so this must be set before anything imports app.main.
_test_log_dir = tempfile.mkdtemp(prefix="pytest-logs-")
os.environ["LOG_DIR"] = _test_log_dir
atexit.register(shutil.rmtree, _test_log_dir, ignore_errors=True)

import app.config  # noqa: E402

app.config.settings = app.config.Settings(_env_file=None)
