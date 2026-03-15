"""
providers/stock.py
Stock video provider abstraction.
Supports: Pexels, Pixabay, Local Folder, Disabled
"""

import hashlib
import os

import numpy as np
import requests

_CACHE_DIR = None


def _get_cache_dir() -> str:
    global _CACHE_DIR
    if _CACHE_DIR is None:
        import settings_manager as sm
        base = os.path.dirname(os.path.abspath(__file__))
        _CACHE_DIR = os.path.join(os.path.dirname(base), "stock_cache")
        os.makedirs(_CACHE_DIR, exist_ok=True)
    return _CACHE_DIR


def _cache_path(prefix: str, keyword: str) -> str:
    h    = hashlib.md5(keyword.encode()).hexdigest()[:8]
    safe = "".join(c for c in keyword if c.isalnum() or c == " ").replace(" ", "_")[:28]
    return os.path.join(_get_cache_dir(), f"{prefix}_{safe}_{h}.mp4")


def _download(url: str, dest: str) -> bool:
    try:
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=65536):
                fh.write(chunk)
        return True
    except Exception as e:
        print(f"  ⚠️  Download error: {e}")
        return False


def _fit_portrait(clip, width: int, height: int):
    """Crop/scale clip to portrait format."""
    cw, ch = clip.size
    target_ratio = width / height
    clip_ratio   = cw / ch

    if clip_ratio > target_ratio:
        new_w = int(ch * target_ratio)
        x1    = (cw - new_w) // 2
        clip  = clip.cropped(x1=x1, y1=0, x2=x1 + new_w, y2=ch)
    else:
        new_h = int(cw / target_ratio)
        y1    = (ch - new_h) // 2
        clip  = clip.cropped(x1=0, y1=y1, x2=cw, y2=y1 + new_h)

    return clip.resized((width, height))


def _prepare_clip(raw_path: str, duration: float, dark_overlay: float, fps: int, width: int, height: int):
    """Load, loop, crop, darken and return a VideoClip."""
    from moviepy import VideoFileClip, concatenate_videoclips
    clip = VideoFileClip(raw_path)

    if clip.duration < duration + 0.1:
        loops = int(duration / clip.duration) + 2
        clip  = concatenate_videoclips([clip] * loops)

    clip = clip.subclipped(0, duration)
    clip = _fit_portrait(clip, width, height)
    clip = clip.image_transform(lambda f: (f * dark_overlay).astype(np.uint8))
    return clip.with_fps(fps)


class StockProvider:
    def fetch(self, keyword: str, duration: float):
        """Returns VideoClip or None."""
        raise NotImplementedError

    def get_frame(self, keyword: str) -> bytes | None:
        """Returns JPEG bytes of a preview frame, or None."""
        return None


class DisabledProvider(StockProvider):
    def fetch(self, keyword, duration):
        return None


class PexelsProvider(StockProvider):
    _API = "https://api.pexels.com/videos/search"

    def __init__(self, api_key: str, dark_overlay: float, fps: int, width: int, height: int):
        self.api_key      = api_key
        self.dark_overlay = dark_overlay
        self.fps          = fps
        self.width        = width
        self.height       = height

    def _search(self, keyword: str) -> str | None:
        headers = {"Authorization": self.api_key}
        for orientation in ("portrait", None):
            params = {"query": keyword, "per_page": 5, "size": "medium"}
            if orientation:
                params["orientation"] = orientation
            try:
                r = requests.get(self._API, headers=headers, params=params, timeout=15)
                r.raise_for_status()
                videos = r.json().get("videos", [])
                if videos:
                    break
            except Exception as e:
                print(f"  ⚠️  Pexels error ({keyword}): {e}")
                return None
        else:
            return None

        for video in videos:
            files = video.get("video_files", [])
            for quality in ("hd", "sd"):
                for f in files:
                    if f.get("quality") == quality and f.get("height", 0) > f.get("width", 0):
                        return f["link"]
            for quality in ("hd", "sd"):
                for f in files:
                    if f.get("quality") == quality:
                        return f["link"]
            if files:
                return files[0]["link"]
        return None

    def fetch(self, keyword: str, duration: float):
        cache = _cache_path("pexels", keyword)

        if not os.path.exists(cache):
            print(f"  🎥 Stock video: '{keyword}'")
            url = self._search(keyword)
            if not url:
                print(f"  ⚠️  Not found: '{keyword}'")
                return None
            print(f"  ⬇️  Downloading...")
            if not _download(url, cache):
                return None
            print(f"  ✓ Cached: {os.path.basename(cache)}")
        else:
            print(f"  ✓ Cache hit: '{keyword}'")

        try:
            return _prepare_clip(cache, duration, self.dark_overlay, self.fps, self.width, self.height)
        except Exception as e:
            print(f"  ⚠️  Clip error ({keyword}): {e}")
            try:
                os.remove(cache)
            except Exception:
                pass
            return None

    def get_frame(self, keyword: str) -> bytes | None:
        """Returns JPEG bytes of first cached frame, or fetches a short clip."""
        import io
        from PIL import Image
        cache = _cache_path("pexels", keyword)

        if not os.path.exists(cache):
            url = self._search(keyword)
            if not url:
                return None
            if not _download(url, cache):
                return None

        try:
            from moviepy import VideoFileClip
            clip  = VideoFileClip(cache)
            frame = clip.get_frame(min(1.0, clip.duration / 2))
            clip.close()
            img   = Image.fromarray(frame.astype("uint8"))
            buf   = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            return buf.getvalue()
        except Exception:
            return None


