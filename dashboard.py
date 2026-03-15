"""
dashboard.py
Video Automation System — Flask tabanlı web arayüzü.
http://localhost:5000 adresinden erişin.
"""

import json
import os
import queue
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta

from flask import Flask, Response, jsonify, render_template, request, send_file, stream_with_context
import settings_manager as sm_module

from config import (
    ANALYTICS_FILE, BASE_DIR, SAVES_FILE, SCHEDULES_FILE, SECRETS_FILE,
    UPLOAD_HOUR, UPLOAD_MINUTE, YOUTUBE_SCOPES,
)
from channels_manager import (
    load_channels, add_channel, remove_channel, nullify_channel_in_schedules,
    save_token, save_pending_token, clear_pending, migrate_legacy_token,
)

# ─── Log Queue (stdout tee) ───────────────────────────────────────────────────
log_queue: queue.Queue = queue.Queue(maxsize=1000)
log_history: list = []
_log_lock = threading.Lock()


class TeeStream:
    """stdout'a yazılan her şeyi hem terminale hem log_queue'ya yönlendirir."""
    def __init__(self, original):
        self.original = original

    def write(self, text):
        self.original.write(text)
        stripped = text.strip()
        if stripped:
            entry = {
                "t": datetime.now().strftime("%H:%M:%S"),
                "m": stripped,
                "l": "ERROR" if "❌" in stripped or "HATA" in stripped else
                     "WARN"  if "⚠️" in stripped else "INFO",
            }
            with _log_lock:
                log_history.append(entry)
                if len(log_history) > 300:
                    log_history.pop(0)
            try:
                log_queue.put_nowait(entry)
            except queue.Full:
                pass

    def flush(self):
        self.original.flush()

    def fileno(self):
        return self.original.fileno()


sys.stdout = TeeStream(sys.stdout)

# ─── Legacy token migration ────────────────────────────────────────────────────
migrate_legacy_token()

# ─── Geç import (stdout tee aktif olduktan sonra) ─────────────────────────────
from generate_content import generate_content  # noqa: E402
from generate_video import generate_video      # noqa: E402
from upload_youtube import get_youtube_client, upload_video  # noqa: E402

# ─── Global State ─────────────────────────────────────────────────────────────
pipeline_lock = threading.Lock()

pipeline_state = {
    "running":       False,
    "current_step":  0,        # 0=idle 1=içerik 2=video 3=yükleme
    "step_started":  None,     # ISO timestamp, adım başlangıcı
    "step_content":  None,     # üretilen içerik dict
    "last_run":      None,
    "last_status":   None,     # "success" | "error"
    "last_video_id": None,
    "last_title":    None,
    "last_error":    None,
}

scheduler_stop_event = threading.Event()
scheduler_thread: threading.Thread | None = None
scheduler_running = False

# ─── Channel Connect State ────────────────────────────────────────────────────
_connect_lock  = threading.Lock()
_connect_state: dict = {"status": "idle"}  # idle | pending | done | error

# ─── Schedules ────────────────────────────────────────────────────────────────
_schedules: list = []
_schedules_lock = threading.Lock()


def _load_schedules():
    global _schedules
    if os.path.exists(SCHEDULES_FILE):
        try:
            with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
                _schedules = json.load(f)
            return
        except Exception:
            pass
    # Varsayılan plan (config'den)
    _schedules = [{
        "id":             str(uuid.uuid4()),
        "label":          "Varsayılan",
        "time":           f"{UPLOAD_HOUR:02d}:{UPLOAD_MINUTE:02d}",
        "date":           None,
        "topic":          "",
        "enabled":        True,
        "last_triggered": None,
        "created_at":     datetime.now().isoformat(),
    }]
    _save_schedules()


def _save_schedules():
    with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
        json.dump(_schedules, f, ensure_ascii=False, indent=2)

# ─── Preview State ────────────────────────────────────────────────────────────
_preview_lock = threading.Lock()
_preview_state: dict = {
    "status":         "idle",   # idle | generating | ready | error
    "video_filename": None,
    "srt_path":       None,
    "thumbnail_path": None,
    "content":        None,
    "privacy":        None,
    "category_id":    None,
    "publish_at":     None,
    "error":          None,
    "topic":          None,     # orijinal konu (re-generate için)
    "channel_id":     None,
}

# ─── Cache ────────────────────────────────────────────────────────────────────
_channel_cache: dict = {}
_videos_cache:  dict = {}

