"""
config.py
Central configuration — reads from settings_manager (settings.json) with .env fallback.
All user-specific values should be set via the dashboard Settings panel.
"""

import os
from dotenv import load_dotenv
load_dotenv()

import settings_manager as sm

# ─── API Keys (read from settings / .env) ──────────────────────────────────────
ANTHROPIC_API_KEY   = sm.get("content.api_key", "") or os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY  = sm.get("tts.api_key", "")     or os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = sm.get("tts.voice_id", "")
ELEVENLABS_MODEL    = sm.get("tts.model", "eleven_multilingual_v2")
TTS_VOLUME          = sm.get("tts.volume", 0.88)
MUSIC_VOLUME_TTS    = sm.get("tts.music_volume_with_tts", 0.10)

# ─── Video ─────────────────────────────────────────────────────────────────────
VIDEO_WIDTH  = sm.get("video.width",  1080)
VIDEO_HEIGHT = sm.get("video.height", 1920)
VIDEO_FPS    = sm.get("video.fps",    30)

# ─── Colors ────────────────────────────────────────────────────────────────────
_bg = sm.get("video.background_color", [0, 0, 0])
_tx = sm.get("video.text_color",       [255, 255, 255])
_ac = sm.get("channel.accent_color",   "#d97706")

def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

BACKGROUND_COLOR = tuple(_bg) if isinstance(_bg, list) else (0, 0, 0)
TEXT_COLOR       = tuple(_tx) if isinstance(_tx, list) else (255, 255, 255)
ACCENT_COLOR     = _hex_to_rgb(_ac) if isinstance(_ac, str) else tuple(_ac)

# ─── Font Sizes ────────────────────────────────────────────────────────────────
FONT_SIZE_HOOK   = sm.get("video.sections.hook.font_size",    68)
FONT_SIZE_TITLE  = sm.get("video.sections.title.font_size",   60)
FONT_SIZE_BODY   = sm.get("video.sections.fact.font_size",    46)
FONT_SIZE_FOOTER = 32

# ─── Section Durations ─────────────────────────────────────────────────────────
HOOK_DURATION    = sm.get("video.sections.hook.duration",    3.5)
TITLE_DURATION   = sm.get("video.sections.title.duration",   3.5)
FACT_DURATION    = sm.get("video.sections.fact.duration",    7.0)
DETAIL_DURATION  = sm.get("video.sections.detail.duration",  7.0)
CLOSING_DURATION = sm.get("video.sections.closing.duration", 4.0)
CTA_DURATION     = sm.get("video.sections.cta.duration",     3.0)

# ─── Fade ──────────────────────────────────────────────────────────────────────
HOOK_FADE   = 0.3
NORMAL_FADE = 0.5

# ─── Music ─────────────────────────────────────────────────────────────────────
MUSIC_VOLUME = sm.get("video.music_volume", 0.30)

# ─── Channel ───────────────────────────────────────────────────────────────────
CHANNEL_HANDLE = sm.get("channel.name",     "My Channel")
CTA_TEXT       = sm.get("channel.cta_text", "Subscribe")

# ─── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR        = os.path.join(BASE_DIR, "music")
OUTPUT_DIR       = os.path.join(BASE_DIR, "output")
STOCK_CACHE_DIR  = os.path.join(BASE_DIR, "stock_cache")
TOKEN_FILE       = os.path.join(BASE_DIR, "youtube_token.json")
SECRETS_FILE     = os.path.join(BASE_DIR, "client_secrets.json")
USED_FACTS_FILE  = os.path.join(BASE_DIR, "used_facts.txt")
ANALYTICS_FILE   = os.path.join(BASE_DIR, "analytics.jsonl")
SCHEDULES_FILE   = os.path.join(BASE_DIR, "schedules.json")
SAVES_FILE       = os.path.join(BASE_DIR, "saves.json")
CHANNELS_DIR     = os.path.join(BASE_DIR, "channels")
CHANNELS_FILE    = os.path.join(BASE_DIR, "channels.json")

os.makedirs(MUSIC_DIR,       exist_ok=True)
os.makedirs(OUTPUT_DIR,      exist_ok=True)
os.makedirs(STOCK_CACHE_DIR, exist_ok=True)
os.makedirs(CHANNELS_DIR,    exist_ok=True)

# ─── YouTube ───────────────────────────────────────────────────────────────────
YOUTUBE_CATEGORY_ID = sm.get("upload.category_id", "27")
YOUTUBE_PRIVACY     = sm.get("upload.privacy",      "public")
UPLOAD_HOUR         = sm.get("upload.hour",         10)
UPLOAD_MINUTE       = sm.get("upload.minute",       0)

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
