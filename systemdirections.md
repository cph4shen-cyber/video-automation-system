# 🤖 SİSTEM TALİMATLARI — Video Automation System
> Bu dosya, strateji raporundan çıkarılan tüm kritik kuralları
> sistemin her modülüne yönelik teknik direktifler olarak tanımlar.
> Her modül bu dosyayı kendi "davranış sözleşmesi" olarak kabul eder.

---

## 📦 MODÜL 1 — `generate_content.py`
### İçerik Üretim Kuralları

---

### 1.1 Başlık Formatı (KRİTİK)

Üretilen her `title` ve `youtube_title` aşağıdaki formatlardan **birini** kullanmak ZORUNDADIR:

| Format | Şablon | Örnek |
|---|---|---|
| **Soru** | "X neden var?" | "Zaman Neden Var?" |
| **Şok** | "X diye bir şey yok" | "Şu An Diye Bir Şey Yok" |
| **Rakam** | "%N aslında..." | "%99.9 Boşluk: Peki Sen Nesin?" |
| **Karşıtlık** | "X aslında Y" | "Beyin Karar Vermeden Önce Biliyor" |
| **Tamamlanmamış** | "X olmadan önce..." | "Evren Başlamadan Önce..." |

> ❌ **YASAK:** Düz ifade başlıklar. Örnek: "Zamanın Fiziksel Yapısı" → kabul edilmez.
> ✅ **DOĞRU:** "Zaman Gerçekten Akıyor mu?" → kabul edilir.

---

### 1.2 YouTube Başlığı (SEO Zorunluluğu)

`youtube_title` alanı için kesin kurallar:

```
[primary_keyword] [eylem/soru] | Channel Name #Shorts
```

- `primary_keyword` **ilk 1-3 kelimede** yer almalı
- Toplam uzunluk **maksimum 60 karakter** (YouTube kırpma sınırı)
- `#Shorts` etiketi başlığın **sonunda** yer almalı
- `|` ayracı ile bölümlenmiş yapı tercih edilmeli

**Geçerli örnekler:**
```
Zaman Neden Var? | Channel Name #Shorts     ✅ (38 karakter)
Kuantum Fiziği Bizi Sildi mi? | #Shorts     ✅ (42 karakter)
Bilinç Nedir? Beyin mi Üretiyor? #Shorts    ✅ (44 karakter)
```

**Geçersiz örnekler:**
```
Zamanın Fiziksel Yapısı ve Görelilik Teorisi Üzerine Bir İnceleme #Shorts   ❌ (çok uzun)
Channel Name #Shorts                                                         ❌ (anahtar kelime yok)
```

---

### 1.3 YouTube Açıklaması (SEO Zorunluluğu)

`seo_description` alanı şu şablonu takip etmeli:

```
[primary_keyword içeren güçlü cümle — arama önizlemesi bu olacak].
[Videonun içeriğini 1-2 cümle ile açıkla].

[hashtag_1] [hashtag_2] [hashtag_3] [hashtag_4] [hashtag_5] #Shorts

🤖 Bu video yapay zeka ile üretilmiştir.
```

> **Neden:** YouTube açıklamanın ilk cümlesini arama sonuçlarında önizleme olarak gösterir.
> `primary_keyword` bu cümlede geçmezse arama görünürlüğü düşer.

---

### 1.4 Hashtag Kompozisyonu

Her video için hashtag listesi şu dağılımı takip etmeli:

```python
hashtags = [
    "#[primary_keyword]",          # 1 adet — birincil anahtar kelime
    "#[niche_specific_1]",         # 1-2 adet — konuya özel
    "#[niche_specific_2]",
    "#[channel_hashtag]",          # sabit — kanal kimliği (settings'den)
    "#bilim",                      # sabit — geniş kitle
    "#felsefe",                    # sabit — geniş kitle
    "#Shorts",                     # zorunlu
]
```

> Toplam: **5-7 hashtag.** Daha fazlası spam olarak işaretlenebilir.

---

### 1.5 Konu Tekrar Önleme

- Son **15 kullanılan konu** `used_facts.txt`'ye kaydedilmeli
- Yeni üretimde bu başlıklar prompt'a "KULLANMA" listesi olarak eklenmeli
- Aynı `primary_keyword` **30 video içinde** tekrar edilmemeli

