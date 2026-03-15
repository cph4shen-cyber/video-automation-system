"""
scheduler.py
Her gün belirlenen saatte pipeline'ı çalıştırır.
Arka planda sürekli çalışır.
"""

import time
import logging
from datetime import datetime

import schedule

from config import UPLOAD_HOUR, UPLOAD_MINUTE
from main import run_pipeline


# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scheduler.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def job():
    log.info("⏰ Zamanlanmış görev başlatıldı.")
    success = run_pipeline()
    if success:
        log.info("✅ Görev başarıyla tamamlandı.")
    else:
        log.error("❌ Görev başarısız. Logları kontrol et.")


def main():
    run_time = f"{UPLOAD_HOUR:02d}:{UPLOAD_MINUTE:02d}"
    log.info(f"📅 Zamanlayıcı başlatıldı. Her gün {run_time}'de çalışacak.")
    log.info("   Durdurmak için: Ctrl+C")

    schedule.every().day.at(run_time).do(job)

    # İlk çalışmayı hemen yapmak istersen:
    # log.info("🔄 İlk çalışma hemen başlatılıyor...")
    # job()

    while True:
        schedule.run_pending()
        time.sleep(30)  # 30 saniyede bir kontrol


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("⛔ Zamanlayıcı durduruldu.")
