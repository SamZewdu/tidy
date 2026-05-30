"""Scan common locations and suggest which folders are worth tidying."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .core import (
    UNDO_FILENAME,
    build_ext_lookup,
    category_for,
    load_category_map,
    managed_names,
)

# Folders most likely to accumulate loose files.
DEFAULT_CANDIDATES = ["~/Downloads", "~/Desktop", "~/Documents"]

# A folder is flagged "messy" once it crosses either threshold.
MESSY_FILE_COUNT = 10
MESSY_CATEGORY_COUNT = 3


@dataclass
class Assessment:
    folder: Path
    loose_files: int
    categories: list[str] = field(default_factory=list)
    score: int = 0

    @property
    def messy(self) -> bool:
        return self.loose_files >= MESSY_FILE_COUNT or len(self.categories) >= MESSY_CATEGORY_COUNT


def _loose_files(folder: Path, managed: set[str]) -> list[Path]:
    """Top-level files not already filed into a category folder (and not hidden)."""
    files: list[Path] = []
    for entry in folder.glob("*"):
        if not entry.is_file():
            continue
        if entry.name == UNDO_FILENAME or entry.name.startswith("."):
            continue
        files.append(entry)
    return files


def assess(folder: Path, ext_lookup: dict[str, str], managed: set[str]) -> Assessment:
    files = _loose_files(folder, managed)
    cats = sorted({category_for(f, ext_lookup) for f in files})
    # Messiness = volume of loose files plus how many distinct categories are jumbled together.
    score = len(files) + 2 * len(cats)
    return Assessment(folder=folder, loose_files=len(files), categories=cats, score=score)


def suggest(
    paths: list[str] | None = None, config: str | None = None
) -> list[Assessment]:
    """Assess candidate folders and return them ranked messiest-first."""
    category_map = load_category_map(config)
    ext_lookup = build_ext_lookup(category_map)
    managed = managed_names(category_map)

    candidates = paths if paths else DEFAULT_CANDIDATES
    results: list[Assessment] = []
    for raw in candidates:
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            continue
        results.append(assess(folder, ext_lookup, managed))
    results.sort(key=lambda a: a.score, reverse=True)
    return results
