# 🎬 Video Automation System

Günde 1 kez otomatik olarak:
1. Claude API ile içerik üretir
2. Siyah arka plan + beyaz metin + fon müziği ile Shorts videosu oluşturur
3. YouTube kanalına yükler ve yayınlar

---

## 📁 Dosya Yapısı

```
youtube-automation/
├── README.md
├── .env                  ← API anahtarların buraya
├── requirements.txt
├── config.py             ← Ayarlar
├── generate_content.py   ← Claude API → bilgi üretimi
├── generate_video.py     ← Video oluşturma (MoviePy)
├── upload_youtube.py     ← YouTube'a yükleme
├── scheduler.py          ← Günlük zamanlayıcı
├── main.py               ← Tek komutla çalıştır
├── music/                ← Fon müziklerini buraya koy (.mp3)
│   └── README_MUSIC.txt
└── output/               ← Üretilen videolar burada birikir
```

---

## ⚙️ Kurulum (Adım Adım)

### 1. Python Bağımlılıkları

```bash
pip install anthropic moviepy google-auth google-auth-oauthlib google-api-python-client schedule pillow numpy
```

> MoviePy için FFmpeg gerekli:
> - **Windows:** https://ffmpeg.org/download.html → PATH'e ekle
> - **Mac:** `brew install ffmpeg`
> - **Linux:** `sudo apt install ffmpeg`

---

### 2. Claude API Anahtarı

- https://console.anthropic.com adresine git
- API Keys → Create Key
- `.env` dosyasına yapıştır

---

### 3. YouTube API Kurulumu

1. https://console.cloud.google.com adresine git
2. Yeni proje oluştur → "YouTube Shorts Bot" gibi bir isim ver
3. **APIs & Services → Enable APIs** → "YouTube Data API v3" aktif et
4. **OAuth 2.0 Credentials** oluştur:
   - Application type: **Desktop App**
   - İndir → `client_secrets.json` olarak kaydet → proje klasörüne koy
5. **OAuth Consent Screen** ayarla:
   - User Type: External
   - Kendi Gmail'ini test kullanıcısı olarak ekle

---

### 4. .env Dosyası

```env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

---

### 5. Fon Müziği Ekle

`music/` klasörüne **telif hakkı olmayan** `.mp3` dosyaları ekle.

Ücretsiz müzik kaynakları:
- https://pixabay.com/music (ambient/space kategorisi)
- https://freemusicarchive.org
- YouTube Audio Library (Studio → Audio Library)

---

## 🚀 Çalıştırma

### Tek seferlik test:
```bash
python main.py --once
```

### Günlük otomatik (her gün saat 10:00):
```bash
python scheduler.py
```

### Arka planda çalıştır (Windows):
```bash
pythonw scheduler.py
```

### Arka planda çalıştır (Mac/Linux):
```bash
nohup python scheduler.py &
```

---

## 🔐 İlk Çalıştırmada

YouTube OAuth için tarayıcı açılacak → Google hesabınla giriş yap → İzin ver.
Bu işlem sadece bir kez yapılır. Token otomatik kaydedilir.

---

## 📊 Video Özellikleri

| Özellik | Değer |
|---------|-------|
| Çözünürlük | 1080x1920 (Shorts formatı) |
| Süre | ~45-60 saniye |
| Format | MP4 (H.264) |
| Arka plan | Siyah |
| Metin | Beyaz, animasyonlu |
| Müzik | Rastgele seçim (music/ klasöründen) |

---

## ❓ Sorun Giderme

**"FFmpeg not found"** → FFmpeg'i kur ve PATH'e ekle

**"quota exceeded"** → YouTube API günlük kotası (10.000 unit). Günde 1 video yeterlidir.

**"OAuth Error"** → client_secrets.json doğru klasörde mi kontrol et
