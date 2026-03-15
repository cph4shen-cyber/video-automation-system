"""
providers/content.py
Content generation provider abstraction.
Supports: Claude (Anthropic), OpenAI-compatible (GPT-4, local LLMs, etc.), Gemini
"""


class ContentProvider:
    def generate(self, prompt: str, system: str, max_tokens: int = 1200) -> str:
        raise NotImplementedError


class ClaudeProvider(ContentProvider):
    def __init__(self, api_key: str, model: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = model

    def generate(self, prompt: str, system: str, max_tokens: int = 1200) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()


class OpenAIProvider(ContentProvider):
    """Works with OpenAI, Azure, Ollama, or any OpenAI-compatible endpoint."""
    def __init__(self, api_key: str, model: str, base_url: str = None):
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model  = model

    def generate(self, prompt: str, system: str, max_tokens: int = 1200) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()


class GeminiProvider(ContentProvider):
    def __init__(self, api_key: str, model: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model_name = model
        self._genai = genai

    def generate(self, prompt: str, system: str, max_tokens: int = 1200) -> str:
        model = self._genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system,
        )
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens},
        )
        return response.text.strip()


def get_provider() -> ContentProvider:
    """Returns configured content provider based on settings."""
    import settings_manager as sm
    provider = sm.get("content.provider", "claude")
    api_key  = sm.get("content.api_key", "")
    model    = sm.get("content.model", "claude-sonnet-4-6")

    if provider == "claude":
        return ClaudeProvider(api_key=api_key, model=model)
    elif provider in ("openai", "custom"):
        base_url = sm.get("content.base_url", None)
        return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
    elif provider == "gemini":
        return GeminiProvider(api_key=api_key, model=model)
    else:
        raise ValueError(f"Unknown content provider: {provider}")
