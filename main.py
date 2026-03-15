"""
main.py
Pipeline v2 — 4 adımlı, analytics loglu, renkli terminal çıktılı.
systemdirections.md §5 kurallarını uygular.
"""

import json
import sys
import time
from datetime import datetime

from config import ANALYTICS_FILE
from generate_content import generate_content
from generate_video import generate_video
from upload_youtube import upload_video

# ─── ANSI Renk Kodları (§5.2) ─────────────────────────────────────────────────
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

WIDTH  = 52

def banner(text: str):
    print(f"\n{CYAN}╔{'═'*WIDTH}╗")
    pad = WIDTH - len(text)
    print(f"║  {BOLD}{text}{RESET}{CYAN}{' '*pad}║")
    print(f"╚{'═'*WIDTH}╝{RESET}")

def step(n: int, total: int, text: str):
    print(f"\n  {CYAN}▶  Adım {n}/{total}  {text}{RESET}")

def ok(label: str, value: str):
    print(f"     {GREEN}✓{RESET} {DIM}{label:<10}{RESET} {value}")

def warn(text: str):
    print(f"     {YELLOW}⚠  {text}{RESET}")

def err(text: str):
    print(f"     {RED}✗  {text}{RESET}")


# ─── Analytics Kayıt ──────────────────────────────────────────────────────────
def write_analytics(entry: dict):
    try:
        with open(ANALYTICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        warn(f"Analytics yazılamadı: {e}")


# ─── Pipeline ─────────────────────────────────────────────────────────────────
def run_pipeline(topic: str = "") -> bool:
    start_total = time.time()
    now = datetime.now()

    banner("🎬  VIDEO AUTOMATION SYSTEM  —  Pipeline v2")
    print(f"\n  {DIM}{now.strftime('%Y-%m-%d  %H:%M:%S')}{RESET}")

    content    = None
    video_path = None
    srt_path   = None
    video_id   = None

    try:
        # ── Adım 1: İçerik ────────────────────────────────────────────────────
        step(1, 4, "İçerik üretiliyor...")
        t0 = time.time()
        content = generate_content(topic=topic)
        ok("Konu",    content["title"])
        ok("Keyword", content.get("primary_keyword", "—"))
        ok("Hook",    content.get("hook", "—")[:50])
        ok("Süre",    f"{time.time()-t0:.1f} sn")

        # ── Adım 2: Video ─────────────────────────────────────────────────────
        step(2, 4, "Video oluşturuluyor...")
        t0 = time.time()
        video_path, srt_path, thumbnail_path = generate_video(content)
        ok("Süre",  f"{time.time()-t0:.1f} sn")
        ok("Video", video_path.split("\\")[-1])
        ok("SRT",   srt_path.split("\\")[-1])
        ok("Thumb", thumbnail_path.split("\\")[-1])

        # ── Adım 3: Kontrol listesi (§kontrol listesi) ────────────────────────
        step(3, 4, "Kontrol listesi...")
        checks = [
            (len(content.get("hook", "").split()) <= 12,               "hook ≤ 12 kelime"),
            (len(content.get("youtube_title", "")) <= 60,              "youtube_title ≤ 60 karakter"),
            ("#Shorts" in content.get("youtube_title", ""),            "#Shorts başlıkta"),
            (5 <= len(content.get("hashtags", [])) <= 7,               "hashtag sayısı 5-7"),
            (srt_path is not None and __import__("os").path.exists(srt_path), "SRT dosyası üretildi"),
            (thumbnail_path is not None and __import__("os").path.exists(thumbnail_path), "Thumbnail üretildi"),
        ]
        all_ok = True
        for passed, label in checks:
            if passed:
                ok("✓", label)
            else:
                warn(f"✗ {label}")
                all_ok = False

        # ── Adım 4: YouTube yükleme ───────────────────────────────────────────
        step(4, 4, "YouTube'a yükleniyor...")
        t0 = time.time()
        video_id = upload_video(video_path, content, srt_path=srt_path, thumbnail_path=thumbnail_path,
                                channel_id=None)
        ok("Video ID", video_id)
        ok("URL",      f"youtube.com/shorts/{video_id}")
        ok("Süre",     f"{time.time()-t0:.1f} sn")

        total_secs = time.time() - start_total

        # ── Tamamlandı ────────────────────────────────────────────────────────
        print(f"\n{GREEN}╔{'═'*WIDTH}╗")
        print(f"║  ✅  TAMAMLANDI{' '*(WIDTH-14)}║")
        print(f"║{' '*(WIDTH+2)}║")
        konu_line = f"Konu    : {content['title']}"[:WIDTH-2]
        url_line  = f"URL     : youtube.com/shorts/{video_id}"[:WIDTH-2]
        sure_line = f"Toplam  : {total_secs:.1f} saniye"[:WIDTH-2]
        print(f"║  {konu_line}{' '*(WIDTH-len(konu_line))}║")
        print(f"║  {url_line}{' '*(WIDTH-len(url_line))}║")
        print(f"║  {sure_line}{' '*(WIDTH-len(sure_line))}║")
        print(f"╚{'═'*WIDTH}╝{RESET}\n")

        # Analytics
        write_analytics({
            "timestamp":       now.isoformat(),
            "title":           content["title"],
            "primary_keyword": content.get("primary_keyword", ""),
            "video_id":        video_id,
            "video_url":       f"https://youtube.com/shorts/{video_id}",
            "video_path":      video_path,
            "srt_path":        srt_path,
            "thumbnail_path":  thumbnail_path,
            "duration_sec":    round(total_secs, 1),
            "status":          "success",
        })

        return True

    except Exception as e:
        elapsed = time.time() - start_total
        print(f"\n{RED}╔{'═'*WIDTH}╗")
        print(f"║  ✗  HATA{' '*(WIDTH-8)}║")
        hata_line = str(e)[:WIDTH-2]
        print(f"║  {hata_line}{' '*(WIDTH-len(hata_line))}║")
        print(f"╚{'═'*WIDTH}╝{RESET}\n")

        write_analytics({
            "timestamp":  now.isoformat(),
            "title":      content["title"] if content else "",
            "video_path": video_path or "",
            "srt_path":   srt_path or "",
            "duration_sec": round(elapsed, 1),
            "status":     "failed",
            "error":      str(e),
        })
        return False


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    success = run_pipeline(topic=topic)
    sys.exit(0 if success else 1)