---

### 1.6 `hook` Alanı

`hook`, videonun ilk karesinde gösterilecek en kritik metindir.

Kurallar:
- Maksimum **12 kelime**
- Soru veya tamamlanmamış cümle formatında olmalı
- İzleyiciyi **"bekle ne?"** durumuna sokmalı
- `title`'dan **farklı** olmalı — kopyalama yasak

---

### 1.7 İçerik Derinliği

| Alan | Uzunluk | Amaç |
|---|---|---|
| `hook` | 1 cümle, max 12 kelime | İlk 3 saniyede durdurma |
| `title` | max 8 kelime | Konuyu netleştirme |
| `fact` | 2-3 cümle | Çarpıcı ana bilgi |
| `detail` | 2-3 cümle | Bir adım daha derine giden bağlam |
| `closing` | 1 cümle | İzleyiciyi düşündüren soru |

> `fact` ve `detail` birbirini tekrar etmemeli. `detail`, `fact`'in **devamı** olmalı.

---

## 📹 MODÜL 2 — `generate_video.py`
### Video Üretim Kuralları

---

### 2.1 Video Yapısı (Zorunlu Sıra)

Her video aşağıdaki 6 bölümde üretilmeli:

```
┌─────────────────────────────────────┐
│  1. HOOK          (3.5 sn)          │  ← büyük font, kanal adı üstte
│  2. BAŞLIK        (3.5 sn)          │  ← konuya yumuşak giriş
│  3. ANA BİLGİ    (7.0 sn)          │  ← çarpıcı gerçek
│  4. DETAY         (7.0 sn)          │  ← daha derin bağlam
│  5. KAPANIŞ       (4.0 sn)          │  ← düşündürücü soru, hashtag alt bilgi
│  6. CTA           (3.0 sn)          │  ← abone çağrısı, kanal adı
└─────────────────────────────────────┘
   TOPLAM ≈ 28 saniye (ideal Shorts uzunluğu)
```

> **Neden 28 saniye:** Watch-through rate için kritik. Çok kısa (< 15 sn) → düşük engagement.
> Çok uzun (> 45 sn) → swipe-away oranı artar.

---

### 2.2 Hook Frame (İlk Kare) — KRİTİK

İlk kare, kullanıcının scroll'da **durma kararını** verdiği andır.

