"""
generate_tts.py
TTS generation via configurable provider (ElevenLabs, OpenAI, Edge-TTS, Disabled).
"""

import os
import tempfile
import wave


# ─── Silent WAV (used by generate_video.py) ───────────────────────────────────
def _silent_wav(duration: float):
    """Create silent stereo WAV AudioClip."""
    from moviepy import AudioFileClip
    fps      = 44100
    n        = int(fps * duration)
    tmp      = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(fps)
        wf.writeframes(b"\x00" * n * 2 * 2)
    tmp.close()
    return AudioFileClip(tmp.name), tmp.name


# ─── Segment generation ────────────────────────────────────────────────────────
def generate_tts_segments(texts: list[str]) -> list | None:
    """
    Generate TTS for each text segment.
    Returns list of (AudioClip, duration, temp_path) or None if TTS disabled/failed.
    """
    from providers.tts import get_provider
    provider = get_provider()

    results = []
    for text in texts:
        result = provider.synthesize(text)
        if result is None:
            return None  # TTS disabled or failed
        results.append(result)

    return results


def generate_tts_track(segments: list) -> str | None:
    """Legacy helper — kept for compatibility."""
    return None
