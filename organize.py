#!/usr/bin/env python3
"""organize.py — rule-based folder auto-organizer.

Sweeps a folder and files loose files into category subfolders (Images, Documents,
Code, Archives, ...) by extension, optionally split further by date. Dry-run by
default; only moves files when --apply is given, and writes an undo log so a run
can be reversed with --undo.

Standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import sys
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


def load_category_map(config_path: str | None) -> dict[str, list[str]]:
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


def category_for(path: Path, ext_lookup: dict[str, str]) -> str:
    ext = path.suffix.lower().lstrip(".")
    if not ext:
        return OTHER_CATEGORY
    return ext_lookup.get(ext, OTHER_CATEGORY)


def iter_candidates(
    folder: Path,
    recursive: bool,
    include_hidden: bool,
    exclude: list[str],
    managed_names: set[str],
    self_path: Path,
) -> list[Path]:
    """Yield files eligible for organizing, applying skip rules."""
    walker = folder.rglob("*") if recursive else folder.glob("*")
    candidates: list[Path] = []
    for entry in walker:
        if not entry.is_file():
            continue
        if entry.resolve() == self_path:
            continue
        if entry.name == UNDO_FILENAME:
            continue
        if not include_hidden and any(part.startswith(".") for part in entry.relative_to(folder).parts):
            continue
        # Idempotency: skip anything already inside a managed category folder.
        rel_parts = entry.relative_to(folder).parts
        if len(rel_parts) > 1 and rel_parts[0] in managed_names:
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


def plan(folder: Path, args, ext_lookup: dict[str, str], managed_names: set[str]):
    """Return (moves, counts) where moves is a list of (src, dest)."""
    self_path = Path(__file__).resolve()
    candidates = iter_candidates(
        folder, args.recursive, args.include_hidden, args.exclude, managed_names, self_path
    )
    moves: list[tuple[Path, Path]] = []
    counts: dict[str, int] = {}
    taken: set[Path] = set()
    for src in sorted(candidates):
        category = category_for(src, ext_lookup)
        dest_dir = folder / category
        if args.by_date:
            mtime = datetime.fromtimestamp(src.stat().st_mtime)
            dest_dir = dest_dir / f"{mtime.year:04d}" / f"{mtime.month:02d}"
        dest = resolve_collision(dest_dir / src.name, taken)
        if src.resolve() == dest.resolve():
            continue
        taken.add(dest)
        moves.append((src, dest))
        counts[category] = counts.get(category, 0) + 1
    return moves, counts


def render_dryrun(folder: Path, moves, counts) -> None:
    if not moves:
        print(f"Nothing to organize in {folder} — already tidy.")
        return
    print(f"Planned moves for {folder}:\n")
    for src, dest in moves:
        print(f"  {src.name}  ->  {dest.relative_to(folder)}")
    print("\nSummary:")
    for category in sorted(counts):
        print(f"  {category}: {counts[category]}")
    print(f"\n{len(moves)} file(s) — dry-run, nothing moved. Pass --apply to move.")


def apply_moves(folder: Path, moves, copy: bool) -> None:
    if not moves:
        print(f"Nothing to organize in {folder} — already tidy.")
        return
    log: list[dict[str, str]] = []
    for src, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if copy:
            shutil.copy2(src, dest)
        else:
            shutil.move(str(src), str(dest))
        log.append({"from": str(src), "to": str(dest), "copied": copy})
    undo_path = folder / UNDO_FILENAME
    undo_path.write_text(
        json.dumps(
            {"timestamp": datetime.now().isoformat(), "copy": copy, "moves": log},
            indent=2,
        ),
        encoding="utf-8",
    )
    verb = "Copied" if copy else "Moved"
    print(f"{verb} {len(moves)} file(s). Undo log: {undo_path}")
    if not copy:
        print("Reverse with: --undo")


def prune_empty_dirs(folder: Path, managed_names: set[str]) -> None:
    for category in managed_names:
        root = folder / category
        if not root.exists():
            continue
        for sub in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()
        if root.is_dir() and not any(root.iterdir()):
            root.rmdir()


def undo(folder: Path, managed_names: set[str]) -> None:
    undo_path = folder / UNDO_FILENAME
    if not undo_path.exists():
        print(f"No undo log found at {undo_path}.")
        return
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
    prune_empty_dirs(folder, managed_names)
    undo_path.unlink()
    action = "removed" if was_copy else "restored"
    print(f"Undo complete: {restored} file(s) {action}, {skipped} skipped.")


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="organize.py",
        description="Rule-based folder auto-organizer (dry-run by default).",
    )
    p.add_argument("folder", help="Folder to organize.")
    p.add_argument("--apply", action="store_true", help="Actually move files (default: dry-run preview).")
    p.add_argument("--by-date", action="store_true", help="Nest as Category/YYYY/MM using file mtime.")
    p.add_argument("--copy", action="store_true", help="Copy instead of move (originals stay put).")
    p.add_argument("--recursive", action="store_true", help="Descend into sub-directories.")
    p.add_argument("--include-hidden", action="store_true", help="Include dotfiles.")
    p.add_argument("--exclude", action="append", default=[], metavar="PATTERN",
                   help="Glob to skip (repeatable), e.g. --exclude '*.part'.")
    p.add_argument("--undo", action="store_true", help="Reverse the most recent run in this folder.")
    p.add_argument("--config", metavar="FILE", help="JSON overriding/extending the category map.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Error: not a directory: {folder}", file=sys.stderr)
        return 2

    category_map = load_category_map(args.config)
    managed_names = set(category_map) | {OTHER_CATEGORY}

    if args.undo:
        undo(folder, managed_names)
        return 0

    ext_lookup = build_ext_lookup(category_map)
    moves, counts = plan(folder, args, ext_lookup, managed_names)

    if args.apply:
        apply_moves(folder, moves, args.copy)
    else:
        render_dryrun(folder, moves, counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
