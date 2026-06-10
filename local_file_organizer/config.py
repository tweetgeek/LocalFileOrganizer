from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DedupConfig(BaseModel):
    method: Literal["hash"] = "hash"
    action: Literal["quarantine", "report_only"] = "quarantine"


class PasswordConfig(BaseModel):
    enabled: bool = True
    formats: list[str] = Field(
        default_factory=lambda: ["pdf", "zip", "7z", "rar", "docx", "xlsx"]
    )


class ReportConfig(BaseModel):
    format: list[Literal["console", "json"]] = Field(
        default_factory=lambda: ["console"]
    )
    output: Path | None = None


class CacheConfig(BaseModel):
    enabled: bool = True
    path: Path = Path("./.lfo_cache.sqlite")


class AIConfig(BaseModel):
    enabled: bool = False
    provider: Literal["ollama"] = "ollama"
    endpoint: str = "http://localhost:11434"
    model: str = "llama3.2"
    extensions: list[str] = Field(
        default_factory=lambda: ["pdf", "txt", "md", "docx"]
    )
    max_chars: int = Field(default=4000, gt=0)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    on_error: Literal["fallback", "abort"] = "fallback"
    allow_suggestions: bool = True
    taxonomy: dict[str, str] = Field(default_factory=dict)


class Config(BaseModel):
    # extra='ignore' -> nieznane klucze sa pomijane
    model_config = ConfigDict(extra="ignore")

    source_dir: Path
    dest_dir: Path
    mode: Literal["type", "category"] = "category"
    recursive: bool = True
    max_depth: int = 5
    ignore: list[str] = Field(default_factory=lambda: [".git", "node_modules"])
    follow_symlinks: bool = False
    categories: dict[str, list[str]] = Field(default_factory=dict)
    unknown_dir: str = "unsorted"
    duplicates_dir: str = "duplikaty"
    review_dir: str = "do_przejrzenia"
    conflict: Literal["rename", "skip"] = "rename"
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    password_detection: PasswordConfig = Field(default_factory=PasswordConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    ai: AIConfig = Field(default_factory=AIConfig)

    @field_validator("source_dir")
    @classmethod
    def _source_exists(cls, v: Path) -> Path:
        if not v.exists() or not v.is_dir():
            raise ValueError(f"source_dir nie istnieje lub nie jest katalogiem: {v}")
        return v

    @model_validator(mode="after")
    def _paths_differ(self) -> "Config":
        if self.source_dir.resolve() == self.dest_dir.resolve():
            raise ValueError("source_dir i dest_dir nie moga byc tym samym katalogiem")
        return self


def load_config(path: Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config(**data)