class PixabayProvider(StockProvider):
    _API = "https://pixabay.com/api/videos/"

    def __init__(self, api_key: str, dark_overlay: float, fps: int, width: int, height: int):
        self.api_key      = api_key
        self.dark_overlay = dark_overlay
        self.fps          = fps
        self.width        = width
        self.height       = height

    def _search(self, keyword: str) -> str | None:
        params = {
            "key":         self.api_key,
            "q":           keyword,
            "per_page":    5,
            "video_type":  "film",
        }
        try:
            r = requests.get(self._API, params=params, timeout=15)
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                return None
            videos = hits[0].get("videos", {})
            for quality in ("medium", "large", "small", "tiny"):
                v = videos.get(quality)
                if v and v.get("url"):
                    return v["url"]
        except Exception as e:
            print(f"  ⚠️  Pixabay error ({keyword}): {e}")
        return None

    def fetch(self, keyword: str, duration: float):
        cache = _cache_path("pixabay", keyword)

        if not os.path.exists(cache):
            print(f"  🎥 Stock video (Pixabay): '{keyword}'")
            url = self._search(keyword)
            if not url:
                return None
            if not _download(url, cache):
                return None

        try:
            return _prepare_clip(cache, duration, self.dark_overlay, self.fps, self.width, self.height)
        except Exception as e:
            print(f"  ⚠️  Clip error ({keyword}): {e}")
            return None


class LocalFolderProvider(StockProvider):
    """Uses local video files from a folder. Picks randomly by keyword match."""

    def __init__(self, folder: str, dark_overlay: float, fps: int, width: int, height: int):
        self.folder       = folder
        self.dark_overlay = dark_overlay
        self.fps          = fps
        self.width        = width
        self.height       = height

    def fetch(self, keyword: str, duration: float):
        import random
        if not os.path.exists(self.folder):
            return None

        exts  = (".mp4", ".mov", ".avi", ".mkv")
        files = [f for f in os.listdir(self.folder) if f.lower().endswith(exts)]
        if not files:
            return None

        # Try keyword match first
        kw_lower = keyword.lower().replace(" ", "_")
        matches  = [f for f in files if kw_lower in f.lower()]
        chosen   = random.choice(matches) if matches else random.choice(files)
        path     = os.path.join(self.folder, chosen)

        try:
            return _prepare_clip(path, duration, self.dark_overlay, self.fps, self.width, self.height)
        except Exception as e:
            print(f"  ⚠️  Local clip error: {e}")
            return None


def get_provider() -> StockProvider:
    """Returns configured stock video provider based on settings."""
    import settings_manager as sm

    if not sm.get("stock_video.enabled", True):
        return DisabledProvider()

    provider = sm.get("stock_video.provider", "pexels")
    dark     = sm.get("video.dark_overlay", 0.55)
    fps      = sm.get("video.fps", 30)
    width    = sm.get("video.width", 1080)
    height   = sm.get("video.height", 1920)

    if provider == "pexels":
        api_key = sm.get("stock_video.pexels_api_key", "")
        if not api_key:
            print("  ⚠️  Pexels API key not set. Stock video disabled.")
            return DisabledProvider()
        return PexelsProvider(api_key, dark, fps, width, height)

    elif provider == "pixabay":
        api_key = sm.get("stock_video.pixabay_api_key", "")
        if not api_key:
            print("  ⚠️  Pixabay API key not set. Stock video disabled.")
            return DisabledProvider()
        return PixabayProvider(api_key, dark, fps, width, height)

    elif provider == "local":
        folder = sm.get("stock_video.local_folder", "stock_videos/")
        base   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.isabs(folder):
            folder = os.path.join(base, folder)
        return LocalFolderProvider(folder, dark, fps, width, height)

    else:
        return DisabledProvider()
