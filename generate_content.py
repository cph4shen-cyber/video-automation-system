"""
generate_content.py
Generates YouTube Shorts content via configurable AI provider.
"""

import json
import os
import re
import time

import settings_manager as sm
from config import USED_FACTS_FILE


def _build_system_prompt() -> str:
    channel = sm.get("channel.name", "My Channel")
    custom  = sm.get("content.system_prompt", "")
    if custom:
        return custom.replace("My Channel", channel)
    return f"""You are a content writer producing short-form YouTube videos about physics, consciousness, time, the universe, and strange scientific facts. Channel name: {channel}.

CORE RULES:
- Scientifically and philosophically grounded. No theological/spiritual content.
- Choose surprising, lesser-known facts.
- Clear but profound.
- Always choose a different topic.
- Return only valid JSON, nothing else.

TITLE FORMAT (one REQUIRED):
  Question: "Why does X exist?" / "Is X real?"
  Shock: "There is no such thing as X"
  Number: "X% actually..." / "N of X are..."
  Contrast: "X is actually Y" / "Before X there was Y"
  Incomplete: "Before X..."

YOUTUBE TITLE FORMAT: [primary_keyword] [action/question] | {channel} #Shorts
  - Max 60 characters
  - primary_keyword in first 1-3 words
  - #Shorts at end

HOOK RULES:
  - Max 12 words
  - Question or incomplete sentence
  - Must create a "wait, what?" moment
  - Must be DIFFERENT from title

HASHTAG: 5-7 total. primary_keyword + niche + #shorts"""


USER_PROMPT_TEMPLATE = """Generate a surprising and shocking scientific fact for a YouTube Shorts video.

Return ONLY this JSON:
{{
  "hook":              "First frame text (max 12 words, question/incomplete, different from title)",
  "title":             "Short title (max 8 words, follows format rules)",
  "primary_keyword":   "Main keyword (1-2 words)",
  "fact":              "Main information (2-3 sentences, clear and striking)",
  "detail":            "Deepening context (2-3 sentences, continues fact, no repetition)",
  "closing":           "Closing question (1 sentence, thought-provoking)",
  "hashtags":          ["#keyword", "#niche1", "#niche2", "#science", "#Shorts"],
  "youtube_title":     "[keyword] [action] | Channel #Shorts (max 60 chars)",
  "seo_description":   "SEO description (keyword in first sentence + content summary + hashtags)",
  "seo_tags":          ["tag1", "tag2"],
  "video_keywords": {{
    "hook":    "1-3 English words for visual search matching this section (e.g. 'universe expanding')",
    "title":   "1-3 English words for visual search matching this section",
    "fact":    "1-3 English words for visual search matching this section",
    "detail":  "1-3 English words for visual search matching this section",
    "closing": "1-3 English words for visual search (e.g. 'person thinking contemplating')",
    "cta":     "1-3 English words for visual search (e.g. 'galaxy stars night sky')"
  }}
}}

{extra}
"""


def load_used_facts() -> list[str]:
    if not os.path.exists(USED_FACTS_FILE):
        return []
    with open(USED_FACTS_FILE, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]


def save_used_fact(title: str):
    with open(USED_FACTS_FILE, "a", encoding="utf-8") as f:
        f.write(title + "\n")


def validate_content(data: dict) -> list[str]:
    warnings = []
    hook      = data.get("hook", "")
    yt_title  = data.get("youtube_title", "")
    hashtags  = data.get("hashtags", [])

    if len(hook.split()) > 12:
        warnings.append(f"hook exceeds 12 words ({len(hook.split())} words)")

    if len(yt_title) > 60:
        warnings.append(f"youtube_title exceeds 60 chars — trimming")
        data["youtube_title"] = yt_title[:57] + "..."

    if "#Shorts" not in yt_title and "#shorts" not in yt_title:
        warnings.append("youtube_title missing #Shorts — adding")
        data["youtube_title"] = (yt_title[:54] + " #Shorts") if len(yt_title) > 54 else yt_title + " #Shorts"

    if not (5 <= len(hashtags) <= 7):
        warnings.append(f"hashtag count {len(hashtags)} (expected: 5-7)")

    return warnings


def generate_content(topic: str = "") -> dict:
    """Generate content using configured AI provider."""
    from providers.content import get_provider

    used = load_used_facts()
    extra_parts = []

    if used:
        recent = used[-15:]
        extra_parts.append(f"DO NOT repeat these topics (last 15 used): {', '.join(recent)}")

    if topic and topic.strip():
        extra_parts.append(f"User selected topic (MUST write about this): {topic.strip()}")

    extra  = "\n\n".join(extra_parts)
    prompt = USER_PROMPT_TEMPLATE.format(extra=extra)
    system = _build_system_prompt()
    max_tokens = sm.get("content.max_tokens", 1200)

    provider = get_provider()

    for attempt in range(3):
        try:
            raw = provider.generate(prompt, system, max_tokens)
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"```\s*$",     "", raw).strip()

            data = json.loads(raw)

            # Fill missing fields
            if "hook" not in data:
                data["hook"] = data.get("title", "")
            if "primary_keyword" not in data:
                data["primary_keyword"] = data.get("title", "").split()[0] if data.get("title") else "science"
            if "seo_description" not in data:
                data["seo_description"] = data.get("fact", "")
            if "seo_tags" not in data:
                data["seo_tags"] = [h.lstrip("#") for h in data.get("hashtags", [])]
            if "video_keywords" not in data:
                kw = data.get("primary_keyword", "science").replace("#", "")
                data["video_keywords"] = {
                    "hook":    f"{kw} abstract",
                    "title":   f"{kw} concept",
                    "fact":    f"{kw} science",
                    "detail":  f"{kw} close up",
                    "closing": "person thinking",
                    "cta":     "galaxy stars",
                }

            warnings = validate_content(data)
            for w in warnings:
                print(f"  ⚠️  {w}")

            save_used_fact(data.get("title", "unknown"))
            print(f"  ✓ Topic   : {data['title']}")
            print(f"  ✓ Keyword : {data['primary_keyword']}")
            return data

        except (json.JSONDecodeError, KeyError) as e:
            if attempt < 2:
                print(f"  ⚠️  JSON error (attempt {attempt+1}/3): {e} — retrying in 5s...")
                time.sleep(5)
            else:
                raise RuntimeError(f"Content generation failed: {e}")

    raise RuntimeError("Content generation failed after 3 attempts")


if __name__ == "__main__":
    content = generate_content()
    print(json.dumps(content, ensure_ascii=False, indent=2))
