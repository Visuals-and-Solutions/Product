"""Orkiestracja: prompt -> odpowiedź modelu -> kod -> zapis w katalogu."""

from __future__ import annotations

import re

from .providers import Provider, ProviderError
from .storage import Catalog

SYSTEM_PROMPT = (
    "Jesteś generatorem skryptów. Zwróć WYŁĄCZNIE jeden blok kodu w znacznikach ``` "
    "z nazwą języka. Bez komentarzy wokół. Kod ma być kompletny, uruchamialny i dobrze skomentowany w środku. "
    "Dodaj krótki docstring na początku opisujący cel skryptu."
)

FENCE_RE = re.compile(r"```([a-zA-Z0-9_+#-]*)\s*\n(.*?)```", re.DOTALL)

LANG_ALIASES = {
    "py": "python",
    "python": "python",
    "sh": "bash",
    "bash": "bash",
    "shell": "bash",
    "zsh": "bash",
    "js": "javascript",
    "javascript": "javascript",
    "node": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "ps1": "powershell",
    "powershell": "powershell",
    "go": "go",
    "rust": "rust",
    "rs": "rust",
}

FENCE_TO_LANG = {
    "python": "python",
    "py": "python",
    "bash": "bash",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "powershell": "powershell",
    "ps1": "powershell",
    "go": "go",
    "golang": "go",
    "rust": "rust",
}


def extract_code(response: str) -> tuple[str, str | None]:
    """Zwraca (kod, język-z-fence). Gdy brak fence, zwraca całą odpowiedź."""
    match = FENCE_RE.search(response)
    if match:
        return match.group(2).strip() + "\n", FENCE_TO_LANG.get(match.group(1).lower(), match.group(1).lower() or None)
    return response.strip() + "\n", None


def build_user_prompt(task: str, language: str) -> str:
    return f"Język: {language}\nZadanie: {task}\n\nZwróć kompletny skrypt w jednym bloku ```{language}."


def generate_and_save(
    catalog: Catalog,
    provider: Provider,
    task: str,
    *,
    language: str = "python",
    tags: list[str] | None = None,
    description: str = "",
) -> tuple[str, object]:
    """Zwraca (ścieżka_pliku, Script). Rzuca ProviderError przy błędzie API."""
    language = LANG_ALIASES.get(language.lower(), language.lower())
    response = provider.generate(build_user_prompt(task, language), system=SYSTEM_PROMPT)
    code, fenced_lang = extract_code(response)
    if fenced_lang and fenced_lang in LANG_ALIASES and language == "python":
        language = LANG_ALIASES[fenced_lang]
    script = catalog.add(
        name_hint=task,
        code=code,
        language=language,
        description=description or task.strip()[:200],
        tags=tags,
        prompt=task,
        provider=provider.name,
        model=provider.model,
    )
    return script.path, script


__all__ = [
    "ProviderError",
    "build_user_prompt",
    "extract_code",
    "generate_and_save",
    "LANG_ALIASES",
]
