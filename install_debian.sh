#!/usr/bin/env bash
# ScriptForge — czysta, idempotentna instalacja (Debian/Ubuntu/Termux).
# Można uruchamiać wielokrotnie: kod aktualizuje się w jednym stałym miejscu,
# klucze API w ~/.config/scriptforge/.env nigdy nie są nadpisywane.
#
# Użycie:
#   ./install_debian.sh              instalacja/aktualizacja do ~/scriptforge
#   ./install_debian.sh doctor       instalacja + test kluczy
#   ./install_debian.sh serve        instalacja + panel webowy
#   ./install_debian.sh models       instalacja + lista modeli

set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
TARGET="${SCRIPTFORGE_DIR:-$HOME/scriptforge}"
VENV="$TARGET/.venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
BIN="$VENV/bin/scriptforge"
USER_CONFIG="${SCRIPTFORGE_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/scriptforge/.env}"
KEYS_RE='^(GOOGLE_API_KEY|GEMINI_API_KEY|NVIDIA_API_KEY|ZAI_API_KEY|ZHIPU_API_KEY)=.+'

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mBŁĄD:\033[0m %s\n' "$*" >&2; exit 1; }
has_keys() { grep -qE "$KEYS_RE" "$1" 2>/dev/null; }

[ -f "$SRC/pyproject.toml" ] || die "Uruchom z katalogu paczki ScriptForge (tam, gdzie jest pyproject.toml)."

command -v python3 >/dev/null 2>&1 || die "Zainstaluj python3: sudo apt install python3 python3-venv (Termux: pkg install python)"

log "Cel instalacji: $TARGET (stały, wspólny dla wszystkich wersji)"
mkdir -p "$TARGET"

log "Kopiuję kod (nadpisuje tylko pliki programu, nigdy kluczy)"
for item in pyproject.toml scriptforge tests README.md .env.example; do
    [ -e "$SRC/$item" ] || continue
    rm -rf "$TARGET/$item"
    cp -r "$SRC/$item" "$TARGET/$item"
done
rm -f "$TARGET/.env"

cd "$TARGET"

if [ ! -x "$PY" ]; then
    log "Tworzę środowisko wirtualne"
    if ! python3 -m venv "$VENV" 2>/dev/null; then
        if command -v pkg >/dev/null 2>&1; then
            log "Termux: doinstalowuję python-pip i ponawiam"
            pkg install -y python-pip || true
        fi
        python3 -m venv "$VENV" || die "Nie udało się venv. Debian: sudo apt install python3-venv; Termux: pkg install python-pip"
    fi
fi

log "Instaluję pakiet (venv reused)"
"$PIP" install --upgrade pip >/dev/null 2>&1 || true
"$PIP" install -q -e .

mkdir -p "$HOME/.local/bin"
ln -sf "$BIN" "$HOME/.local/bin/scriptforge"
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) PATH_NOTE=1 ;;
esac

imported=0
if [ -f "$SRC/.env" ] && has_keys "$SRC/.env"; then
    log "Klucze w paczce ($SRC/.env) — przenoszę do $USER_CONFIG"
    "$BIN" config --import "$SRC/.env" || true
    imported=1
fi
if [ "$imported" -eq 0 ] && ! has_keys "$USER_CONFIG"; then
    for cand in "$SRC/../.env" "$SRC/../../.env" "$HOME/.env" "$HOME/scriptforge/.env"; do
        if has_keys "$cand"; then
            log "Znalazłem stare klucze w $cand — importuję do $USER_CONFIG"
            "$BIN" config --import "$cand" || true
            imported=1
            break
        fi
    done
fi
if [ "$imported" -eq 0 ] && ! has_keys "$USER_CONFIG"; then
    log "Brak kluczy — utwórz $USER_CONFIG (nano) albo: scriptforge config --import /ścieżka/.env"
fi

log "Instalacja zakończona."
echo
echo "Teraz używaj po prostu: scriptforge (działa z każdego katalogu)"
if [ "${PATH_NOTE:-0}" = "1" ]; then
    echo "UWAGA: dodaj do PATH jeśli 'command not found':"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
    echo "  (Termux: ~/.bashrc lub uruchamiaj \$HOME/.local/bin/scriptforge)"
    echo
fi
echo "  scriptforge doctor     # test kluczy API"
echo "  scriptforge models     # dostępne modele"
echo "  scriptforge serve      # panel: http://127.0.0.1:7860"
echo
echo "Stare, zduplikowane katalogi paczek możesz usunąć:"
echo "  rm -rf ~/.../Product-vibe-scriptforge-*  (te z zagnieżdżeniami)"

case "${1:-}" in
    doctor|serve|models|providers)
        "$BIN" "$@"
        ;;
    "")
        ;;
    *)
        "$BIN" "$@"
        ;;
esac
