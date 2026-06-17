"""Load per-trader config, falling back to default.json for any missing keys.

Usage:
    from config.loader import get_config
    cfg = get_config("Grizzlies")
    min_conf = cfg["risk"]["min_confidence"]
"""
import json
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def get_config(trader: str) -> dict:
    default_path = _CONFIG_DIR / "default.json"
    trader_path  = _CONFIG_DIR / f"{trader}.json"

    default = json.loads(default_path.read_text(encoding="utf-8"))
    if trader_path.exists():
        override = json.loads(trader_path.read_text(encoding="utf-8"))
        return _deep_merge(default, override)
    return default
