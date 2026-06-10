from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


class AICache:
    def __init__(self, db_path: Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS ai_cache ("
            "key TEXT PRIMARY KEY, category TEXT, confidence REAL, suggestion TEXT)"
        )
        self.conn.commit()

    @staticmethod
    def make_key(file_hash: str, model: str, taxonomy: dict[str, str]) -> str:
        tax = hashlib.sha256(
            json.dumps(taxonomy, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        return f"{file_hash}:{model}:{tax}"

    def get(self, key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT category, confidence, suggestion FROM ai_cache WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return {"category": row[0], "confidence": row[1], "suggested_name": row[2]}

    def put(self, key: str, result: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO ai_cache (key, category, confidence, suggestion) "
            "VALUES (?, ?, ?, ?)",
            (
                key,
                result.get("category"),
                float(result.get("confidence") or 0.0),
                result.get("suggested_name"),
            ),
        )
        self.conn.commit()
