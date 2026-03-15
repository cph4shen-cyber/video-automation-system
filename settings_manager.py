"""
settings_manager.py
Manages user settings. Merges settings.default.json with user's settings.json.
API keys can come from settings.json (UI-saved) or .env (fallback).
settings.json is gitignored (personal), settings.default.json is in git (template).
"""

import copy
import json
import os

_BASE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_FILE = os.path.join(_BASE, "settings.default.json")
_USER_FILE    = os.path.join(_BASE, "settings.json")

_cache: dict | None = None


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    with open(_DEFAULT_FILE, "r", encoding="utf-8") as f:
        defaults = json.load(f)

    user = {}
    if os.path.exists(_USER_FILE):
        with open(_USER_FILE, "r", encoding="utf-8") as f:
            try:
                user = json.load(f)
            except Exception:
                user = {}

    merged = _deep_merge(defaults, user)

    # .env fallback for API keys (env overrides settings.json only if settings.json key is empty)
    from dotenv import load_dotenv
    load_dotenv()

    def env_fallback(path: list, env_var: str):
        """If setting is empty, try env var."""
        d = merged
        for key in path[:-1]:
            d = d.setdefault(key, {})
        if not d.get(path[-1]):
            val = os.getenv(env_var, "")
            if val:
                d[path[-1]] = val

    env_fallback(["content", "api_key"],      "ANTHROPIC_API_KEY")
    env_fallback(["tts", "api_key"],           "ELEVENLABS_API_KEY")
    env_fallback(["stock_video", "pexels_api_key"], "PEXELS_API_KEY")

    _cache = merged
    return _cache


def get(path: str, default=None):
    """Get a nested setting by dot-path. e.g. get('channel.name')"""
    keys = path.split(".")
    d = load()
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return default
    return d if d is not None else default


def save(updates: dict):
    """Save updates to settings.json (partial update, deep merge)."""
    global _cache

    existing = {}
    if os.path.exists(_USER_FILE):
        with open(_USER_FILE, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except Exception:
                existing = {}

    merged = _deep_merge(existing, updates)

    with open(_USER_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    # Invalidate cache
    _cache = None


def reload():
    global _cache
    _cache = None
    return load()
