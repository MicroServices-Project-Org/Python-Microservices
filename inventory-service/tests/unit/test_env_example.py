import re
from pathlib import Path

from app.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def _example_keys() -> set[str]:
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", ENV_EXAMPLE.read_text(), re.MULTILINE))


def test_env_example_has_every_setting():
    missing = set(Settings.model_fields) - _example_keys()
    assert not missing, f"Add to .env.example: {sorted(missing)}"


def test_env_example_has_no_unknown_keys():
    unknown = _example_keys() - set(Settings.model_fields)
    assert not unknown, f"Not in app/config.py (would fail startup): {sorted(unknown)}"


def test_env_example_loads():
    Settings(_env_file=ENV_EXAMPLE)
