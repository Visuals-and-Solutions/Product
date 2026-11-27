"""Panel webowy ScriptForge (Flask, nasłuch wyłącznie na 127.0.0.1)."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for

from .generator import LANG_ALIASES, generate_and_save
from .providers import ProviderError, build_provider, provider_status
from .storage import Catalog


def create_app(workspace: Path | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    def get_catalog() -> Catalog:
        if workspace:
            return Catalog(Path(workspace))
        from .config import Settings

        s = Settings.from_env()
        return Catalog(s.workspace, s.db_path)

    @app.context_processor
    def inject_globals():
        return {"provider_rows": provider_status()}

    @app.get("/")
    def index():
        catalog = get_catalog()
        tag = request.args.get("tag") or None
        search = request.args.get("q") or None
        scripts = catalog.list(tag=tag, search=search)
        return render_template("index.html", scripts=scripts, tag=tag or "", search=search or "")

    @app.get("/scripts/<ref>")
    def detail(ref: str):
        catalog = get_catalog()
        script = catalog.get(ref)
        if not script:
            abort(404)
        return render_template("detail.html", script=script, code=catalog.read_code(script))

    @app.route("/generate", methods=["GET", "POST"])
    def generate():
        catalog = get_catalog()
        if request.method == "POST":
            task = (request.form.get("task") or "").strip()
            provider_name = request.form.get("provider") or "google"
            model = request.form.get("model") or None
            language = request.form.get("language") or "python"
            tags = [t.strip() for t in (request.form.get("tags") or "").split(",") if t.strip()]
            error = None
            script = None
            if not task:
                error = "Podaj treść zadania."
            else:
                try:
                    provider = build_provider(provider_name, model)
                    _, script = generate_and_save(catalog, provider, task, language=language, tags=tags)
                    catalog.export_index()
                except ProviderError as exc:
                    error = str(exc)
            if script and not error:
                return redirect(url_for("detail", ref=script.slug))
            return render_template(
                "generate.html",
                error=error,
                task=task,
                provider=provider_name,
                model=model or "",
                language=language,
                tags=request.form.get("tags", ""),
                languages=sorted(set(LANG_ALIASES.values())),
            )
        return render_template(
            "generate.html",
            error=None,
            task="",
            provider="google",
            model="",
            language="python",
            tags="",
            languages=sorted(set(LANG_ALIASES.values())),
        )

    @app.post("/scripts/<ref>/delete")
    def delete(ref: str):
        catalog = get_catalog()
        catalog.delete(ref)
        catalog.export_index()
        return redirect(url_for("index"))

    @app.get("/api/scripts")
    def api_scripts():
        catalog = get_catalog()
        scripts = catalog.list(tag=request.args.get("tag"), search=request.args.get("q"))
        return {"scripts": [s.__dict__ for s in scripts]}

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=7860, debug=False)
