"""Core organizing logic — categorization, planning, applying, and undo.

This module is I/O-light: functions return structured results instead of
printing, so the CLI, scan, and GUI can all reuse them.
"""

from __future__ import annotations

import fnmatch
import json
import shutil
from datetime import datetime
from pathlib import Path

UNDO_FILENAME = ".organize-undo.json"

# Default category -> file extensions (lowercase, no leading dot).
DEFAULT_CATEGORY_MAP: dict[str, list[str]] = {
    "Images": ["jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "heic", "tiff", "ico"],
    "Videos": ["mp4", "mov", "avi", "mkv", "webm", "flv", "wmv", "m4v"],
    "Audio": ["mp3", "wav", "flac", "aac", "ogg", "m4a", "wma"],
    "Documents": ["pdf", "doc", "docx", "txt", "md", "rtf", "odt", "pages", "epub"],
    "Spreadsheets": ["xls", "xlsx", "csv", "ods", "numbers"],
    "Presentations": ["ppt", "pptx", "key", "odp"],
    "Archives": ["zip", "tar", "gz", "tgz", "rar", "7z", "bz2", "xz"],
    "Installers": ["dmg", "pkg", "app", "exe", "msi"],
    "Code": [
        "py", "js", "ts", "tsx", "jsx", "java", "c", "cpp", "h", "go", "rs",
        "rb", "php", "sh", "html", "css", "json", "yaml", "yml", "toml",
    ],
    "Fonts": ["ttf", "otf", "woff", "woff2"],
}
OTHER_CATEGORY = "Other"


def load_category_map(config_path: str | None = None) -> dict[str, list[str]]:
    """Built-in map, optionally merged with a user JSON of {Category: [ext, ...]}."""
    category_map = {k: list(v) for k, v in DEFAULT_CATEGORY_MAP.items()}
    if config_path:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("--config JSON must be an object of {Category: [ext, ...]}")
        for category, exts in data.items():
            category_map[category] = [str(e).lower().lstrip(".") for e in exts]
    return category_map


def build_ext_lookup(category_map: dict[str, list[str]]) -> dict[str, str]:
    """Reverse map: extension -> category. Later categories win on conflict."""
    lookup: dict[str, str] = {}
    for category, exts in category_map.items():
        for ext in exts:
            lookup[ext.lower().lstrip(".")] = category
    return lookup


def managed_names(category_map: dict[str, list[str]]) -> set[str]:
    """The set of folder names this tool manages (categories + Other)."""
    return set(category_map) | {OTHER_CATEGORY}


def category_for(path: Path, ext_lookup: dict[str, str]) -> str:
    ext = path.suffix.lower().lstrip(".")
    if not ext:
        return OTHER_CATEGORY
    return ext_lookup.get(ext, OTHER_CATEGORY)


def iter_candidates(
    folder: Path,
    *,
    recursive: bool = False,
    include_hidden: bool = False,
    exclude: tuple[str, ...] = (),
    managed: set[str],
) -> list[Path]:
    """Yield files eligible for organizing, applying skip rules."""
    walker = folder.rglob("*") if recursive else folder.glob("*")
    candidates: list[Path] = []
    for entry in walker:
        if not entry.is_file():
            continue
        if entry.name == UNDO_FILENAME:
            continue
        rel_parts = entry.relative_to(folder).parts
        if not include_hidden and any(part.startswith(".") for part in rel_parts):
            continue
        # Idempotency: skip anything already inside a managed category folder.
        if len(rel_parts) > 1 and rel_parts[0] in managed:
            continue
        if any(fnmatch.fnmatch(entry.name, pat) for pat in exclude):
            continue
        candidates.append(entry)
    return candidates


def resolve_collision(dest: Path, taken: set[Path]) -> Path:
    """Return a non-colliding path by appending ' (n)' before the suffix."""
    if dest not in taken and not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 1
    while True:
        candidate = dest.with_name(f"{stem} ({n}){suffix}")
        if candidate not in taken and not candidate.exists():
            return candidate
        n += 1


def plan(
    folder: Path,
    *,
    ext_lookup: dict[str, str],
    managed: set[str],
    by_date: bool = False,
    recursive: bool = False,
    include_hidden: bool = False,
    exclude: tuple[str, ...] = (),
) -> tuple[list[tuple[Path, Path]], dict[str, int]]:
    """Return (moves, counts) where moves is a list of (src, dest)."""
    candidates = iter_candidates(
        folder,
        recursive=recursive,
        include_hidden=include_hidden,
        exclude=exclude,
        managed=managed,
    )
    moves: list[tuple[Path, Path]] = []
    counts: dict[str, int] = {}
    taken: set[Path] = set()
    for src in sorted(candidates):
        category = category_for(src, ext_lookup)
        dest_dir = folder / category
        if by_date:
            mtime = datetime.fromtimestamp(src.stat().st_mtime)
            dest_dir = dest_dir / f"{mtime.year:04d}" / f"{mtime.month:02d}"
        dest = resolve_collision(dest_dir / src.name, taken)
        if src.resolve() == dest.resolve():
            continue
        taken.add(dest)
        moves.append((src, dest))
        counts[category] = counts.get(category, 0) + 1
    return moves, counts


def apply_moves(
    folder: Path, moves: list[tuple[Path, Path]], *, copy: bool = False
) -> list[dict]:
    """Move (or copy) files and write an undo log. Returns the log records."""
    log: list[dict] = []
    for src, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if copy:
            shutil.copy2(src, dest)
        else:
            shutil.move(str(src), str(dest))
        log.append({"from": str(src), "to": str(dest), "copied": copy})
    if log:
        undo_path = folder / UNDO_FILENAME
        undo_path.write_text(
            json.dumps(
                {"timestamp": datetime.now().isoformat(), "copy": copy, "moves": log},
                indent=2,
            ),
            encoding="utf-8",
        )
    return log


def prune_empty_dirs(folder: Path, managed: set[str]) -> None:
    for category in managed:
        root = folder / category
        if not root.exists():
            continue
        for sub in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()
        if root.is_dir() and not any(root.iterdir()):
            root.rmdir()


def undo(folder: Path, managed: set[str]) -> tuple[int, int, bool] | None:
    """Reverse the most recent run. Returns (restored, skipped, was_copy) or None."""
    undo_path = folder / UNDO_FILENAME
    if not undo_path.exists():
        return None
    data = json.loads(undo_path.read_text(encoding="utf-8"))
    was_copy = data.get("copy", False)
    restored = skipped = 0
    for record in reversed(data["moves"]):
        dest = Path(record["to"])
        src = Path(record["from"])
        if not dest.exists():
            skipped += 1
            continue
        if was_copy:
            dest.unlink()  # remove the copy; original was never moved
            restored += 1
            continue
        if src.exists():
            skipped += 1
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(src))
        restored += 1
    prune_empty_dirs(folder, managed)
    undo_path.unlink()
    return restored, skipped, was_copy
