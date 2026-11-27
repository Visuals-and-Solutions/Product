"""CLI ScriptForge.

Przykłady:
    scriptforge providers
    scriptforge gen "backup katalogu do tar.gz z rotacją" -p google --tags backup,bash
    scriptforge list --tag backup
    scriptforge show 3
    scriptforge run 3
    scriptforge export
    scriptforge serve --port 7860
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import KNOWN_KEY_NAMES, PROVIDERS, Settings, import_env_file, key_status, set_api_key, user_config_path
from .generator import LANG_ALIASES, ProviderError, generate_and_save
from .modelinfo import all_models
from .providers import build_provider, explain_error, provider_status
from .storage import RUNNABLE, Catalog


def _catalog(args) -> Catalog:
    settings = Settings.from_env()
    workspace = Path(args.workspace) if getattr(args, "workspace", None) else settings.workspace
    db = Path(args.db) if getattr(args, "db", None) else workspace / "catalog.sqlite3"
    return Catalog(workspace, db)


def _resolve_script(catalog: Catalog, ref: str):
    script = catalog.get(ref)
    if not script:
        print(f"Nie znaleziono skryptu: {ref}", file=sys.stderr)
        sys.exit(1)
    return script


def cmd_providers(_args) -> None:
    print(f"{'Provider':<10} {'Model domyślny':<34} {'Klucz':<6} Zmienne środowiskowe")
    for row in provider_status():
        print(f"{row['name']:<10} {row['default_model']:<34} {'OK' if row['configured'] else '—':<6} {','.join(row['env_keys']) or '-'}")


def cmd_gen(args) -> None:
    catalog = _catalog(args)
    try:
        provider = build_provider(args.provider, args.model)
    except ProviderError as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        sys.exit(2)
    print(f"Provider: {provider.name} / model: {provider.model}")
    print("Generowanie...")
    try:
        path, script = generate_and_save(
            catalog,
            provider,
            args.task,
            language=args.language,
            tags=[t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None,
        )
    except ProviderError as exc:
        print(f"Błąd API: {exc}", file=sys.stderr)
        sys.exit(3)
    print(f"Zapisano: {path}")
    print(f"ID: {script.id}  slug: {script.slug}  język: {script.language}")
    catalog.export_index()


def cmd_list(args) -> None:
    catalog = _catalog(args)
    scripts = catalog.list(tag=args.tag, search=args.search)
    if not scripts:
        print("Brak skryptów. Użyj: scriptforge gen \"zadanie\"")
        return
    print(f"{'ID':<5} {'Język':<12} {'Tagi':<22} {'Nazwa'}")
    for s in scripts:
        print(f"{s.id:<5} {s.language:<12} {(','.join(s.tags))[:21]:<22} {s.name[:60]}")


def cmd_show(args) -> None:
    catalog = _catalog(args)
    script = _resolve_script(catalog, args.ref)
    print(f"ID: {script.id}")
    print(f"Nazwa: {script.name}")
    print(f"Plik: {script.path}")
    print(f"Język: {script.language}")
    print(f"Tagi: {', '.join(script.tags) or '—'}")
    print(f"Provider: {script.provider}/{script.model}")
    print(f"Utworzono: {script.created_at}  Wersja: {script.version}")
    print(f"Prompt: {script.prompt}")
    print("-" * 60)
    print(catalog.read_code(script))


def cmd_run(args) -> None:
    catalog = _catalog(args)
    script = _resolve_script(catalog, args.ref)
    if script.language not in RUNNABLE:
        print(f"Języka {script.language} nie da się uruchomić bezpośrednio.", file=sys.stderr)
        sys.exit(1)
    runner = RUNNABLE[script.language][0]
    print(f"$ {runner} {script.path}")
    result = subprocess.run([runner, script.path])
    sys.exit(result.returncode)


def cmd_edit(args) -> None:
    catalog = _catalog(args)
    script = catalog.update_meta(
        args.ref,
        name=args.name,
        description=args.description,
        tags=[t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None,
    )
    if not script:
        print(f"Nie znaleziono skryptu: {args.ref}", file=sys.stderr)
        sys.exit(1)
    catalog.export_index()
    print(f"Zaktualizowano: {script.id} {script.name}")


def cmd_delete(args) -> None:
    catalog = _catalog(args)
    if catalog.delete(args.ref):
        catalog.export_index()
        print(f"Usunięto: {args.ref}")
    else:
        print(f"Nie znaleziono skryptu: {args.ref}", file=sys.stderr)
        sys.exit(1)


def cmd_models(args) -> None:
    catalog = _catalog(args)
    results = all_models(refresh=args.refresh, cache_dir=catalog.workspace)
    for name, info in results.items():
        label = PROVIDERS[name]["label"]
        src = f"(z cache, {info['fetched_at']})" if info["source"] == "cache" else f"({info['source']})"
        print(f"\n{label} [{name}] {src}")
        if info["error"]:
            print(f"  błąd: {info['error']}")
        if not info["models"]:
            print("  brak danych")
        for m in info["models"]:
            marker = "* " if m == PROVIDERS[name]["default_model"] else "  "
            print(f"  {marker} {m}")
    print("\n(* = model domyślny)")


def cmd_config(args) -> None:
    if args.import_path:
        try:
            imported, skipped = import_env_file(args.import_path)
        except FileNotFoundError as exc:
            print(f"Błąd: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Stała konfiguracja: {user_config_path()}")
        if imported:
            print(f"Zaimportowano klucze: {', '.join(imported)}")
        else:
            print("Nie znaleziono nowych kluczy do zaimportowania.")
        if skipped:
            print(f"Pominięto (już zapisane): {skipped}")
        return
    print(f"Stała konfiguracja (przetrwa reinstalacje): {user_config_path()}")
    print(f"{'Zmienna':<20} {'Stan':<12} {'Typ':<18} Wartość")
    for row in key_status():
        print(f"{row['name']:<20} {'OK' if row['set'] else '—':<12} {row['kind'][:17]:<18} {row['masked'] or '(brak)'}")
        if row["warning"]:
            print(f"{'':<20} ⚠ {row['kind']}")
    print("\nGoogle: nowe klucze AI Studio mają format 'AQ.Ab…' (Auth). Stare 'AIza…' wygasły po IX 2026.")
    print("Import kluczy ze starego .env (bez wyświetlania wartości):")
    print(f"  scriptforge config --import /ścieżka/do/starego/.env")


def cmd_doctor(args) -> None:
    catalog = _catalog(args)
    results = all_models(refresh=True, cache_dir=catalog.workspace)
    problems = 0
    for name, info in results.items():
        label = PROVIDERS[name]["label"]
        if info["error"]:
            problems += 1
            print(f"[BŁĄD] {label} [{name}]")
            print(f"       {info['error']}")
        elif info["models"]:
            print(f"[OK]   {label} [{name}] — klucz działa, dostępne modele: {len(info['models'])}")
        else:
            problems += 1
            print(f"[?]    {label} [{name}] — brak danych")
    if problems:
        print(f"\nProblemy: {problems}. Napraw i uruchom ponownie: scriptforge doctor")
    else:
        print("\nWszystkie skonfigurowane providery działają poprawnie.")


def cmd_key(args) -> None:
    if args.action == "list":
        cmd_config(args)
        return
    name = args.name
    if name not in KNOWN_KEY_NAMES:
        print(f"Nieznana nazwa klucza: {name}. Dozwolone: {', '.join(KNOWN_KEY_NAMES)}", file=sys.stderr)
        sys.exit(1)
    import getpass

    value = args.value or getpass.getpass(f"{name} (wejście ukryte): ")
    try:
        set_api_key(name, value)
    except ValueError as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Zapisano {name} w {user_config_path()}")
    print("Test: scriptforge doctor")


def cmd_export(args) -> None:
    catalog = _catalog(args)
    md = catalog.export_index()
    js = catalog.export_json()
    print(f"INDEX.md: {md}")
    print(f"catalog.json: {js}")


def cmd_serve(args) -> None:
    from .webapp import create_app

    settings = Settings.from_env()
    app = create_app()
    host = "127.0.0.1"
    print(f"Panel: http://{host}:{args.port}")
    app.run(host=host, port=args.port, debug=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scriptforge", description="Generator i katalog skryptów (Google / NVIDIA / Z.ai)")
    parser.add_argument("--workspace", help="katalog roboczy (domyślnie ~/scriptforge)")
    parser.add_argument("--db", help="ścieżka do bazy SQLite")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("providers", help="lista providerów i stan kluczy")
    p.set_defaults(func=cmd_providers)

    p = sub.add_parser("gen", help="wygeneruj skrypt z promptu")
    p.add_argument("task", help="co ma robić skrypt")
    p.add_argument("-p", "--provider", default=Settings.from_env().provider, choices=list(PROVIDERS))
    p.add_argument("-m", "--model", default=None, help="model (domyślny z configu providera)")
    p.add_argument("-l", "--language", default="python", help=f"język skryptu: {', '.join(sorted(set(LANG_ALIASES.values())))}")
    p.add_argument("--tags", default=None, help="tagi po przecinku, np. backup,devops")
    p.set_defaults(func=cmd_gen)

    p = sub.add_parser("list", help="lista skryptów")
    p.add_argument("--tag", default=None)
    p.add_argument("--search", default=None)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="pokaż szczegóły i kod")
    p.add_argument("ref", help="ID lub slug")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("run", help="uruchom skrypt (python/bash/js)")
    p.add_argument("ref", help="ID lub slug")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("edit", help="edytuj metadane (nazwa, opis, tagi)")
    p.add_argument("ref", help="ID lub slug")
    p.add_argument("--name", default=None)
    p.add_argument("--description", default=None)
    p.add_argument("--tags", default=None)
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("delete", help="usuń skrypt i plik")
    p.add_argument("ref", help="ID lub slug")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("models", help="dostępne modele dla kluczy API (z cache)")
    p.add_argument("--refresh", action="store_true", help="wymuś odświeżenie z API")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("config", help="stan kluczy i stała konfiguracja (~/.config/scriptforge/.env)")
    p.add_argument("--import", dest="import_path", default=None, metavar="PLIK", help="zaimportuj klucze API ze starego pliku .env")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("doctor", help="test kluczy API każdego providera (pobiera modele)")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("key", help="dodaj/aktualizuj klucz API (wejście ukryte)")
    p.add_argument("action", choices=["set", "list"])
    p.add_argument("name", nargs="?", default=None, help=f"nazwa zmiennej: {', '.join(KNOWN_KEY_NAMES)}")
    p.add_argument("value", nargs="?", default=None, help="opcjonalnie wartość (lepiej pominąć — wtedy ukryte pytanie)")
    p.set_defaults(func=cmd_key)

    p = sub.add_parser("export", help="eksportuj INDEX.md i catalog.json")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("serve", help="panel webowy (tylko 127.0.0.1)")
    p.add_argument("--port", type=int, default=7860)
    p.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
