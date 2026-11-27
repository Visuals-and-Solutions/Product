# ScriptForge

System do generowania i katalogowania skryptów z API modeli: **Google (Gemini)**, **NVIDIA (NIM)** oraz **Z.ai (GLM)**.

Składa się z dwóch interfejsów:

- **CLI** — generowanie, katalogowanie, uruchamianie i eksport skryptów z terminala,
- **Panel webowy** (Flask, tylko `127.0.0.1`) — lista, wyszukiwanie, tagi, generowanie i podgląd kodu w przeglądarce.

## Instalacja na Debian / Ubuntu / Termux (czysta, idempotentna)

Kod instaluje się zawsze do **jednego stałego katalogu** `~/scriptforge`, a klucze do `~/.config/scriptforge/.env`. Skrypt można uruchamiać wielokrotnie — aktualizuje kod, nigdy nie dubluje instalacji ani nie nadpisuje kluczy. Instalator sam znajdzie i zaimportuje klucze ze starych katalogów (`../.env`, `~/.env`).

```bash
tar xzf scriptforge-*.tar.gz && cd Product-*
chmod +x install_debian.sh
./install_debian.sh          # instalacja/aktualizacja → ~/scriptforge
scriptforge doctor           # test kluczy (lub $HOME/.local/bin/scriptforge)
scriptforge serve            # panel: http://127.0.0.1:7860
```

Po instalacji stare, zduplikowane katalogi paczek można usunąć — nie są już potrzebne.

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
| Google Gemini | `GOOGLE_API_KEY` lub `GEMINI_API_KEY` | `gemini-4-hydrogen` |
| NVIDIA NIM | `NVIDIA_API_KEY` | `meta/llama-3.3-70b-instruct` |
| Z.ai (GLM) | `ZAI_API_KEY` lub `ZHIPU_API_KEY` | `glm-4.6` |

Zmienne opcjonalne: `SCRIPTFORGE_HOME` (katalog roboczy, domyślnie `~/scriptforge`), `SCRIPTFORGE_PROVIDER`, `SCRIPTFORGE_MODEL`, `SCRIPTFORGE_CONFIG` (ścieżka stałej konfiguracji).

### Modele Google (AI Studio, stan: 2026-11)

Domyślnie: **`gemini-4-hydrogen`** (rekomendowany przez Google do nowych projektów). Dostępne konkretnie: `gemini-4-carbon`, `gemini-4-neon`, `gemini-4-hydrogen`, `gemini-4-argon`, `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.1-pro-preview`.

Uwaga: `gemini-2.5-flash` i `gemini-2.5-pro` są wycofane — od 1.12.2026 Google przekierowuje je na `gemini-3.5-flash-lite` i `gemini-3.8-flash`. Pełna, aktualna lista dla Twojego klucza: `scriptforge models --refresh`.

### Stała konfiguracja kluczy (przetrwa reinstalacje)

Klucze zapisane w `~/.config/scriptforge/.env` są wczytywane zawsze — nawet gdy uruchamiasz system z nowo rozpakowanej paczki, w której nie ma lokalnego `.env`. Instalator nigdy nie nadpisze istniejących kluczy.

```bash
scriptforge config                        # stan kluczy (maskowany) + ścieżki konfiguracji
scriptforge config --import ~/stara-paczka/.env   # import kluczy ze starego .env (bez wyświetlania wartości)
scriptforge doctor                        # test każdego klucza w praktyce (pobiera listę modeli)
```

`scriptforge doctor` wypisze `[OK]` dla działających kluczy, a przy błędzie poda konkretną przyczynę po polsku (np. nieprawidłowy klucz, brak uprawnień, przekroczony limit). Klucze są przy wczytywaniu oczyszczane ze spacji, cudzysłowów i prefiksu `Bearer`.

Stan kluczy sprawdzisz także poleceniem `scriptforge providers`. Provider `mock` nie wymaga klucza — służy do testów i pracy offline.

### Format kluczy Google (AI Studio) — WAŻNE

Od **28.05.2026** Google AI Studio wydaje wyłącznie nowe klucze **Auth** zaczynające się od **`AQ.Ab…`** (ok. 53 znaki). Stare klucze **Standard (`AIza…`) wygasły po wrześniu 2026** — jeśli masz stary klucz, wygeneruj nowy w AI Studio. System przesyła klucz nagłówkiem `x-goog-api-key` (zalecana droga dla formatu Auth) i w `scriptforge config` / panelu pokazuje rozpoznany format oraz ostrzeżenie przy przestarzałym `AIza`.

Pułapka: lista kluczy w AI Studio pokazuje **skrócony, zamaskowany podgląd** — otwórz szczegóły klucza i użyj **„Copy key"**, żeby skopiować pełną wartość; skrócony fragment da błąd `API_KEY_INVALID`.

### Klucze z poziomu przeglądarki i CLI

W panelu webowym: zakładka **Klucze** (`http://127.0.0.1:7860/keys`) — dodajesz/aktualizujesz klucz, wartość nigdy nie jest wyświetlana (tylko maska), a przycisk **Testuj klucze** od razu weryfikuje każdy klucz pobierając listę modeli. Klucze zapisują się w stałej konfiguracji.

Z terminala (wejście ukryte, nie trafia do historii shella):

```bash
scriptforge key set GOOGLE_API_KEY   # zapyta o wartość bez echa
scriptforge key list
```

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
