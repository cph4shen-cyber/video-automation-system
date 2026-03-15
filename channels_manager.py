"""
channels_manager.py
Kanal manifest (channels.json) CRUD ve OAuth token yönetimi.
_channels_lock altında tüm dosya I/O yapılır.
"""

import json
import os
import pickle
import shutil
import threading
from datetime import datetime

from config import CHANNELS_DIR, CHANNELS_FILE, TOKEN_FILE, YOUTUBE_SCOPES

_channels_lock = threading.Lock()


# ─── Manifest Helpers ─────────────────────────────────────────────────────────

def load_channels() -> list:
    """channels.json'dan kanal listesini döner. Dosya yoksa []."""
    with _channels_lock:
        return _load_channels_unlocked()


def _load_channels_unlocked() -> list:
    if not os.path.exists(CHANNELS_FILE):
        return []
    try:
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_channels_unlocked(channels: list):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)


def add_channel(channel_data: dict):
    """Manifest'e kanal ekler (id çakışıyorsa günceller)."""
    with _channels_lock:
        channels = _load_channels_unlocked()
        channels = [c for c in channels if c["id"] != channel_data["id"]]
        channels.append(channel_data)
        _save_channels_unlocked(channels)


def remove_channel(channel_id: str):
    """Manifest ve token dosyasını siler."""
    with _channels_lock:
        channels = _load_channels_unlocked()
        channels = [c for c in channels if c["id"] != channel_id]
        _save_channels_unlocked(channels)
        token_path = _token_path(channel_id)
        if os.path.exists(token_path):
            os.remove(token_path)
        # Üst klasörü de temizle
        channel_dir = os.path.dirname(token_path)
        if os.path.isdir(channel_dir) and not os.listdir(channel_dir):
            os.rmdir(channel_dir)


def get_channel(channel_id: str) -> dict | None:
    """Manifest'ten tek kanal kaydı döner."""
    with _channels_lock:
        channels = _load_channels_unlocked()
        return next((c for c in channels if c["id"] == channel_id), None)


def nullify_channel_in_schedules(channel_id: str, schedules_file: str):
    """Silinen kanalı referans eden schedule'larda channel_id'yi null yapar."""
    if not os.path.exists(schedules_file):
        return
    try:
        with open(schedules_file, "r", encoding="utf-8") as f:
            schedules = json.load(f)
        changed = False
        for s in schedules:
            if s.get("channel_id") == channel_id:
                s["channel_id"] = None
                changed = True
        if changed:
            with open(schedules_file, "w", encoding="utf-8") as f:
                json.dump(schedules, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ─── Token Paths ──────────────────────────────────────────────────────────────

def _token_path(channel_id: str) -> str:
    return os.path.join(CHANNELS_DIR, channel_id, "token.pkl")


def _pending_token_path() -> str:
    return os.path.join(CHANNELS_DIR, "_pending", "token.pkl")


def save_token(channel_id: str, creds):
    """Token'ı channels/{channel_id}/token.pkl olarak kaydeder."""
    token_dir = os.path.join(CHANNELS_DIR, channel_id)
    os.makedirs(token_dir, exist_ok=True)
    with open(_token_path(channel_id), "wb") as f:
        pickle.dump(creds, f)


def save_pending_token(creds):
    """OAuth akışı sırasında geçici token kaydeder."""
    pending_dir = os.path.join(CHANNELS_DIR, "_pending")
    os.makedirs(pending_dir, exist_ok=True)
    with open(_pending_token_path(), "wb") as f:
        pickle.dump(creds, f)


def load_token(channel_id: str):
    """Token yükler. Bulamazsa None döner."""
    path = _token_path(channel_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def clear_pending():
    """_pending klasörünü temizler."""
    pending_dir = os.path.join(CHANNELS_DIR, "_pending")
    if os.path.isdir(pending_dir):
        shutil.rmtree(pending_dir, ignore_errors=True)


def get_first_channel_id() -> str | None:
    """channels.json'daki ilk kanalın id'sini döner."""
    with _channels_lock:
        channels = _load_channels_unlocked()
        return channels[0]["id"] if channels else None


# ─── Migration ────────────────────────────────────────────────────────────────

def migrate_legacy_token():
    """
    youtube_token.json varsa channels/ yapısına taşır.
    Hata durumunda dosyayı olduğu gibi bırakır.
    """
    if not os.path.exists(TOKEN_FILE):
        return

    try:
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    except Exception:
        os.remove(TOKEN_FILE)
        print("ℹ️  Bozuk eski token silindi.")
        return

    # Scope kontrolü
    required = set(YOUTUBE_SCOPES)
    granted  = set(getattr(creds, "scopes", None) or [])
    if not required.issubset(granted):
        os.remove(TOKEN_FILE)
        print("ℹ️  Eski token scope uyumsuz, silindi. Yeniden bağlantı gerekli.")
        return

    # YouTube API'den kanal bilgisi çek
    try:
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        res = yt.channels().list(part="snippet,statistics", mine=True).execute()
        items = res.get("items", [])
        if not items:
            print("ℹ️  Eski token ile kanal bilgisi alınamadı, migration atlandı.")
            return
        ch    = items[0]
        stats = ch.get("statistics", {})
        channel_data = {
            "id":               ch["id"],
            "name":             ch["snippet"]["title"],
            "handle":           ch["snippet"].get("customUrl", ""),
            "thumbnail":        ch["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count":      int(stats.get("videoCount", 0)),
            "connected_at":     datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"ℹ️  Eski token migration başarısız: {e}. Token korunuyor.")
        return

    # Token kaydet, manifest güncelle
    save_token(channel_data["id"], creds)
    add_channel(channel_data)
    os.remove(TOKEN_FILE)
    print(f"✓ Eski token migrate edildi → kanal: {channel_data['name']}")
