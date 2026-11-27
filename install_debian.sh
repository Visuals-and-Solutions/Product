#!/usr/bin/env bash
# ScriptForge — instalacja i uruchomienie na Debian/Ubuntu
# Użycie:
#   ./install_debian.sh            instalacja (venv + zależności + .env)
#   ./install_debian.sh serve      instalacja (jeśli trzeba) + start panelu webowego
#   ./install_debian.sh providers  szybki podgląd stanu kluczy API

set -euo pipefail

VENV=".venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mBŁĄD:\033[0m %s\n' "$*" >&2; exit 1; }

[ -f pyproject.toml ] || die "Uruchom skrypt z katalogu głównego projektu (tam, gdzie jest pyproject.toml)."

if ! command -v python3 >/dev/null 2>&1; then
    log "Brak python3 — instaluję"
    if command -v pkg >/dev/null 2>&1; then
        pkg install -y python || die "Uruchom: pkg install python"
    elif command -v sudo >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
    else
        apt-get update && apt-get install -y python3 python3-venv python3-pip
    fi
fi

if [ ! -x "$PY" ]; then
    log "Tworzę środowisko wirtualne $VENV"
    if ! python3 -m venv "$VENV" 2>/dev/null; then
        if command -v pkg >/dev/null 2>&1; then
            log "Termux: doinstalowuję python-pip i ponawiam"
            pkg install -y python-pip || true
        fi
        python3 -m venv "$VENV" || die "Nie udało się utworzyć venv. Debian/Ubuntu: sudo apt install python3-venv; Termux: pkg install python-pip"
    fi
fi

log "Aktualizuję pip i instaluję projekt"
"$PIP" install --upgrade pip >/dev/null
"$PIP" install -e . >/dev/null

USER_CONFIG="${SCRIPTFORGE_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/scriptforge/.env}"
KEYS_RE='^(GOOGLE_API_KEY|GEMINI_API_KEY|NVIDIA_API_KEY|ZAI_API_KEY|ZHIPU_API_KEY)=.+'
has_keys() { grep -qE "$KEYS_RE" "$1" 2>/dev/null; }

if [ -f .env ] && has_keys .env; then
    log "Klucze w lokalnym .env — synchronizuję z $USER_CONFIG"
    scriptforge config --import .env >/dev/null 2>&1 || true
elif [ ! -f .env ]; then
    if has_keys "$USER_CONFIG"; then
        log "Klucze API już zapisane w $USER_CONFIG — używam ich"
    else
        imported=0
        for cand in ../.env ../../.env "$HOME/.env" "$HOME/.config/scriptforge/.env"; do
            if has_keys "$cand"; then
                log "Znalazłem klucze w $cand — importuję do $USER_CONFIG"
                scriptforge config --import "$cand" || true
                imported=1
                break
            fi
        done
        if [ "$imported" -eq 0 ]; then
            log "Nie znalazłem żadnych kluczy — tworzę .env z szablonu"
            if [ -f .env.example ]; then
                cp .env.example .env
            else
                printf 'GOOGLE_API_KEY=\nNVIDIA_API_KEY=\nZAI_API_KEY=\n' > .env
            fi
            log "Edytuj plik .env (GOOGLE_API_KEY / NVIDIA_API_KEY / ZAI_API_KEY)"
            log "albo zaimportuj z dowolnego starego .env: .venv/bin/scriptforge config --import /ścieżka/.env"
        fi
    fi
fi

export PATH="$VENV/bin:$PATH"

case "${1:-}" in
    serve)
        log "Start panelu: http://127.0.0.1:7860 (Ctrl+C aby zatrzymać)"
        scriptforge serve
        ;;
    providers)
        scriptforge providers
        ;;
    "")
        log "Instalacja zakończona."
        echo
        if [ -f .env ] && ! grep -qE "$KEYS_RE" .env 2>/dev/null && ! has_keys "$USER_CONFIG"; then
            echo "NAJPIERW KLUCZE:"
            echo "  nano .env                       # wklej klucze API"
            echo "  lub: .venv/bin/scriptforge config --import /ścieżka/do/starego/.env"
            echo
        fi
        echo "Dalsze kroki:"
        echo "  .venv/bin/scriptforge doctor     # test kluczy"
        echo "  .venv/bin/scriptforge serve      # panel webowy"
        echo "  .venv/bin/scriptforge gen \"zadanie\" -p google"
        echo "  (dodaj .venv/bin do PATH albo pisz pełną ścieżkę: .venv/bin/scriptforge)"
        ;;
    *)
        scriptforge "$@"
        ;;
esac
