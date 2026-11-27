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
    log "Brak python3 — instaluję przez apt"
    if command -v sudo >/dev/null 2>&1; then SUDO=sudo; else SUDO=""; fi
    $SUDO apt-get update
    $SUDO apt-get install -y python3 python3-venv python3-pip
fi

if [ ! -x "$PY" ]; then
    log "Tworzę środowisko wirtualne $VENV"
    python3 -m venv "$VENV" 2>/dev/null || die "Nie udało się utworzyć venv. Zainstaluj: sudo apt install python3-venv"
fi

log "Aktualizuję pip i instaluję projekt"
"$PIP" install --upgrade pip >/dev/null
"$PIP" install -e . >/dev/null

if [ ! -f .env ]; then
    log "Tworzę .env z szablonu — wpisz tam swoje klucze API"
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        printf 'GOOGLE_API_KEY=\nNVIDIA_API_KEY=\nZAI_API_KEY=\n' > .env
    fi
    log "Edytuj plik .env (GOOGLE_API_KEY / NVIDIA_API_KEY / ZAI_API_KEY)"
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
        echo "Dalsze kroki:"
        echo "  1) nano .env                 # wpisz klucze API"
        echo "  2) ./install_debian.sh providers   # sprawdź stan kluczy"
        echo "  3) ./install_debian.sh serve       # panel webowy"
        echo "  albo w CLI:"
        echo "     $VENV/bin/scriptforge gen \"zadanie\" -p google"
        ;;
    *)
        scriptforge "$@"
        ;;
esac