# ─── OAuth Connect Worker ────────────────────────────────────────────────────
def _oauth_connect_worker():
    """
    OAuth akışını arka planda yürütür.
    Non-daemon thread — Flask kapanırken callback sunucusunu bekler.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    try:
        if not os.path.exists(SECRETS_FILE):
            raise FileNotFoundError(
                f"'{SECRETS_FILE}' bulunamadı. "
                "Google Cloud Console'dan indirip klasöre koy."
            )
        flow  = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, YOUTUBE_SCOPES)
        creds = flow.run_local_server(port=0, timeout_seconds=300)

        # Geçici token kaydet
        save_pending_token(creds)

        # Kanal bilgisi çek
        yt  = build("youtube", "v3", credentials=creds)
        res = yt.channels().list(part="snippet,statistics", mine=True).execute()
        items = res.get("items", [])
        if not items:
            raise RuntimeError("Bu Google hesabında YouTube kanalı bulunamadı.")

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

        # Kalıcı konuma taşı
        save_token(channel_data["id"], creds)
        clear_pending()
        add_channel(channel_data)

        with _connect_lock:
            _connect_state.update({"status": "done"})
        print(f"✓ Kanal bağlandı: {channel_data['name']}")

    except Exception as e:
        clear_pending()
        with _connect_lock:
            _connect_state.update({"status": "error", "error": str(e)})
        print(f"❌ OAuth hatası: {e}")


# ─── Flask App ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True


# ─── Pipeline ─────────────────────────────────────────────────────────────────
_VIDEO_FIELDS = {"hook", "title", "fact", "detail", "closing"}


def _run_pipeline(topic: str = "", content_override: dict = None,
                  privacy: str = None, category_id: str = None,
                  publish_at: str = None, channel_id: str = None):
    with pipeline_lock:
        if pipeline_state["running"]:
            return
        pipeline_state["running"] = True

    # Orijinal parametreleri re-generate için kaydet
    with _preview_lock:
        _preview_state["topic"]       = topic
        _preview_state["privacy"]     = privacy
        _preview_state["category_id"] = category_id
        _preview_state["publish_at"]  = publish_at
        _preview_state["channel_id"]  = channel_id
        _preview_state["status"]      = "generating"
        _preview_state["error"]       = None

    try:
        print(f"\n{'═'*50}")
        print(f"🚀 Pipeline başlatıldı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'═'*50}")

        # Adım 1: İçerik
        with pipeline_lock:
            pipeline_state["current_step"] = 1
            pipeline_state["step_started"] = datetime.now().isoformat()
            pipeline_state["step_content"] = None

        if content_override and _VIDEO_FIELDS.issubset(set(content_override.keys())):
            print("📝 Adım 1/3: İçerik düzenleyiciden alındı (Claude atlandı).")
            content = dict(content_override)
        else:
            print("📝 Adım 1/3: İçerik üretiliyor...")
            content = generate_content(topic=topic)
            if content_override:
                for k, v in content_override.items():
                    if v:
                        content[k] = v

        with pipeline_lock:
            pipeline_state["step_content"] = {
                "title":           content.get("title", ""),
                "hook":            content.get("hook", ""),
                "youtube_title":   content.get("youtube_title", ""),
                "primary_keyword": content.get("primary_keyword", ""),
            }
        print(f"   ✓ Başlık: {content.get('title','')}")
        print(f"   ✓ Hook: {content.get('hook','')[:60]}")

        # Adım 2: Video
        with pipeline_lock:
            pipeline_state["current_step"] = 2
            pipeline_state["step_started"] = datetime.now().isoformat()
        print("🎬 Adım 2/3: Video oluşturuluyor...")
        video_path, srt_path, thumbnail_path = generate_video(content)
        vname = os.path.basename(video_path)
        print(f"   ✓ Video: {vname}")

        # Adım 2 bitti — kullanıcı onayı bekleniyor, yükleme henüz yapılmıyor
        with _preview_lock:
            _preview_state["status"]         = "ready"
            _preview_state["video_filename"] = vname
            _preview_state["srt_path"]       = srt_path
            _preview_state["thumbnail_path"] = thumbnail_path
            _preview_state["content"]        = content
        with pipeline_lock:
            pipeline_state["current_step"] = 0
        print(f"⏳ Video hazır, kullanıcı onayı bekleniyor: {vname}")
        print(f"{'═'*50}\n")

    except Exception as e:
        print(f"❌ HATA: {e}")
        with _preview_lock:
            _preview_state["status"] = "error"
            _preview_state["error"]  = str(e)
        with pipeline_lock:
            pipeline_state["current_step"] = 0
            pipeline_state["last_run"]     = datetime.now().isoformat()
            pipeline_state["last_status"]  = "error"
            pipeline_state["last_error"]   = str(e)
    finally:
        with pipeline_lock:
            pipeline_state["running"] = False


def start_pipeline_async(topic: str = "", content_override: dict = None,
                         privacy: str = None, category_id: str = None,
                         publish_at: str = None, channel_id: str = None):
    with pipeline_lock:
        if pipeline_state["running"]:
            return False, "Pipeline zaten çalışıyor"
    t = threading.Thread(
        target=_run_pipeline,
        kwargs=dict(topic=topic, content_override=content_override,
                    privacy=privacy, category_id=category_id,
                    publish_at=publish_at, channel_id=channel_id),
        daemon=True,
    )
    t.start()
    return True, "Pipeline başlatıldı"


# ─── Preview Pipeline (video üret, yükleme yok) ───────────────────────────────
def _run_preview(topic: str = "", content_override: dict = None,
                 privacy: str = None, category_id: str = None, publish_at: str = None):
    with _preview_lock:
        _preview_state["status"]         = "generating"
        _preview_state["video_filename"] = None
        _preview_state["srt_path"]       = None
        _preview_state["thumbnail_path"] = None
        _preview_state["content"]        = None
        _preview_state["privacy"]        = privacy
        _preview_state["category_id"]    = category_id
        _preview_state["publish_at"]     = publish_at
        _preview_state["error"]          = None
    with pipeline_lock:
        pipeline_state["current_step"] = 1
        pipeline_state["step_started"] = datetime.now().isoformat()
        pipeline_state["step_content"] = None
        pipeline_state["running"]      = True
    try:
        print(f"\n{'─'*50}")
        print(f"🎬 Önizleme başlatıldı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("📝 Adım 1/2: İçerik hazırlanıyor...")
        if content_override and _VIDEO_FIELDS.issubset(set(content_override.keys())):
            content = dict(content_override)
        else:
            content = generate_content(topic=topic)
            if content_override:
                for k, v in content_override.items():
                    if v:
                        content[k] = v
        with pipeline_lock:
            pipeline_state["step_content"] = {
                "title":         content.get("title", ""),
                "hook":          content.get("hook", ""),
                "youtube_title": content.get("youtube_title", ""),
                "primary_keyword": content.get("primary_keyword", ""),
            }
            pipeline_state["current_step"] = 2
            pipeline_state["step_started"] = datetime.now().isoformat()
        print(f"   ✓ Başlık: {content.get('title','')}")
        print("🎬 Adım 2/2: Video oluşturuluyor...")
        video_path, srt_path, thumbnail_path = generate_video(content)
        video_filename = os.path.basename(video_path)
        with _preview_lock:
            _preview_state["status"]         = "ready"
            _preview_state["video_filename"] = video_filename
            _preview_state["srt_path"]       = srt_path
            _preview_state["thumbnail_path"] = thumbnail_path
            _preview_state["content"]        = content
        with pipeline_lock:
            pipeline_state["current_step"] = 0
        print(f"✅ Önizleme hazır: {video_filename}")
        print(f"{'─'*50}\n")
    except Exception as e:
        print(f"❌ Önizleme hatası: {e}")
        with _preview_lock:
            _preview_state["status"] = "error"
            _preview_state["error"]  = str(e)
        with pipeline_lock:
            pipeline_state["current_step"] = 0
            pipeline_state["last_status"]  = "error"
            pipeline_state["last_error"]   = str(e)
    finally:
        with pipeline_lock:
            pipeline_state["running"] = False


def start_preview_async(topic: str = "", content_override: dict = None,
                        privacy: str = None, category_id: str = None, publish_at: str = None):
    with _preview_lock:
        if _preview_state["status"] == "generating":
            return False, "Video zaten oluşturuluyor"
    with pipeline_lock:
        if pipeline_state["running"]:
            return False, "Pipeline zaten çalışıyor"
    t = threading.Thread(
        target=_run_preview,
        kwargs=dict(topic=topic, content_override=content_override,
                    privacy=privacy, category_id=category_id, publish_at=publish_at),
        daemon=True,
    )
    t.start()
    return True, "Önizleme başlatıldı"


# ─── Scheduler ────────────────────────────────────────────────────────────────
def _scheduler_worker(stop_event: threading.Event):
    with _schedules_lock:
        active = sum(1 for s in _schedules if s.get("enabled"))
    print(f"📅 Zamanlayıcı aktif. {active} plan yüklendi.")
    last_checked = ""
    while not stop_event.is_set():
        now = datetime.now()
        now_str   = now.strftime("%Y-%m-%d %H:%M")
        now_date  = now.strftime("%Y-%m-%d")
        now_time  = now.strftime("%H:%M")

        if now_str != last_checked:
            last_checked = now_str
            with _schedules_lock:
                changed = False
                for s in _schedules:
                    if not s.get("enabled"):
                        continue
                    if s.get("last_triggered") == now_str:
                        continue
                    s_time = s.get("time", "")
                    s_date = s.get("date")  # None = her gün
                    if s_time != now_time:
                        continue
                    if s_date and s_date != now_date:
                        continue
                    # Tetikle
                    s["last_triggered"] = now_str
                    topic   = s.get("topic", "")
                    save_id = s.get("save_id")
                    label   = s.get("label") or s["id"][:8]
                    print(f"⏰ Plan tetiklendi: {label} — {s_time}")
                    # save_id varsa kayıtlı içeriği kullan
                    content_override = None
                    privacy = category_id = publish_at = None
                    if save_id and os.path.exists(SAVES_FILE):
                        try:
                            with open(SAVES_FILE, "r", encoding="utf-8") as _sf:
                                _saves = json.load(_sf)
                            _sv = next((x for x in _saves if x["id"] == save_id), None)
                            if _sv:
                                content_override = _sv.get("content") or None
                                _set = _sv.get("settings") or {}
                                privacy     = _set.get("privacy")
                                category_id = _set.get("category_id")
                                publish_at  = _set.get("publish_at")
                                topic       = _sv.get("topic", topic)
                        except Exception:
                            pass
                    start_pipeline_async(topic, content_override=content_override,
                                         privacy=privacy, category_id=category_id,
                                         publish_at=publish_at,
                                         channel_id=s.get("channel_id"))
                    # Tek seferlik planı devre dışı bırak
                    if s_date:
                        s["enabled"] = False
                    changed = True
                if changed:
                    _save_schedules()

        stop_event.wait(15)
    print("⛔ Zamanlayıcı durduruldu.")


def start_scheduler():
    global scheduler_thread, scheduler_stop_event, scheduler_running
    if scheduler_running:
        return False, "Zamanlayıcı zaten çalışıyor"
    scheduler_stop_event = threading.Event()
    scheduler_thread = threading.Thread(
        target=_scheduler_worker, args=(scheduler_stop_event,), daemon=True
    )
    scheduler_thread.start()
    scheduler_running = True
    return True, "Zamanlayıcı başlatıldı"


def stop_scheduler():
    global scheduler_running
    if not scheduler_running:
        return False, "Zamanlayıcı zaten durmuş"
    scheduler_stop_event.set()
    if scheduler_thread:
        scheduler_thread.join(timeout=3)
    scheduler_running = False
    return True, "Zamanlayıcı durduruldu"


# ─── YouTube Helpers ──────────────────────────────────────────────────────────
def _get_channel():
    now = datetime.now()
    if _channel_cache.get("data") and (now - _channel_cache["at"]).total_seconds() < 300:
        return _channel_cache["data"]
    youtube = get_youtube_client()
    res = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    items = res.get("items", [])
    if not items:
        return None
    ch = items[0]
    thumbs = ch["snippet"]["thumbnails"]
    thumb_url = thumbs.get("medium", thumbs.get("default", {})).get("url", "")
    data = {
        "id":              ch["id"],
        "name":            ch["snippet"]["title"],
        "thumbnail":       thumb_url,
        "subscriberCount": int(ch["statistics"].get("subscriberCount", 0)),
        "viewCount":       int(ch["statistics"].get("viewCount", 0)),
        "videoCount":      int(ch["statistics"].get("videoCount", 0)),
        "url":             f"https://youtube.com/channel/{ch['id']}",
    }
    _channel_cache["data"] = data
    _channel_cache["at"] = now
    return data


def _get_videos(max_results=12):
    now = datetime.now()
    if _videos_cache.get("data") and (now - _videos_cache["at"]).total_seconds() < 300:
        return _videos_cache["data"]
    youtube = get_youtube_client()
    ch_res = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads_id = ch_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl_res = youtube.playlistItems().list(
        part="snippet,contentDetails", playlistId=uploads_id, maxResults=max_results
    ).execute()
    items = pl_res.get("items", [])
    if not items:
        return []
    video_ids = [i["contentDetails"]["videoId"] for i in items]
    v_res = youtube.videos().list(part="snippet,statistics", id=",".join(video_ids)).execute()
    videos = []
    for v in v_res.get("items", []):
        thumbs = v["snippet"]["thumbnails"]
        thumb = thumbs.get("medium", thumbs.get("default", {})).get("url", "")
        videos.append({
            "id":          v["id"],
            "title":       v["snippet"]["title"],
            "publishedAt": v["snippet"]["publishedAt"],
            "thumbnail":   thumb,
            "viewCount":   int(v["statistics"].get("viewCount", 0)),
            "likeCount":   int(v["statistics"].get("likeCount", 0)),
            "url":         f"https://youtube.com/shorts/{v['id']}",
        })
    _videos_cache["data"] = videos
    _videos_cache["at"] = now
    return videos


# ─── Analytics Helper ─────────────────────────────────────────────────────────
def _read_analytics(limit=30) -> list:
    if not os.path.exists(ANALYTICS_FILE):
        return []
    entries = []
    with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries[-limit:]


# ─── API Routes ───────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/channels")
def api_channels_list():
    """Bağlı kanalları döner."""
    return jsonify(load_channels())


@app.get("/api/channels/connect/status")
def api_channels_connect_status():
    """OAuth akışının durumunu döner."""
    with _connect_lock:
        return jsonify(dict(_connect_state))


@app.post("/api/channels/connect")
def api_channels_connect():
    """OAuth akışını başlatır. Zaten pending ise 409 döner."""
    with _connect_lock:
        if _connect_state["status"] == "pending":
            return jsonify({"ok": False, "message": "OAuth zaten devam ediyor"}), 409
        # idle/done/error → pending (reset + set atomically under lock)
        _connect_state.clear()
        _connect_state.update({"status": "pending"})

    t = threading.Thread(target=_oauth_connect_worker, daemon=False)
    t.start()
    return jsonify({"ok": True, "message": "OAuth başlatıldı, tarayıcı açılıyor..."})


@app.delete("/api/channels/<channel_id>")
def api_channels_delete(channel_id):
    """Kanalı sil. Pipeline çalışıyorsa 409 döner."""
    with pipeline_lock:
        if pipeline_state["running"]:
            return jsonify({"ok": False, "message": "Pipeline çalışıyor, önce bekleyin"}), 409
    remove_channel(channel_id)
    nullify_channel_in_schedules(channel_id, SCHEDULES_FILE)
    return jsonify({"ok": True})


@app.get("/api/channel")
def api_channel():
    try:
        return jsonify(_get_channel())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/videos")
def api_videos():
    try:
        return jsonify(_get_videos())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/status")
def api_status():
    now = datetime.now()
    next_run_dt    = None
    next_run_label = None

    with _schedules_lock:
        for s in _schedules:
            if not s.get("enabled"):
                continue
            s_time = s.get("time", "")
            s_date = s.get("date")
            try:
                h, m = map(int, s_time.split(":"))
            except Exception:
                continue
            if s_date:
                try:
                    run_dt = datetime.strptime(f"{s_date} {s_time}", "%Y-%m-%d %H:%M")
                    if run_dt > now:
                        if next_run_dt is None or run_dt < next_run_dt:
                            next_run_dt    = run_dt
                            next_run_label = s.get("label") or s["id"][:8]
                except Exception:
                    pass
            else:
                run_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if run_dt <= now:
                    run_dt += timedelta(days=1)
                if next_run_dt is None or run_dt < next_run_dt:
                    next_run_dt    = run_dt
                    next_run_label = s.get("label") or s["id"][:8]

    if next_run_dt:
        seconds_left   = int((next_run_dt - now).total_seconds())
        next_time_str  = next_run_dt.strftime("%H:%M")
        next_date_str  = next_run_dt.strftime("%Y-%m-%d")
    else:
        seconds_left   = 0
        next_time_str  = "--:--"
        next_date_str  = None
        next_run_label = None

    with pipeline_lock:
        ps = dict(pipeline_state)
    with _preview_lock:
        _pv_content = _preview_state.get("content") or {}
        pv = {
            "status":          _preview_state["status"],
            "video_filename":  _preview_state["video_filename"],
            "error":           _preview_state["error"],
            "title":           _pv_content.get("title", ""),
            "primary_keyword": _pv_content.get("primary_keyword", ""),
            "youtube_title":   _pv_content.get("youtube_title", ""),
            "hook":            _pv_content.get("hook", ""),
            "seo_description": _pv_content.get("seo_description", ""),
            "hashtags":        _pv_content.get("hashtags", []),
        }
    return jsonify({
        "pipeline":  ps,
        "preview":   pv,
        "scheduler": {"running": scheduler_running},
        "nextRun": {
            "time":        next_time_str,
            "date":        next_date_str,
            "label":       next_run_label,
            "secondsLeft": seconds_left,
        },
    })


@app.get("/api/schedules")
def api_schedules_list():
    with _schedules_lock:
        return jsonify(list(_schedules))


@app.post("/api/schedules")
def api_schedules_add():
    body  = request.get_json(silent=True) or {}
    time_str = (body.get("time") or "").strip()
    date_str = (body.get("date") or "").strip() or None
    topic    = (body.get("topic") or "").strip()
    label    = (body.get("label") or "").strip()

    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return jsonify({"ok": False, "message": "Geçersiz saat formatı (HH:MM)"}), 400
    if date_str:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({"ok": False, "message": "Geçersiz tarih formatı (YYYY-MM-DD)"}), 400

    save_id = (body.get("save_id") or "").strip() or None

    with _schedules_lock:
        idx = len(_schedules) + 1
        new_s = {
            "id":             str(uuid.uuid4()),
            "label":          label or f"Plan {idx}",
            "time":           time_str,
            "date":           date_str,
            "topic":          topic,
            "save_id":        save_id,
            "enabled":        True,
            "last_triggered": None,
            "created_at":     datetime.now().isoformat(),
        }
        _schedules.append(new_s)
        _save_schedules()
    return jsonify({"ok": True, "schedule": new_s}), 201


@app.delete("/api/schedules/<schedule_id>")
def api_schedules_delete(schedule_id):
    with _schedules_lock:
        idx = next((i for i, s in enumerate(_schedules) if s["id"] == schedule_id), None)
        if idx is None:
            return jsonify({"ok": False, "message": "Plan bulunamadı"}), 404
        _schedules.pop(idx)
        _save_schedules()
    return jsonify({"ok": True})


@app.patch("/api/schedules/<schedule_id>")
def api_schedules_toggle(schedule_id):
    body = request.get_json(silent=True) or {}
    with _schedules_lock:
        s = next((s for s in _schedules if s["id"] == schedule_id), None)
        if not s:
            return jsonify({"ok": False, "message": "Plan bulunamadı"}), 404
        if "channel_id" in body:
            s["channel_id"] = body["channel_id"] or None
        else:
            s["enabled"] = not s.get("enabled", True)
        _save_schedules()
    return jsonify({"ok": True, "enabled": s.get("enabled"), "channel_id": s.get("channel_id")})


@app.put("/api/schedules/<schedule_id>")
def api_schedules_update(schedule_id):
    body     = request.get_json(silent=True) or {}
    time_str = (body.get("time") or "").strip()
    date_str = (body.get("date") or "").strip() or None
    topic    = (body.get("topic") or "").strip()
    label    = (body.get("label") or "").strip()
    save_id  = (body.get("save_id") or "").strip() or None

    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return jsonify({"ok": False, "message": "Geçersiz saat formatı"}), 400
    if date_str:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({"ok": False, "message": "Geçersiz tarih formatı"}), 400

    with _schedules_lock:
        s = next((s for s in _schedules if s["id"] == schedule_id), None)
        if not s:
            return jsonify({"ok": False, "message": "Plan bulunamadı"}), 404
        s["time"]    = time_str
        s["date"]    = date_str
        s["topic"]   = topic
        s["label"]   = label or s["label"]
        s["save_id"] = save_id
        s["last_triggered"] = None  # saat değişti, sıfırla
        _save_schedules()
    return jsonify({"ok": True, "schedule": s})


@app.get("/api/saves")
def api_saves_list():
    if not os.path.exists(SAVES_FILE):
        return jsonify([])
    try:
        with open(SAVES_FILE, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify([])


@app.post("/api/saves")
def api_saves_add():
    body = request.get_json(silent=True) or {}
    saves = []
    if os.path.exists(SAVES_FILE):
        try:
            with open(SAVES_FILE, "r", encoding="utf-8") as f:
                saves = json.load(f)
        except Exception:
            saves = []
    entry = {
        "id":         str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(),
        "label":      (body.get("label") or "").strip() or None,
        "topic":      (body.get("topic") or "").strip(),
        "content":    body.get("content") or {},
        "settings":   body.get("settings") or {},
    }
    saves.append(entry)
    with open(SAVES_FILE, "w", encoding="utf-8") as f:
        json.dump(saves, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "save": entry}), 201


@app.delete("/api/saves/<save_id>")
def api_saves_delete(save_id):
    if not os.path.exists(SAVES_FILE):
        return jsonify({"ok": False, "message": "Kayıt bulunamadı"}), 404
    with open(SAVES_FILE, "r", encoding="utf-8") as f:
        saves = json.load(f)
    saves = [s for s in saves if s["id"] != save_id]
    with open(SAVES_FILE, "w", encoding="utf-8") as f:
        json.dump(saves, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})


@app.post("/api/saves/<save_id>/publish")
def api_saves_publish(save_id):
    if not os.path.exists(SAVES_FILE):
        return jsonify({"ok": False, "message": "Kayıt bulunamadı"}), 404
    with open(SAVES_FILE, "r", encoding="utf-8") as f:
        saves = json.load(f)
    entry = next((s for s in saves if s["id"] == save_id), None)
    if not entry:
        return jsonify({"ok": False, "message": "Kayıt bulunamadı"}), 404
    settings = entry.get("settings") or {}
    body = request.get_json(silent=True) or {}
    channel_id = body.get("channel_id") or None
    ok, msg = start_pipeline_async(
        topic=entry.get("topic", ""),
        content_override=entry.get("content") or None,
        privacy=settings.get("privacy"),
        category_id=settings.get("category_id"),
        publish_at=settings.get("publish_at"),
        channel_id=channel_id,
    )
    return jsonify({"ok": ok, "message": msg}), (202 if ok else 409)


@app.post("/api/draft")
def api_draft():
    body  = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    try:
        content = generate_content(topic=topic)
        return jsonify({"ok": True, "content": content})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.post("/api/generate")
def api_generate():
    body             = request.get_json(silent=True) or {}
    topic            = (body.get("topic") or "").strip()
    content_override = body.get("content") or None
    privacy          = body.get("privacy")   or None
    category_id      = body.get("category_id") or None
    publish_at       = body.get("publish_at")  or None
    channel_id       = body.get("channel_id")  or None
    ok, msg = start_pipeline_async(
        topic=topic, content_override=content_override,
        privacy=privacy, category_id=category_id, publish_at=publish_at,
        channel_id=channel_id,
    )
    return jsonify({"ok": ok, "message": msg}), (202 if ok else 409)


@app.post("/api/scheduler/start")
def api_scheduler_start():
    ok, msg = start_scheduler()
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 409)


@app.post("/api/scheduler/stop")
def api_scheduler_stop():
    ok, msg = stop_scheduler()
    return jsonify({"ok": ok, "message": msg})


@app.get("/thumbnail/<path:filename>")
def serve_thumbnail(filename):
    """output/ klasöründeki thumbnail dosyasını servis eder."""
    thumb_path = os.path.join(BASE_DIR, "output", filename)
    if not os.path.exists(thumb_path) or not filename.endswith(".jpg"):
        return "", 404
    return send_file(thumb_path, mimetype="image/jpeg")


@app.get("/output/<path:filename>")
def serve_output(filename):
    """output/ klasöründeki video dosyasını servis eder."""
    file_path = os.path.join(BASE_DIR, "output", filename)
    if not os.path.exists(file_path) or not filename.endswith(".mp4"):
        return "", 404
    return send_file(file_path, mimetype="video/mp4", conditional=True)


# ─── Preview Endpoints ─────────────────────────────────────────────────────────
@app.post("/api/saves/<save_id>/preview")
def api_saves_preview(save_id):
    """Video oluşturur ama yüklemez. Kullanıcı izledikten sonra /api/preview/confirm ile yükler."""
    if not os.path.exists(SAVES_FILE):
        return jsonify({"ok": False, "message": "Kayıt bulunamadı"}), 404
    with open(SAVES_FILE, "r", encoding="utf-8") as f:
        saves = json.load(f)
    entry = next((s for s in saves if s["id"] == save_id), None)
    if not entry:
        return jsonify({"ok": False, "message": "Kayıt bulunamadı"}), 404
    settings = entry.get("settings") or {}
    ok, msg = start_preview_async(
        topic=entry.get("topic", ""),
        content_override=entry.get("content") or None,
        privacy=settings.get("privacy"),
        category_id=settings.get("category_id"),
        publish_at=settings.get("publish_at"),
    )
    return jsonify({"ok": ok, "message": msg}), (202 if ok else 409)


@app.post("/api/preview/cancel")
def api_preview_cancel():
    """Önizleme onayından vazgeçildi — state sıfırla."""
    with _preview_lock:
        _preview_state["status"]         = "idle"
        _preview_state["video_filename"] = None
        _preview_state["content"]        = None
    return jsonify({"ok": True})


@app.get("/api/preview/status")
def api_preview_status():
    """Önizleme durumunu ve hazır olunca video dosya adını döner."""
    with _preview_lock:
        return jsonify({
            "status":         _preview_state["status"],
            "video_filename": _preview_state["video_filename"],
            "error":          _preview_state["error"],
        })


@app.post("/api/preview/confirm")
def api_preview_confirm():
    """Kullanıcı onayladı — önceden oluşturulan videoyu YouTube'a yükler."""
    body = request.get_json(silent=True) or {}
    with _preview_lock:
        if _preview_state["status"] != "ready":
            return jsonify({"ok": False, "message": "Önizleme hazır değil"}), 409
        _preview_state["channel_id"] = body.get("channel_id") or None
        video_filename = _preview_state["video_filename"]
        srt_path       = _preview_state["srt_path"]
        thumbnail_path = _preview_state["thumbnail_path"]
        content        = dict(_preview_state["content"])
        privacy        = _preview_state["privacy"]
        category_id    = _preview_state["category_id"]
        publish_at     = _preview_state["publish_at"]
        channel_id     = _preview_state.get("channel_id")
        # Sıfırla — tekrar onaylanmasın
        _preview_state["status"] = "idle"

    video_path = os.path.join(BASE_DIR, "output", video_filename)
    if not os.path.exists(video_path):
        return jsonify({"ok": False, "message": "Video dosyası bulunamadı"}), 404

    def _do_upload():
        with pipeline_lock:
            pipeline_state["running"] = True
        try:
            print(f"\n{'─'*50}")
            print(f"📤 Onaylanan video yükleniyor: {video_filename}")
            video_id = upload_video(
                video_path, content,
                srt_path=srt_path, thumbnail_path=thumbnail_path,
                privacy=privacy, category_id=category_id, publish_at=publish_at,
                channel_id=channel_id,
            )
            with pipeline_lock:
                pipeline_state["last_run"]      = datetime.now().isoformat()
                pipeline_state["last_status"]   = "success"
                pipeline_state["last_video_id"] = video_id
                pipeline_state["last_title"]    = content.get("title", "")
            print(f"🎉 TAMAMLANDI! → https://youtube.com/shorts/{video_id}")
            print(f"{'─'*50}\n")
            _videos_cache.clear()
        except Exception as e:
            print(f"❌ Yükleme hatası: {e}")
            with pipeline_lock:
                pipeline_state["last_run"]    = datetime.now().isoformat()
                pipeline_state["last_status"] = "error"
        finally:
            with pipeline_lock:
                pipeline_state["running"] = False

    with pipeline_lock:
        if pipeline_state["running"]:
            return jsonify({"ok": False, "message": "Pipeline zaten çalışıyor"}), 409

    threading.Thread(target=_do_upload, daemon=True).start()
    return jsonify({"ok": True, "message": "Yükleme başlatıldı"})


