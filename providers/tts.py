"""
providers/tts.py
TTS provider abstraction.
Supports: ElevenLabs, OpenAI TTS, Edge-TTS (free), Disabled
"""

import os
import tempfile
import wave


def _silent_wav(duration: float):
    """Create a silent WAV AudioClip."""
    from moviepy import AudioFileClip
    fps = 44100
    n = int(fps * duration)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(fps)
        wf.writeframes(b"\x00" * n * 2 * 2)
    tmp.close()
    return AudioFileClip(tmp.name), tmp.name


class TTSProvider:
    def synthesize(self, text: str):
        """Returns (AudioClip, duration_sec, temp_path) or None."""
        raise NotImplementedError


class DisabledProvider(TTSProvider):
    def synthesize(self, text: str):
        return None


class ElevenLabsProvider(TTSProvider):
    def __init__(self, api_key: str, voice_id: str, model: str,
                 stability: float, similarity_boost: float, style: float):
        import requests as req
        self._requests    = req
        self.api_key      = api_key
        self.voice_id     = voice_id
        self.model        = model
        self.stability    = stability
        self.similarity_boost = similarity_boost
        self.style        = style

    def synthesize(self, text: str):
        from moviepy import AudioFileClip
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "Accept":       "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key":   self.api_key,
        }
        payload = {
            "text":     text,
            "model_id": self.model,
            "voice_settings": {
                "stability":         self.stability,
                "similarity_boost":  self.similarity_boost,
                "style":             self.style,
                "use_speaker_boost": True,
            },
        }
        try:
            r = self._requests.post(url, json=payload, headers=headers, timeout=40)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠️  ElevenLabs error: {e}")
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(r.content)
        tmp.close()

        try:
            clip = AudioFileClip(tmp.name)
            return clip, clip.duration, tmp.name
        except Exception as e:
            print(f"  ⚠️  ElevenLabs audio parse error: {e}")
            os.unlink(tmp.name)
            return None


class OpenAITTSProvider(TTSProvider):
    def __init__(self, api_key: str, voice: str = "nova", model: str = "tts-1"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.voice  = voice
        self.model  = model

    def synthesize(self, text: str):
        from moviepy import AudioFileClip
        try:
            response = self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
            )
        except Exception as e:
            print(f"  ⚠️  OpenAI TTS error: {e}")
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        response.stream_to_file(tmp.name)
        tmp.close()

        try:
            clip = AudioFileClip(tmp.name)
            return clip, clip.duration, tmp.name
        except Exception as e:
            print(f"  ⚠️  OpenAI TTS audio parse error: {e}")
            os.unlink(tmp.name)
            return None


class EdgeTTSProvider(TTSProvider):
    """Free TTS via Microsoft Edge (no API key needed)."""
    def __init__(self, voice: str = "tr-TR-EmelNeural"):
        self.voice = voice

    def synthesize(self, text: str):
        try:
            import edge_tts
            import asyncio
            from moviepy import AudioFileClip
        except ImportError:
            print("  ⚠️  edge-tts not installed. Run: pip install edge-tts")
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()

        async def _run():
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(tmp.name)

        try:
            asyncio.run(_run())
            clip = AudioFileClip(tmp.name)
            return clip, clip.duration, tmp.name
        except Exception as e:
            print(f"  ⚠️  Edge-TTS error: {e}")
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
            return None


def get_provider() -> TTSProvider:
    """Returns configured TTS provider based on settings."""
    import settings_manager as sm
    if not sm.get("tts.enabled", True):
        return DisabledProvider()

    provider = sm.get("tts.provider", "elevenlabs")
    api_key  = sm.get("tts.api_key", "")

    if provider == "elevenlabs":
        if not api_key:
            print("  ⚠️  ElevenLabs API key not set. TTS disabled.")
            return DisabledProvider()
        return ElevenLabsProvider(
            api_key=api_key,
            voice_id=sm.get("tts.voice_id", ""),
            model=sm.get("tts.model", "eleven_multilingual_v2"),
            stability=sm.get("tts.stability", 0.35),
            similarity_boost=sm.get("tts.similarity_boost", 0.75),
            style=sm.get("tts.style", 0.60),
        )
    elif provider == "openai":
        if not api_key:
            print("  ⚠️  OpenAI API key not set. TTS disabled.")
            return DisabledProvider()
        return OpenAITTSProvider(
            api_key=api_key,
            voice=sm.get("tts.openai_voice", "nova"),
            model=sm.get("tts.openai_model", "tts-1"),
        )
    elif provider == "edge":
        voice = sm.get("tts.edge_voice", "tr-TR-EmelNeural")
        return EdgeTTSProvider(voice=voice)
    else:
        return DisabledProvider()
