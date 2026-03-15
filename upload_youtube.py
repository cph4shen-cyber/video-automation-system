"""
upload_youtube.py
Video + SRT altyazı yükler.
systemdirections.md §3 kurallarını uygular.
"""

import json
import os
import time

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import (
    ANALYTICS_FILE, SECRETS_FILE,
    YOUTUBE_CATEGORY_ID, YOUTUBE_PRIVACY, YOUTUBE_SCOPES,
)
from channels_manager import (
    get_first_channel_id, load_token, save_token,
)


def get_youtube_client(channel_id: str = None):
    """
    OAuth2 ile YouTube istemcisi döner.
    channel_id verilmezse ilk bağlı kanalı kullanır.
    """
    # channel_id belirle
    if channel_id is None:
        channel_id = get_first_channel_id()
    if channel_id is None:
        raise RuntimeError(
            "Hiç kanal bağlı değil. Dashboard > Settings > CHANNEL üzerinden kanal ekleyin."
        )

    creds = load_token(channel_id)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_token(channel_id, creds)   # refresh sonrası geri yaz
        else:
            if not os.path.exists(SECRETS_FILE):
                raise FileNotFoundError(
                    f"'{SECRETS_FILE}' bulunamadı! "
                    "Google Cloud Console'dan indirip klasöre koy."
                )
            flow  = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
            save_token(channel_id, creds)

    return build("youtube", "v3", credentials=creds)


def _write_analytics(entry: dict):
    """analytics.jsonl dosyasına kayıt ekler."""
    with open(ANALYTICS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def upload_video(video_path: str, content: dict, srt_path: str = None, thumbnail_path: str = None,
                 privacy: str = None, category_id: str = None, publish_at: str = None,
                 channel_id: str = None) -> str:
    """
    Videoyu YouTube'a yükler, ardından SRT altyazı ekler.
    Döndürür: video_id
    """
    youtube = get_youtube_client(channel_id)

    effective_privacy     = privacy     or YOUTUBE_PRIVACY
    effective_category_id = category_id or YOUTUBE_CATEGORY_ID

    # §3.1 — max 60 karakter başlık
    title = content.get("youtube_title", content.get("title", "Video"))[:60]

    # §1.3 — seo_description kullan
    description = content.get("seo_description", content.get("youtube_description", ""))
    hashtags    = content.get("hashtags", [])
    seo_tags    = content.get("seo_tags", [h.lstrip("#") for h in hashtags])

    # #Shorts kontrolü
    if "#Shorts" not in title:
        title = (title[:52] + " #Shorts") if len(title) > 52 else title + " #Shorts"

    # Anlatım metni — seslendirilen içeriği açıklamaya ekle
    narration_parts = [
        content.get("hook",    ""),
        content.get("fact",    ""),
        content.get("detail",  ""),
        content.get("closing", ""),
    ]
    narration = "\n\n".join(p for p in narration_parts if p)

    # Açıklama: SEO özeti + anlatım + hashtag — en fazla 5000 karakter
    full_desc = description.strip()
    if narration:
        full_desc = full_desc + "\n\n" + narration if full_desc else narration
    hashtag_line = " ".join(hashtags)
    if hashtag_line:
        full_desc = full_desc + "\n\n" + hashtag_line
    full_desc = full_desc[:4900]
    if "#Shorts" not in full_desc:
        full_desc += "\n#Shorts"

    status_block = {
        "privacyStatus":           "private" if publish_at else effective_privacy,
        "selfDeclaredMadeForKids": False,
    }
    if publish_at:
        # YouTube ISO-8601 formatı: "2026-03-15T10:00:00Z"
        status_block["publishAt"] = publish_at if publish_at.endswith("Z") else publish_at + ":00Z"

    body = {
        "snippet": {
            "title":           title,
            "description":     full_desc,
            "tags":            (seo_tags + ["shorts"])[:15],
            "categoryId":      effective_category_id,
            "defaultLanguage": "tr",
        },
        "status": status_block,
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,
    )

    print(f"  📤 Yükleniyor: {title}")

    # ── Video yükleme (2 deneme) ──────────────────────────────────────────────
    video_id = None
    for attempt in range(3):
        try:
            request  = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"     %{int(status.progress() * 100)}", end="\r")
            video_id = response["id"]
            print(f"  ✓ Video ID : {video_id}")
            break
        except Exception as e:
            if attempt < 2:
                print(f"  ⚠️  Yükleme hatası (deneme {attempt+1}/3): {e} — 5 sn bekleniyor...")
                time.sleep(5)
                # media nesnesini sıfırla
                media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024*5)
            else:
                _write_analytics({
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                    "title": content.get("title", ""),
                    "video_path": video_path,
                    "status": "upload_failed",
                    "error": str(e),
                })
                raise

    # ── Thumbnail yükleme ────────────────────────────────────────────────────
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
            ).execute()
            print(f"  ✓ Thumbnail: yüklendi")
        except Exception as e:
            print(f"  ⚠️  Thumbnail yüklenemedi: {e}")
    else:
        print(f"  ⚠️  Thumbnail dosyası bulunamadı — atlandı")

    # ── SRT altyazı yükleme (§3.2) ────────────────────────────────────────────
    if srt_path and os.path.exists(srt_path):
        try:
            youtube.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId":  video_id,
                        "language": "tr",
                        "name":     "Türkçe",
                        "isDraft":  False,
                    }
                },
                media_body=MediaFileUpload(srt_path, mimetype="text/plain"),
            ).execute()
            print(f"  ✓ Altyazı  : yüklendi")
        except Exception as e:
            print(f"  ⚠️  Altyazı yüklenemedi: {e}")
    else:
        print(f"  ⚠️  SRT dosyası bulunamadı — altyazısız yüklendi")

    return video_id
