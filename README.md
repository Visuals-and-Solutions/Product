# ScriptForge

System do generowania i katalogowania skryptów z API modeli: **Google (Gemini)**, **NVIDIA (NIM)** oraz **Z.ai (GLM)**.

Składa się z dwóch interfejsów:

- **CLI** — generowanie, katalogowanie, uruchamianie i eksport skryptów z terminala,
- **Panel webowy** (Flask, tylko `127.0.0.1`) — lista, wyszukiwanie, tagi, generowanie i podgląd kodu w przeglądarce.

## Instalacja na Debian / Ubuntu (skrypt)

Pobierz archiwum z [Releases](../../releases), rozpakuj i uruchom:

```bash
tar xzf scriptforge-*.tar.gz && cd scriptforge-*   # lub unzip scriptforge-*.zip
chmod +x install_debian.sh
./install_debian.sh            # venv + zależności + .env
./install_debian.sh serve      # start panelu: http://127.0.0.1:7860
```

Skrypt sam doinstaluje `python3`, `python3-venv` i `python3-pip` (przez `sudo apt`), jeśli ich brakuje.

## Instalacja (ręczna)

```bash
pip install -e .
# tryb deweloperski z testami:
pip install -e ".[dev]"
```

## Klucze API

Skopiuj `.env.example` do `.env` (lub wyeksportuj zmienne w shellu) i uzupełnij klucze providerów, których używasz:

| Provider | Zmienne | Domyślny model |
|---|---|---|
| Google Gemini | `GOOGLE_API_KEY` lub `GEMINI_API_KEY` | `gemini-2.5-flash` |
| NVIDIA NIM | `NVIDIA_API_KEY` | `meta/llama-3.3-70b-instruct` |
| Z.ai (GLM) | `ZAI_API_KEY` lub `ZHIPU_API_KEY` | `glm-4.6` |

Zmienne opcjonalne: `SCRIPTFORGE_HOME` (katalog roboczy, domyślnie `~/scriptforge`), `SCRIPTFORGE_PROVIDER`, `SCRIPTFORGE_MODEL`.

Stan kluczy sprawdzisz poleceniem `scriptforge providers`. Provider `mock` nie wymaga klucza — służy do testów i pracy offline.

## CLI

```bash
scriptforge providers                                   # providerzy i stan kluczy
scriptforge models [--refresh]                          # dostępne modele dla kluczy (cache 24 h)
scriptforge gen "backup katalogu do tar.gz z rotacją" -p google --tags backup,devops
scriptforge gen "sprawdzenie zajętości dysku" -p nvidia -l bash
scriptforge gen "masowa zmiana nazw plików" -p zai --tags files
scriptforge list [--tag backup] [--search "tar"]
scriptforge show 3                                      # szczegóły + kod
scriptforge run 3                                       # uruchom (python/bash/js)
scriptforge edit 3 --tags backup,prod --name "Backup dzienny"
scriptforge delete 3
scriptforge export                                      # INDEX.md + catalog.json
scriptforge serve --port 7860                           # panel webowy
```

Globalne opcje: `--workspace` (katalog skryptów), `--db` (ścieżka bazy SQLite).

## Panel webowy

```bash
scriptforge serve            # http://127.0.0.1:7860
```

Funkcje: lista skryptów z tagami i wyszukiwaniem, formularz generowania (provider, model, język, tagi), podgląd kodu i promptu źródłowego, usuwanie, API JSON pod `/api/scripts`, lista dostępnych modeli dla klucza pod `/api/models?provider=...` (odświeżenie: `&refresh=1`), health-check `/healthz`. Serwer nasłuchuje **wyłącznie na 127.0.0.1**.

## Struktura danych

```
~/scriptforge/
├── catalog.sqlite3          # katalog: nazwa, opis, tagi, prompt, provider, wersje
├── INDEX.md                 # automatyczny indeks (eksport)
├── catalog.json             # eksport JSON
└── scripts/
    ├── python/*.py
    ├── bash/*.sh
    └── ...
```

Każdy skrypt zapisywany jest jako plik w podfolderze języka, a jego metadane trafiają do SQLite. `INDEX.md` aktualizuje się automatycznie po generowaniu, edycji i usuwaniu.

## Testy

```bash
python -m pytest tests/ -q
```

## Uwagi bezpieczeństwa

- Klucze API trzymaj w `.env` (dodany do `.gitignore`) lub zmiennych środowiskowych — nigdy w kodzie.
- `scriptforge run` wykonuje wygenerowany kod bez dalszych pytań — uruchamiaj tylko skrypty, które sprawdziłeś.
- Panel webowy celowo nie jest wystawiany na sieć; jeśli potrzebujesz dostępu zdalnego, użyj własnego reverse proxy z autoryzacją.
