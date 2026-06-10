from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path


class UndoStore:
    def __init__(self, db_path: Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, ts REAL, done INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS moves (run_id INTEGER, source TEXT, dest TEXT);
            CREATE TABLE IF NOT EXISTS dirs (run_id INTEGER, path TEXT);
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "UndoStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def start_run(self) -> int:
        cur = self.conn.execute("INSERT INTO runs (ts) VALUES (?)", (time.time(),))
        self.conn.commit()
        return int(cur.lastrowid)

    def record_move(self, run_id: int, source: Path, dest: Path) -> None:
        self.conn.execute(
            "INSERT INTO moves VALUES (?, ?, ?)", (run_id, str(source), str(dest))
        )
        self.conn.commit()

    def record_dir(self, run_id: int, path: Path) -> None:
        self.conn.execute("INSERT INTO dirs VALUES (?, ?)", (run_id, str(path)))
        self.conn.commit()

    def finish_run(self, run_id: int) -> None:
        self.conn.execute("UPDATE runs SET done = 1 WHERE id = ?", (run_id,))
        self.conn.commit()

    def last_run_id(self) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return int(row[0]) if row else None

    def undo_run(self, run_id: int) -> dict:
        if self.conn.execute(
            "SELECT 1 FROM runs WHERE id = ?", (run_id,)
        ).fetchone() is None:
            raise ValueError(f"przebieg o id {run_id} nie istnieje")
        moves = self.conn.execute(
            "SELECT source, dest FROM moves WHERE run_id = ? ORDER BY rowid DESC",
            (run_id,),
        ).fetchall()
        restored = 0
        for source, dest in moves:
            src_p, dst_p = Path(source), Path(dest)
            if dst_p.exists():
                src_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst_p), str(src_p))
                restored += 1
        dirs = [
            Path(r[0])
            for r in self.conn.execute(
                "SELECT path FROM dirs WHERE run_id = ?", (run_id,)
            ).fetchall()
        ]
        for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
            try:
                d.rmdir()  # usuwa tylko puste
            except OSError:
                pass
        self.conn.execute("DELETE FROM moves WHERE run_id = ?", (run_id,))
        self.conn.execute("DELETE FROM dirs WHERE run_id = ?", (run_id,))
        self.conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        self.conn.commit()
        return {"restored": restored}
