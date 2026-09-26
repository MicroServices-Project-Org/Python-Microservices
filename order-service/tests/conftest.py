# Tests run against the defaults in app/config.py (what CI sees), not your local .env.
# pytest loads this before any test module, so every later `from app.config import settings`
# gets this instance. Shell env vars still apply, e.g. `AUTH_ENABLED=true pytest`.
import app.config

app.config.settings = app.config.Settings(_env_file=None)
