"""Providerzy LLM: Google Gemini, NVIDIA NIM, Z.ai (GLM) oraz mock do testów."""

from __future__ import annotations

import re
from typing import Protocol

import httpx

from .config import PROVIDERS, api_key_for


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    name: str
    model: str

    def generate(self, prompt: str, *, system: str | None = None) -> str: ...

    def list_models(self) -> list[str]: ...


class OpenAICompatibleProvider:
    """NVIDIA NIM i Z.ai udostępniają API zgodne z OpenAI chat/completions."""

    name = "openai-compatible"

    def __init__(self, base_url: str, model: str, api_key: str, *, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "temperature": 0.2},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise ProviderError(f"{self.name}: HTTP {response.status_code}: {response.text[:500]}")
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.name}: nieoczekiwana odpowiedź API: {exc}") from exc

    def list_models(self) -> list[str]:
        response = httpx.get(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise ProviderError(f"{self.name}: HTTP {response.status_code} przy /models: {response.text[:300]}")
        data = response.json()
        try:
            return sorted(item["id"] for item in data["data"])
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"{self.name}: nieoczekiwany format /models: {exc}") from exc


class GoogleGeminiProvider:
    name = "google"

    def __init__(self, model: str, api_key: str, *, timeout: float = 120.0):
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise ProviderError(f"google: HTTP {response.status_code}: {response.text[:500]}")
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"google: nieoczekiwana odpowiedź API: {exc}") from exc

    def list_models(self) -> list[str]:
        response = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": self.api_key, "pageSize": 1000},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise ProviderError(f"google: HTTP {response.status_code} przy /models: {response.text[:300]}")
        data = response.json()
        try:
            names = [
                m["name"].removeprefix("models/")
                for m in data["models"]
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            return sorted(names)
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"google: nieoczekiwany format /models: {exc}") from exc


class MockProvider:
    """Zwraca deterministyczny kod — smoke testy i praca offline bez kluczy."""

    name = "mock"

    def __init__(self, model: str = "mock-1"):
        self.model = model

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:32].strip("_") or "demo"
        return (
            f"```python\n"
            f'"""Skrypt: {prompt[:80]}"""\n'
            f"def main():\n"
            f'    print("Hello from ScriptForge mock ({slug})")\n'
            f"\n"
            f'if __name__ == "__main__":\n'
            f"    main()\n"
            f"```"
        )

    def list_models(self) -> list[str]:
        return ["mock-1", "mock-2-mini"]


class NVIDIAProvider(OpenAICompatibleProvider):
    name = "nvidia"

    def __init__(self, model: str, api_key: str, **kwargs):
        super().__init__("https://integrate.api.nvidia.com/v1", model, api_key, **kwargs)


class ZaiProvider(OpenAICompatibleProvider):
    name = "zai"

    def __init__(self, model: str, api_key: str, **kwargs):
        super().__init__("https://api.z.ai/api/paas/v4", model, api_key, **kwargs)


def build_provider(provider: str, model: str | None = None) -> Provider:
    if provider not in PROVIDERS:
        raise ProviderError(
            f"Nieznany provider: {provider}. Dostępne: {', '.join(PROVIDERS)}"
        )
    model = model or PROVIDERS[provider]["default_model"]
    if provider == "mock":
        return MockProvider(model)
    api_key = api_key_for(provider)
    if not api_key:
        envs = ", ".join(PROVIDERS[provider]["env_keys"])
        raise ProviderError(f"Brak klucza API dla {provider}. Ustaw {envs}.")
    if provider == "google":
        return GoogleGeminiProvider(model, api_key)
    if provider == "nvidia":
        return NVIDIAProvider(model, api_key)
    if provider == "zai":
        return ZaiProvider(model, api_key)
    raise ProviderError(f"Provider {provider} nie jest obsługiwany")


def provider_status() -> list[dict]:
    rows = []
    for name, meta in PROVIDERS.items():
        key = api_key_for(name)
        rows.append(
            {
                "name": name,
                "label": meta["label"],
                "default_model": meta["default_model"],
                "configured": bool(key) or name == "mock",
                "env_keys": meta["env_keys"],
            }
        )
    return rows
