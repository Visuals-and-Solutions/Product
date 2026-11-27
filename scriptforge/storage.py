"""Katalog skryptów: SQLite + pliki w folderach + eksport INDEX.md."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

EXTENSIONS = {
    "python": ".py",
    "bash": ".sh",
    "shell": ".sh",
    "javascript": ".js",
    "typescript": ".ts",
    "powershell": ".ps1",
    "go": ".go",
    "rust": ".rs",
}

RUNNABLE = {"python": ["python3"], "bash": ["bash"], "shell": ["bash"], "javascript": ["node"]}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


PL_MAP = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def slugify(text: str, max_len: int = 48) -> str:
    text = text.translate(PL_MAP)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:max_len].rstrip("-")) or "script"


@dataclass
class Script:
    id: int | None
    slug: str
    name: str
    description: str
    language: str
    tags: list[str] = field(default_factory=list)
    prompt: str = ""
    provider: str = ""
    model: str = ""
    path: str = ""
    version: int = 1
    created_at: str = ""
    updated_at: str = ""

    def to_row(self) -> dict:
        d = self.__dict__.copy()
        d["tags"] = ",".join(self.tags)
        return d

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Script":
        d = dict(row)
        d["tags"] = [t for t in (d.get("tags") or "").split(",") if t]
        return cls(**d)


class Catalog:
    def __init__(self, workspace: Path, db_path: Path | None = None):
        self.workspace = Path(workspace)
        self.scripts_dir = self.workspace / "scripts"
        self.db_path = Path(db_path) if db_path else self.workspace / "catalog.sqlite3"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    language TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    prompt TEXT DEFAULT '',
                    provider TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    path TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def add(
        self,
        *,
        name_hint: str,
        code: str,
        language: str = "python",
        description: str = "",
        tags: list[str] | None = None,
        prompt: str = "",
        provider: str = "",
        model: str = "",
    ) -> Script:
        slug = slugify(name_hint)
        with self._connect() as conn:
            base = slug
            n = 2
            while conn.execute("SELECT 1 FROM scripts WHERE slug = ?", (slug,)).fetchone():
                slug = f"{base}-{n}"
                n += 1
            ext = EXTENSIONS.get(language, ".txt")
            folder = self.scripts_dir / language
            folder.mkdir(parents=True, exist_ok=True)
            file_path = folder / f"{slug}{ext}"
            file_path.write_text(code, encoding="utf-8")
            ts = now_iso()
            cur = conn.execute(
                """
                INSERT INTO scripts (slug, name, description, language, tags, prompt, provider, model, path, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    slug,
                    name_hint[:100],
                    description,
                    language,
                    ",".join(tags or []),
                    prompt,
                    provider,
                    model,
                    str(file_path),
                    ts,
                    ts,
                ),
            )
            row = conn.execute("SELECT * FROM scripts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return Script.from_row(row)

    def get(self, ref: str | int) -> Script | None:
        with self._connect() as conn:
            if isinstance(ref, int) or str(ref).isdigit():
                row = conn.execute("SELECT * FROM scripts WHERE id = ?", (int(ref),)).fetchone()
            else:
                row = conn.execute("SELECT * FROM scripts WHERE slug = ?", (str(ref),)).fetchone()
        return Script.from_row(row) if row else None

    def list(self, *, tag: str | None = None, search: str | None = None) -> list[Script]:
        query = "SELECT * FROM scripts"
        clauses, params = [], []
        if tag:
            clauses.append("(',' || tags || ',') LIKE ?")
            params.append(f"%,{tag},%")
        if search:
            like = f"%{search}%"
            clauses.append("(name LIKE ? OR description LIKE ? OR prompt LIKE ? OR tags LIKE ?)")
            params += [like, like, like, like]
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC, id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Script.from_row(r) for r in rows]

    def update_meta(self, ref: str | int, *, name: str | None = None, description: str | None = None, tags: list[str] | None = None) -> Script | None:
        script = self.get(ref)
        if not script:
            return None
        if name is not None:
            script.name = name
        if description is not None:
            script.description = description
        if tags is not None:
            script.tags = tags
        script.updated_at = now_iso()
        with self._connect() as conn:
            conn.execute(
                "UPDATE scripts SET name = ?, description = ?, tags = ?, updated_at = ? WHERE id = ?",
                (script.name, script.description, ",".join(script.tags), script.updated_at, script.id),
            )
        return script

    def delete(self, ref: str | int) -> bool:
        script = self.get(ref)
        if not script:
            return False
        with self._connect() as conn:
            conn.execute("DELETE FROM scripts WHERE id = ?", (script.id,))
        Path(script.path).unlink(missing_ok=True)
        return True

    def read_code(self, script: Script) -> str:
        return Path(script.path).read_text(encoding="utf-8")

    def export_index(self, path: Path | None = None) -> Path:
        path = path or self.workspace / "INDEX.md"
        scripts = self.list()
        lines = ["# Katalog skryptów (ScriptForge)", "", f"Ostatnia aktualizacja: {now_iso()}", "", f"Łącznie: {len(scripts)}", ""]
        by_lang: dict[str, list[Script]] = {}
        for s in scripts:
            by_lang.setdefault(s.language, []).append(s)
        for lang in sorted(by_lang):
            lines.append(f"## {lang} ({len(by_lang[lang])})")
            lines.append("")
            lines.append("| ID | Nazwa | Tagi | Provider | Plik | Utworzono |")
            lines.append("|---|---|---|---|---|---|")
            for s in by_lang[lang]:
                lines.append(
                    f"| {s.id} | {s.name} | {', '.join(s.tags) or '—'} | {s.provider}/{s.model} | `{s.path}` | {s.created_at} |"
                )
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def export_json(self, path: Path | None = None) -> Path:
        path = path or self.workspace / "catalog.json"
        data = [s.__dict__ for s in self.list()]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
