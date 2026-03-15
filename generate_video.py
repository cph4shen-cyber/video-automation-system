"""
generate_video.py
6 bölümlü Shorts videosu + SRT altyazı dosyası üretir.
systemdirections.md §2 kurallarını uygular.
"""

import os
import random
import textwrap
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import AudioFileClip, VideoClip, concatenate_videoclips

from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    BACKGROUND_COLOR, TEXT_COLOR, ACCENT_COLOR,
    FONT_SIZE_HOOK, FONT_SIZE_TITLE, FONT_SIZE_BODY, FONT_SIZE_FOOTER,
    HOOK_DURATION, TITLE_DURATION, FACT_DURATION,
    DETAIL_DURATION, CLOSING_DURATION, CTA_DURATION,
    HOOK_FADE, NORMAL_FADE,
    MUSIC_VOLUME, MUSIC_DIR, OUTPUT_DIR,
    CHANNEL_HANDLE, CTA_TEXT,
    ELEVENLABS_API_KEY, TTS_VOLUME, MUSIC_VOLUME_TTS,
)
from generate_tts import generate_tts_segments, generate_tts_track
from stock_video import fetch_stock_clip


# ─── Font cache ────────────────────────────────────────────────────────────────
_font_cache: dict = {}

def get_font(size: int) -> ImageFont.FreeTypeFont:
    if size in _font_cache:
        return _font_cache[size]
    candidates = [
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            font = ImageFont.truetype(path, size)
            _font_cache[size] = font
            return font
    font = ImageFont.load_default()
    _font_cache[size] = font
    return font


# ─── Metin sarma (§2.3 karakter sınırları) ────────────────────────────────────
def wrap_text(text: str, font_size: int) -> list[str]:
    limits = {
        FONT_SIZE_HOOK:   18,
        FONT_SIZE_TITLE:  22,
        FONT_SIZE_BODY:   28,
        FONT_SIZE_FOOTER: 40,
    }
    max_chars = limits.get(font_size, 28)
    return textwrap.wrap(text, width=max_chars)


# ─── Frame çizimi ─────────────────────────────────────────────────────────────
def make_frame(
    lines: list[str],
    font_size: int,
    alpha: float = 1.0,
    header: str = None,          # Üst kısım (kanal adı)
    header_color: tuple = None,  # Üst metin rengi
    footer: str = None,          # Alt kısım (hashtag/cta)
) -> np.ndarray:
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    font      = get_font(font_size)
    hdr_font  = get_font(FONT_SIZE_FOOTER)
    ftr_font  = get_font(FONT_SIZE_FOOTER)

    # Üst başlık (kanal adı)
    if header:
        hdr_color = header_color or ACCENT_COLOR
        hdr_color = tuple(int(c * alpha) for c in hdr_color)
        bbox = draw.textbbox((0, 0), header, font=hdr_font)
        hx = (VIDEO_WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((hx, 80), header, font=hdr_font, fill=hdr_color)

    # Ana metin bloğu (dikey ortalanmış)
    line_h = font_size + 18
    total_h = len(lines) * line_h
    y_start = (VIDEO_HEIGHT - total_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (VIDEO_WIDTH - (bbox[2] - bbox[0])) // 2
        y = y_start + i * line_h
        color = tuple(int(c * alpha) for c in TEXT_COLOR)
        draw.text((x, y), line, font=font, fill=color)

    # Alt bilgi
    if footer:
        ftr_color = tuple(int(c * alpha * 0.6) for c in TEXT_COLOR)
        bbox = draw.textbbox((0, 0), footer, font=ftr_font)
        fx = (VIDEO_WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((fx, VIDEO_HEIGHT - 120), footer, font=ftr_font, fill=ftr_color)

    return np.array(img)


# ─── VideoClip üretici ────────────────────────────────────────────────────────
def make_clip(
    text: str,
    font_size: int,
    duration: float,
    fade: float = NORMAL_FADE,
    header: str = None,
    header_color: tuple = None,
    footer: str = None,
) -> VideoClip:
    lines = wrap_text(text, font_size)
    fps = VIDEO_FPS
    total_frames = int(duration * fps)
    fade_frames  = max(1, int(fade * fps))

    # Pre-compute tek frame (alpha=1.0) — fade için numpy multiply kullanılır
    base = make_frame(lines, font_size, alpha=1.0,
                      header=header, header_color=header_color, footer=footer)

    def frame_fn(t):
        i = min(int(t * fps), total_frames - 1)
        if i < fade_frames:
            a = i / fade_frames
        elif i > total_frames - fade_frames:
            a = (total_frames - i) / max(fade_frames, 1)
        else:
            return base  # Hızlı yol: klibin büyük çoğunluğu
        return (base * a).astype(np.uint8)

    return VideoClip(frame_fn, duration=duration).with_fps(fps)


# ─── SRT üretimi (§2.4) ──────────────────────────────────────────────────────
def ms(seconds: float) -> str:
    """Saniyeyi SRT zaman formatına çevirir: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms_ = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms_:03d}"


def generate_srt(sections: list[tuple[str, float, float]], output_path: str):
    """
    sections: [(text, start_sec, end_sec), ...]
    Her bölümü ayrı SRT entry olarak yazar.
    """
    lines = []
    for i, (text, start, end) in enumerate(sections, 1):
        lines.append(str(i))
        lines.append(f"{ms(start)} --> {ms(end)}")
        lines.append(text)
        lines.append("")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ─── Thumbnail Üretici ───────────────────────────────────────────────────────
def generate_thumbnail(content: dict, output_path: str) -> str:
    """
    1280x720 YouTube thumbnail üretir.
    Tasarım: koyu uzay gradyanı + büyük hook metni + kanal branding.
    """
    W, H = 1280, 720

    # ── Arka plan gradyanı (numpy — piksel döngüsünden ~200x hızlı) ────────
    t_vals = np.arange(H, dtype=np.float32) / H
    r_ch = np.clip(4  + t_vals * 2,  0, 255).astype(np.uint8)
    g_ch = np.clip(8  + t_vals * 4,  0, 255).astype(np.uint8)
    b_ch = np.clip(20 + (1 - t_vals) * 35, 0, 255).astype(np.uint8)
    arr  = np.zeros((H, W, 3), dtype=np.uint8)
    arr[:, :, 0] = r_ch[:, np.newaxis]
    arr[:, :, 1] = g_ch[:, np.newaxis]
    arr[:, :, 2] = b_ch[:, np.newaxis]
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # ── Glow çemberi (merkez) ──────────────────────────────────────────────
    for radius in range(260, 100, -20):
        alpha = int(18 * (1 - radius / 260))
        overlay = Image.new("RGB", (W, H), (0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.ellipse(
            [W//2 - radius, H//2 - radius, W//2 + radius, H//2 + radius],
            fill=(int(ACCENT_COLOR[0] * alpha / 255),
                  int(ACCENT_COLOR[1] * alpha / 255),
                  int(ACCENT_COLOR[2] * alpha / 255))
        )
        img = Image.blend(img, overlay, alpha=0.15)

    draw = ImageDraw.Draw(img)

    # ── Yıldızlar ──────────────────────────────────────────────────────────
    rng = random.Random(hash(content.get("title", "")) % (2**32))
    for _ in range(120):
        sx = rng.randint(0, W)
        sy = rng.randint(0, H)
        br = rng.randint(120, 220)
        sz = rng.choice([1, 1, 1, 2])
        draw.ellipse([sx, sy, sx+sz, sy+sz], fill=(br, br, br))

    # ── Hook metni (büyük, ortada) ─────────────────────────────────────────
    hook     = content.get("hook", content.get("title", ""))
    keyword  = content.get("primary_keyword", "")

    font_hook   = get_font(86)
    font_sub    = get_font(42)
    font_handle = get_font(34)

    hook_lines = textwrap.wrap(hook, width=20)

    line_h     = 96
    total_h    = len(hook_lines) * line_h
    y_start    = (H - total_h) // 2 - 30

    for i, line in enumerate(hook_lines):
        bbox = draw.textbbox((0, 0), line, font=font_hook)
        tw = bbox[2] - bbox[0]
        x  = (W - tw) // 2
        y  = y_start + i * line_h
        # Gölge
        draw.text((x+3, y+3), line, font=font_hook, fill=(0, 0, 0))
        draw.text((x, y), line, font=font_hook, fill=(255, 255, 255))

    # ── Primary keyword (accent renkte, hook'un altında) ──────────────────
    if keyword:
        kw_text = f"#{keyword}"
        bbox = draw.textbbox((0, 0), kw_text, font=font_sub)
        kw_w = bbox[2] - bbox[0]
        kw_y = y_start + total_h + 18
        draw.text(((W - kw_w)//2 + 2, kw_y + 2), kw_text, font=font_sub, fill=(0, 0, 0))
        draw.text(((W - kw_w)//2, kw_y), kw_text, font=font_sub,
                  fill=tuple(ACCENT_COLOR))

    # ── Kanal adı (alt orta) ───────────────────────────────────────────────
    handle = CHANNEL_HANDLE
    bbox   = draw.textbbox((0, 0), handle, font=font_handle)
    hx     = (W - (bbox[2] - bbox[0])) // 2
    draw.text((hx + 2, H - 62 + 2), handle, font=font_handle, fill=(0, 0, 0))
    draw.text((hx, H - 62), handle, font=font_handle, fill=tuple(ACCENT_COLOR))

    # ── Alt çizgi ─────────────────────────────────────────────────────────
    draw.rectangle([80, H - 72, W - 80, H - 70],
                   fill=(*ACCENT_COLOR, 180) if hasattr(draw, 'rectangle') else ACCENT_COLOR)

    img.save(output_path, "JPEG", quality=95)
    return output_path


# ─── Müzik ────────────────────────────────────────────────────────────────────
def get_random_music() -> str | None:
    if not os.path.exists(MUSIC_DIR):
        return None
    files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(".mp3")]
    if not files:
        print("  ⚠️  music/ klasöründe MP3 bulunamadı — müziksiz devam")
        return None
    return os.path.join(MUSIC_DIR, random.choice(files))


# ─── Ana Video Üretici ────────────────────────────────────────────────────────
def generate_video(content: dict) -> tuple[str, str, str]:
    """
    6 bölümlü video + SRT + thumbnail üretir.
    Döndürür: (video_path, srt_path, thumbnail_path)
    """
    hook    = content.get("hook",    content.get("title", ""))
    title   = content.get("title",   "")
    fact    = content.get("fact",    "")
    detail  = content.get("detail",  "")
    closing = content.get("closing", "")
    hashtag_str = " ".join(content.get("hashtags", [])[:4])

    # ── TTS: önce ses üret, gerçek sürelerle klip oluştur ────────────────────
    # Her segmentin sonuna eklenen sessizlik tamponu (sn)
    TTS_BUFFER = 0.45
    cta_text   = CTA_TEXT
    cta_spoken = f"{CHANNEL_HANDLE}'e abone olmayı unutma!"

    tts_segments = None
    tts_track    = None
    from moviepy import concatenate_audioclips, CompositeAudioClip

    if ELEVENLABS_API_KEY:
        tts_segments = generate_tts_segments([
            hook, title, fact, detail, closing, cta_spoken,
        ])

    if tts_segments:
        # Gerçek TTS süresi + tampon = klip süresi
        (d_hook, d_title, d_fact,
         d_detail, d_closing, d_cta) = [
            seg[1] + TTS_BUFFER for seg in tts_segments
        ]
        print(f"  ✓ TTS süreleri: hook={d_hook:.1f}s title={d_title:.1f}s "
              f"fact={d_fact:.1f}s detail={d_detail:.1f}s "
              f"closing={d_closing:.1f}s cta={d_cta:.1f}s")

        # TTS track'i kırpmadan birleştir (buffer = sessizlik ekle)
        tts_clips = []
        temp_files = [seg[2] for seg in tts_segments]
        for (audio_clip, actual_dur, _), clip_dur in zip(tts_segments, [
            d_hook, d_title, d_fact, d_detail, d_closing, d_cta
        ]):
            silence, sil_path = __import__("generate_tts")._silent_wav(clip_dur - actual_dur)
            temp_files.append(sil_path)
            tts_clips.append(concatenate_audioclips([audio_clip, silence]))

        tts_combined = concatenate_audioclips(tts_clips)
        tts_tmp = os.path.join(OUTPUT_DIR, "_tts_temp.wav")
        tts_combined.write_audiofile(tts_tmp, fps=44100, logger=None)
        tts_track = tts_tmp
        print(f"  ✓ TTS track yazıldı: {tts_combined.duration:.1f}s")

        # Geçici MP3 dosyalarını temizle
        for fp in temp_files:
            try:
                os.unlink(fp)
            except Exception:
                pass
    else:
        # TTS yoksa config'deki sabit süreler
        d_hook, d_title, d_fact, d_detail, d_closing, d_cta = (
            HOOK_DURATION, TITLE_DURATION, FACT_DURATION,
            DETAIL_DURATION, CLOSING_DURATION, CTA_DURATION,
        )

    # ── Stok video keyword'leri ───────────────────────────────────────────────
    vkw = content.get("video_keywords", {})

    def _bg(key: str, duration: float, font_size: int, fade: float = NORMAL_FADE):
        """Keyword için stok klip al; bulunamazsa siyah fallback."""
        keyword = vkw.get(key, "")
        clip = fetch_stock_clip(keyword, duration) if keyword else None
        return clip if clip is not None else make_clip("", font_size, duration, fade=fade)

    # ── Klipler (stok video arka planı, yoksa siyah) ──────────────────────────
    clip_hook    = _bg("hook",    d_hook,    FONT_SIZE_HOOK,  fade=HOOK_FADE)
    clip_title   = _bg("title",   d_title,   FONT_SIZE_TITLE)
    clip_fact    = _bg("fact",    d_fact,    FONT_SIZE_BODY)
    clip_detail  = _bg("detail",  d_detail,  FONT_SIZE_BODY)
    clip_closing = _bg("closing", d_closing, FONT_SIZE_BODY)
    clip_cta     = _bg("cta",     d_cta,     FONT_SIZE_TITLE)

    clips = [clip_hook, clip_title, clip_fact, clip_detail, clip_closing, clip_cta]
    final_video = concatenate_videoclips(clips, method="compose")
    dur = final_video.duration

    music_path = get_random_music()
    music_vol  = MUSIC_VOLUME_TTS if tts_track else MUSIC_VOLUME

    if music_path:
        music = AudioFileClip(music_path)
        if music.duration < dur:
            loops = int(dur / music.duration) + 1
            music = concatenate_audioclips([music] * loops)
        music = music.subclipped(0, dur).with_volume_scaled(music_vol)

        if tts_track:
            tts_audio = AudioFileClip(tts_track).with_volume_scaled(TTS_VOLUME)
            if tts_audio.duration > dur:
                tts_audio = tts_audio.subclipped(0, dur)
            mixed = CompositeAudioClip([music, tts_audio])
            final_video = final_video.with_audio(mixed)
        else:
            final_video = final_video.with_audio(music)
    elif tts_track:
        tts_audio = AudioFileClip(tts_track).with_volume_scaled(TTS_VOLUME)
        if tts_audio.duration > dur:
            tts_audio = tts_audio.subclipped(0, dur)
        final_video = final_video.with_audio(tts_audio)

    # ── Kaydet ───────────────────────────────────────────────────────────────
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in content["title"] if c.isalnum() or c in " _-")[:40].strip().replace(" ", "_")
    base_name  = f"{ts}_{safe_title}"
    video_path = os.path.join(OUTPUT_DIR, base_name + ".mp4")
    srt_path   = os.path.join(OUTPUT_DIR, base_name + ".srt")

    print(f"  🎬 Render: {base_name}.mp4")
    final_video.write_videofile(
        video_path,
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp_audio.m4a",
        remove_temp=True,
        logger=None,
    )

    # TTS geçici dosyasını temizle
    if tts_track and os.path.exists(tts_track):
        try:
            os.remove(tts_track)
        except Exception:
            pass

    # ── SRT ──────────────────────────────────────────────────────────────────
    durations = [d_hook, d_title, d_fact, d_detail, d_closing, d_cta]
    texts = [hook, title, fact, detail, closing, cta_text]

    sections = []
    t = 0.0
    for text, dur in zip(texts, durations):
        sections.append((text, t, t + dur))
        t += dur

    generate_srt(sections, srt_path)
    print(f"  ✓ SRT   : {base_name}.srt  ({len(sections)} segment / {t:.1f}s)")

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    thumbnail_path = os.path.join(OUTPUT_DIR, base_name + ".jpg")
    generate_thumbnail(content, thumbnail_path)
    print(f"  ✓ Thumb : {base_name}.jpg")

    return video_path, srt_path, thumbnail_path


if __name__ == "__main__":
    test_content = {
        "hook":    "Şu An Gerçekten Var mı?",
        "title":   "Şu An Diye Bir Şey Yok",
        "primary_keyword": "zaman",
        "fact":    "Einstein'ın görelilik teorisine göre 'şu an' evrensel değildir.",
        "detail":  "GPS uyduları her gün bu etkiyi hesaba katmak zorundadır.",
        "closing": "Peki sen şu an gerçekten 'şu an'da mısın?",
        "hashtags": ["#zaman", "#fizik", "#bilim", "#einstein", "#Shorts"],
        "youtube_title": "Zaman Gerçek mi? | Channel Name #Shorts",
        "seo_description": "Zaman aslında aktığını sandığımız gibi akmıyor.",
        "seo_tags": ["zaman", "garip", "fizik"],
    }
    vp, sp = generate_video(test_content)
    print(f"Video: {vp}\nSRT  : {sp}")