Zorunlu özellikler:
- Font büyüklüğü: `FONT_SIZE_HOOK` (68px) — en büyük font
- Kanal adı (settings'den alınan handle) üst orta konumda, accent renkte
- Hook metni **ortalanmış**, dikey olarak ekranın ortasında
- Fade-in süresi: **0.3 saniye** (normal 0.5'ten hızlı — hemen dikkat çekmeli)

---

### 2.3 Metin Sarmalama (Readability)

| Font Büyüklüğü | Max Karakter/Satır | Neden |
|---|---|---|
| 68px (hook) | 18 karakter | Mobilde 3 saniyede okunabilmeli |
| 60px (başlık) | 22 karakter | Hızlı kavrama |
| 46px (body) | 28 karakter | Detay okuma için daha geniş |
| 32px (footer) | 40 karakter | Hashtag ve küçük bilgiler |

> Satır başına düşen kelime sayısı **3-5 arası** olmalı. Çok uzun satırlar mobilde okunmuyor.

---

### 2.4 Closed Caption / SRT (Zorunlu)

Her video için SRT dosyası üretilmeli. SRT olmadan yükleme **tamamlanmış sayılmaz.**

```
Neden zorunlu:
  - Sessiz izleyicilerin %40-60'ı altyazı olmadan geçiyor
  - YouTube metni indexleyerek SEO'ya katkı sağlıyor
  - Erişilebilirlik politikası algoritma güveni artırıyor
```

SRT segment yapısı her bölümü ayrı entry olarak içermeli:
```
1
00:00:00,000 --> 00:00:03,500
[hook metni]

2
00:00:03,500 --> 00:00:07,000
[başlık metni]
...
```

---

### 2.5 Müzik Yönetimi

- `music/` klasöründe **minimum 3 farklı parça** bulunmalı (çeşitlilik için)
- Müzik sesi: `MUSIC_VOLUME = 0.30` — metin sesinin önüne geçmemeli
- Müzik **CC0 veya Royalty-Free** olmak ZORUNDA (aksi halde video kaldırılır)
- Önerilen kaynaklar: Pixabay Music, YouTube Audio Library, Free Music Archive

---

### 2.6 Render Ayarları

```python
codec       = "libx264"    # YouTube uyumlu — değiştirme
audio_codec = "aac"        # YouTube uyumlu — değiştirme
fps         = 30           # Shorts standardı
resolution  = 1080x1920    # 9:16 Shorts formatı — değiştirme
```

> Bu değerler YouTube'un Shorts önerilen formatıyla birebir eşleşiyor. Değiştirme.

---

## 📤 MODÜL 3 — `upload_youtube.py`
### Yükleme Kuralları

---

### 3.1 Metadata Zorunlulukları

Her yüklemede şu alanların **tamamı dolu olmalı:**

| Alan | Kaynak | Neden |
|---|---|---|
| `title` | `youtube_title` (max 60 karakter) | SEO, arama görünürlüğü |
| `description` | `seo_description` | Arama önizlemesi + hashtag |
| `tags` | `seo_tags` (max 15 tag) | İlgili video önerisi |
| `categoryId` | `"27"` (Education) | Doğru kategori hedeflemesi |
| `defaultLanguage` | `"tr"` | Türkçe kitle hedeflemesi |
| `privacyStatus` | `"public"` | Yayınlanma |
| `selfDeclaredMadeForKids` | `False` | Yanlış işaretleme kısıtlama getirir |

---

### 3.2 SRT Yükleme (Zorunlu)

Video yüklendikten sonra SRT dosyası altyazı olarak eklenmeli:

```python
youtube.captions().insert(
    part="snippet",
    body={
        "snippet": {
            "videoId":      video_id,
            "language":     "tr",
            "name":         "Türkçe",
            "isDraft":      False,
        }
    },
    media_body=MediaFileUpload(srt_path, mimetype="text/plain")
)
```

> YouTube altyazıyı metinsel içerik olarak indexler → **SEO değeri yüksek.**

---

### 3.3 Günlük API Kotası

```
Günlük limit     : 10.000 unit
Video yükleme    : ~1.600 unit
SRT ekleme       : ~50 unit
Metadata güncell.: ~50 unit
─────────────────────────────
Günde 1 video    : ~1.700 unit   ✅ Güvenli
```

> Günde 1 videodan fazla yükleme kotayı tehdit eder. `scheduler.py` bunu enforce etmeli.

---

### 3.4 Hata Yönetimi

Yükleme başarısız olursa:
1. `analytics.jsonl`'ye `status: "upload_failed"` yaz
2. Video ve SRT dosyasını `output/` klasöründe **silme** — retry için sakla
3. Hata mesajını terminale açıkça bas
4. Scheduler bir sonraki günde tekrar dener

---

## ⏱️ MODÜL 4 — `scheduler.py`
### Zamanlama Kuralları

---

### 4.1 Yayın Saati Stratejisi

```
Varsayılan: Her gün 10:00 (lokal saat)

Neden 10:00:
  - Türkiye saat diliminde sabah erken aktivite yüksek
  - Algoritma ilk 1-2 saatte test eder; 10:00 başlangıç
    → öğle zirvesine (12:00-14:00) denk gelir
  - Akşam zirve saatleri (20:00-23:00) için gün içinde
    algoritmanın içeriği tanıması gerekir
```

---

### 4.2 Frekans Zorunluluğu

- **Günde 1 video** — ne daha az, ne daha fazla
- Günde 1'den az → algoritma kanalı "pasif" olarak işaretler
- Günde 1'den fazla → spam riski + API kotası aşımı
- En az **14 gün** kesintisiz yayın yapılmadan kanal otoritesi oluşmaz

---

### 4.3 Analytics Logu

Her başarılı çalışmada `analytics.jsonl`'ye şu kayıt eklenmeli:

```json
{
  "timestamp":     "2026-03-11T10:00:00",
  "title":         "Zaman Neden Var?",
  "primary_keyword": "zaman",
  "video_id":      "abc123xyz",
  "video_url":     "https://youtube.com/shorts/abc123xyz",
  "video_path":    "output/20260311_...",
  "srt_path":      "output/20260311_....srt",
  "duration_sec":  28.5,
  "status":        "success"
}
```

> Bu log ile hangi konuların ne kadar sıklıkta üretildiği takip edilebilir.

---

## 🖥️ MODÜL 5 — `main.py`
### Terminal Arayüzü Kuralları

---

### 5.1 Aşama Gösterimi

Her pipeline çalışmasında terminal çıktısı şu yapıyı takip etmeli:

```
╔══════════════════════════════════════════════════╗
║        🎬  VIDEO AUTOMATION SYSTEM  —  Pipeline v2  ║
╚══════════════════════════════════════════════════╝

  2026-03-11  10:00:00

  ▶  Adım 1/4  İçerik üretiliyor...
     ✓ Konu    : Zaman Neden Var?
     ✓ Keyword : zaman
     ✓ Süre    : 3.2 sn

  ▶  Adım 2/4  Video oluşturuluyor...
     ✓ Süre    : 47.8 sn
     ✓ Dosya   : output/20260311_Zaman_Neden_Var.mp4
     ✓ SRT     : output/20260311_Zaman_Neden_Var.srt

  ▶  Adım 3/4  Altyazı hazırlanıyor...
     ✓ 6 segment / 28.5 saniye

  ▶  Adım 4/4  YouTube'a yükleniyor...
     Yükleniyor... %100
     ✓ Video ID : abc123xyz

╔══════════════════════════════════════════════════╗
║  ✅  TAMAMLANDI                                   ║
║                                                  ║
║  Konu    : Zaman Neden Var?                      ║
║  URL     : youtube.com/shorts/abc123xyz          ║
║  Toplam  : 54.3 saniye                           ║
╚══════════════════════════════════════════════════╝
```

---

### 5.2 Renk Kodlaması (ANSI)

```python
CYAN   = "\033[96m"   # Başlık ve bölüm adları
GREEN  = "\033[92m"   # Başarı mesajları (✓)
YELLOW = "\033[93m"   # Uyarılar
RED    = "\033[91m"   # Hatalar (✗)
DIM    = "\033[2m"    # İkincil bilgi (süre, dosya yolu)
RESET  = "\033[0m"    # Sıfırlama
```

---

### 5.3 Retry Davranışı

```
İçerik üretimi başarısız → 5 sn bekle → tekrar dene (max 2)
Video render başarısız   → hata bas, dur (retry anlamsız)
YouTube yükleme başarısız → 5 sn bekle → tekrar dene (max 2)
```

---

## 🚫 GENEL YASAKLAR — Tüm Modüller

Bu kurallar hiçbir koşulda ihlal edilmez:

| Kural | Neden |
|---|---|
| Telif hakkı olan müzik kullanma | Video kaldırılır, gelir kesilir |
| `#Shorts` etiketini atlama | Shorts feed'e girmez |
| 60 karakteri aşan YouTube başlığı | YouTube kırpar, SEO değeri düşer |
| SRT olmadan yükleme | Watch-through rate düşer, sessiz izleyici kaybedilir |
| Günde 1'den fazla yükleme | API kotası aşımı + spam riski |
| `selfDeclaredMadeForKids: True` | Monetizasyon tamamen kapanır |
| Aynı konuyu 30 video içinde tekrar | İzleyici bağlılığı ve algoritma çeşitlilik skoru düşer |
| AI üretimi etiketini açıklamadan kaldırma | YouTube şeffaflık politikası ihlali |

---

## ✅ KONTROL LİSTESİ — Her Çalışmada

Sistem her pipeline sonunda şunları doğrulamalı:

```
[ ] hook metni 12 kelimeyi geçmiyor
[ ] youtube_title 60 karakteri geçmiyor
[ ] youtube_title #Shorts içeriyor
[ ] seo_description primary_keyword ile başlıyor
[ ] seo_description AI üretimi etiketi içeriyor
[ ] hashtag sayısı 5-7 arasında
[ ] SRT dosyası üretildi ve video ile aynı base name'e sahip
[ ] analytics.jsonl'ye kayıt eklendi
[ ] used_facts.txt güncellendi
[ ] video_id döndürüldü ve loglandı
```

---

*Son güncelleme: Mart 2026 — Strateji Raporundan türetilmiştir.*
*Bu dosya değiştirildiğinde tüm modüller güncellenen kurallara uyum sağlamalıdır.*
