"""
stock_video.py
Stock video fetching — delegates to providers/stock.py.
"""


def fetch_stock_clip(keyword: str, duration: float):
    """Fetch stock video clip for keyword. Returns VideoClip or None."""
    from providers.stock import get_provider
    return get_provider().fetch(keyword, duration)


def get_frame_jpeg(keyword: str) -> bytes | None:
    """Get a preview JPEG frame for keyword. Returns bytes or None."""
    from providers.stock import get_provider, PexelsProvider, PixabayProvider
    provider = get_provider()
    if hasattr(provider, "get_frame"):
        return provider.get_frame(keyword)
    return None