@app.post("/api/preview/start")
def api_preview_start():
    """İçerik verisiyle doğrudan video önizlemesi başlatır (saves gerektirmez)."""
    body             = request.get_json(silent=True) or {}
    topic            = (body.get("topic") or "").strip()
    content          = body.get("content") or None
    privacy          = body.get("privacy") or None
    category_id      = body.get("category_id") or None
    publish_at       = body.get("publish_at") or None
    section_overrides = body.get("section_overrides") or {}

    # Apply section_overrides to content if provided
    if section_overrides and content:
        # Update video_keywords from section keyword overrides
        if "video_keywords" not in content:
            content["video_keywords"] = {}
        for sec_key, sec_data in section_overrides.items():
            if isinstance(sec_data, dict):
                kw = sec_data.get("keyword")
                if kw:
                    content["video_keywords"][sec_key] = kw
                dur = sec_data.get("duration")
                if dur is not None:
                    # Store custom durations so generate_video can use them
                    if "_section_durations" not in content:
                        content["_section_durations"] = {}
                    content["_section_durations"][sec_key] = dur

    ok, msg = start_preview_async(
        topic=topic, content_override=content,
        privacy=privacy, category_id=category_id, publish_at=publish_at,
    )
    return jsonify({"ok": ok, "message": msg}), (202 if ok else 409)


