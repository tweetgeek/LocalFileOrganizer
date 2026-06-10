from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml

from .config import Config
from .executor import apply_plan
from .hashing import group_duplicates
from .planner import build_plan
from .report import build_summary, render_console, write_json
from .scanner import scan
from .security import detect_password
from .undo import UndoStore

app = typer.Typer(add_completion=False, help="Local File Organizer (lfo)")


def _resolve_config(
    config: Optional[Path],
    source: Optional[Path],
    dest: Optional[Path],
    mode: Optional[str],
) -> Config:
    data: dict = {}
    if config is not None:
        data = yaml.safe_load(Path(config).read_text(encoding="utf-8")) or {}
    if source is not None:
        data["source_dir"] = str(source)
    if dest is not None:
        data["dest_dir"] = str(dest)
    if mode is not None:
        data["mode"] = mode
    return Config(**data)


@app.command()
def run(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    source: Optional[Path] = typer.Option(None, "--source"),
    dest: Optional[Path] = typer.Option(None, "--dest"),
    mode: Optional[str] = typer.Option(None, "--mode"),
    apply: bool = typer.Option(False, "--apply", help="Wykonaj realne przeniesienia"),
) -> None:
    cfg = _resolve_config(config, source, dest, mode)
    entries = scan(cfg)
    group_duplicates(entries)
    if cfg.password_detection.enabled:
        for e in entries:
            if detect_password(e.path, e.ext, cfg.password_detection.formats):
                e.is_encrypted = True
                e.encrypted_format = e.ext
    plan = build_plan(entries, cfg)

    applied = False
    if apply:
        with UndoStore(cfg.cache.path) as store:
            result = apply_plan(plan, store)
        applied = True
        typer.echo(
            f"Wykonano (run_id={result['run_id']}). Cofnij: "
            f"lfo undo {result['run_id']} --db {cfg.cache.path}"
        )

    summary = build_summary(plan, entries, applied)
    if "console" in cfg.report.format:
        render_console(summary)
    if "json" in cfg.report.format and cfg.report.output is not None:
        write_json(summary, cfg.report.output)


@app.command()
def undo(
    run_id: str = typer.Argument("last", help="ID przebiegu lub 'last'"),
    db: Path = typer.Option(Path("./.lfo_cache.sqlite"), "--db"),
) -> None:
    with UndoStore(db) as store:
        target = store.last_run_id() if run_id == "last" else int(run_id)
        if target is None:
            typer.echo("Brak przebiegow do cofniecia.")
            raise typer.Exit(code=1)
        try:
            result = store.undo_run(target)
        except ValueError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1)
    typer.echo(f"Cofnieto przebieg {target}: przywrocono {result['restored']} plikow.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