@app.post("/api/preview/regenerate")
def api_preview_regenerate():
    """Mevcut videoyu sil, aynı parametrelerle yeni pipeline başlat."""
    with _preview_lock:
        old_fn      = _preview_state.get("video_filename")
        topic       = _preview_state.get("topic") or ""
        privacy     = _preview_state.get("privacy")
        category_id = _preview_state.get("category_id")
        publish_at  = _preview_state.get("publish_at")
        _preview_state["status"]         = "idle"
        _preview_state["video_filename"] = None
        _preview_state["content"]        = None
        _preview_state["error"]          = None

    if old_fn:
        old_path = os.path.join(BASE_DIR, "output", old_fn)
        try:
            if os.path.exists(old_path):
                os.remove(old_path)
                print(f"🗑️  Eski video silindi: {old_fn}")
        except Exception as e:
            print(f"⚠️  Video silinemedi: {e}")

    ok, msg = start_pipeline_async(topic=topic, privacy=privacy,
                                   category_id=category_id, publish_at=publish_at)
    return jsonify({"ok": ok, "message": msg}), (202 if ok else 409)


@app.get("/api/analytics")
def api_analytics():
    entries = _read_analytics(30)
    total      = len(entries)
    success    = sum(1 for e in entries if e.get("status") == "success")
    failed     = sum(1 for e in entries if e.get("status") != "success")
    return jsonify({
        "entries": list(reversed(entries)),
        "summary": {"total": total, "success": success, "failed": failed},
    })


# ─── Settings API ─────────────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    """Returns all settings. API keys are masked for security."""
    import copy
    s = copy.deepcopy(sm_module.load())

    def mask(d, path):
        keys = path.split(".")
        obj = d
        for k in keys[:-1]:
            obj = obj.get(k, {})
        if keys[-1] in obj and obj[keys[-1]]:
            val = str(obj[keys[-1]])
            obj[keys[-1]] = val[:6] + "…" + val[-4:] if len(val) > 12 else "***"

    # Mask API keys in GET response
    for path in ["content.api_key", "tts.api_key", "stock_video.pexels_api_key", "stock_video.pixabay_api_key"]:
        mask(s, path)

    return jsonify(s)


@app.route("/api/settings", methods=["POST"])
def api_settings_save():
    """Save settings. Receives full or partial settings object."""
    data = request.get_json(force=True) or {}
    try:
        sm_module.save(data)
        sm_module.reload()
        # Reload config module to pick up new values
        import importlib
        import config
        importlib.reload(config)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/settings/raw", methods=["GET"])
def api_settings_raw():
    """Returns settings with unmasked API keys (for editing in UI)."""
    return jsonify(sm_module.load())


@app.route("/api/settings/test-provider", methods=["POST"])
def api_test_provider():
    """Test a provider connection."""
    data = request.get_json(force=True) or {}
    provider_type = data.get("type")  # "content", "tts", "stock"

    try:
        if provider_type == "content":
            from providers.content import get_provider
            p = get_provider()
            result = p.generate("Say: {\"test\": \"ok\"}", "Return only valid JSON: {\"test\": \"ok\"}", 50)
            return jsonify({"ok": True, "message": "Content provider connected successfully"})

        elif provider_type == "tts":
            from providers.tts import get_provider
            p = get_provider()
            result = p.synthesize("Test")
            if result is None:
                return jsonify({"ok": False, "message": "TTS is disabled or returned no audio"})
            clip, dur, path = result
            import os as _os
            try: _os.unlink(path)
            except: pass
            return jsonify({"ok": True, "message": f"TTS connected ({dur:.1f}s audio generated)"})

        elif provider_type == "stock":
            from providers.stock import get_provider
            p = get_provider()
            frame = p.get_frame("nature landscape") if hasattr(p, "get_frame") else None
            if frame:
                return jsonify({"ok": True, "message": "Stock video provider connected successfully"})
            else:
                return jsonify({"ok": False, "message": "Provider returned no frame (check API key)"})

        else:
            return jsonify({"ok": False, "message": f"Unknown provider type: {provider_type}"}), 400

    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/stock/preview")
def api_stock_preview():
    """Returns a base64 JPEG preview frame for a keyword."""
    import base64
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"ok": False}), 400

    try:
        from stock_video import get_frame_jpeg
        frame = get_frame_jpeg(keyword)
        if not frame:
            return jsonify({"ok": False, "message": "No frame available"}), 404
        b64 = base64.b64encode(frame).decode()
        return jsonify({"ok": True, "data": f"data:image/jpeg;base64,{b64}"})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.get("/api/logs/history")
def api_logs_history():
    with _log_lock:
        return jsonify(list(log_history[-200:]))


@app.get("/api/logs/stream")
def api_logs_stream():
    def _gen():
        # İlk yüklemede son 50 log gönder
        with _log_lock:
            recent = list(log_history[-50:])
        for entry in recent:
            yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
        # Yeni logları stream et
        while True:
            try:
                entry = log_queue.get(timeout=20)
                yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield ": ping\n\n"

    return Response(
        stream_with_context(_gen()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _load_schedules()
    start_scheduler()
    print("🌐 Dashboard: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True, use_reloader=False)
