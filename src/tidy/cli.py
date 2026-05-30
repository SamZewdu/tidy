"""Command-line interface for tidy.

Usage:
    tidy-files <folder> [options]     # organize (default action)
    tidy-files organize <folder> ...  # same, explicit
    tidy-files scan [paths...]        # suggest folders worth tidying
    tidy-files undo <folder>          # reverse the most recent run
    tidy-files gui                    # launch the desktop GUI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from . import core
from .scan import suggest

_SUBCOMMANDS = {"organize", "scan", "undo", "gui"}


# --------------------------------------------------------------------------- #
# Rendering helpers (CLI owns all printing).
# --------------------------------------------------------------------------- #
def _render_dryrun(folder: Path, moves, counts) -> None:
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


def _render_scan(results) -> None:
    if not results:
        print("No candidate folders found to scan.")
        return
    print("Folders ranked by how much they could use a tidy:\n")
    for a in results:
        flag = "  ** messy **" if a.messy else ""
        cats = ", ".join(a.categories) if a.categories else "—"
        print(f"  {a.folder}{flag}")
        print(f"      {a.loose_files} loose file(s) across {len(a.categories)} type(s): {cats}")
    messy = [a for a in results if a.messy]
    if messy:
        print("\nSuggested:")
        for a in messy:
            print(f"  tidy-files organize \"{a.folder}\"")
    else:
        print("\nEverything looks reasonably tidy. Nice.")


# --------------------------------------------------------------------------- #
# Subcommand handlers.
# --------------------------------------------------------------------------- #
def _cmd_organize(args) -> int:
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Error: not a directory: {folder}", file=sys.stderr)
        return 2

    category_map = core.load_category_map(args.config)
    managed = core.managed_names(category_map)
    ext_lookup = core.build_ext_lookup(category_map)

    moves, counts = core.plan(
        folder,
        ext_lookup=ext_lookup,
        managed=managed,
        by_date=args.by_date,
        recursive=args.recursive,
        include_hidden=args.include_hidden,
        exclude=tuple(args.exclude),
    )

    if not args.apply:
        _render_dryrun(folder, moves, counts)
        return 0

    log = core.apply_moves(folder, moves, copy=args.copy)
    if not log:
        print(f"Nothing to organize in {folder} — already tidy.")
        return 0
    verb = "Copied" if args.copy else "Moved"
    print(f"{verb} {len(log)} file(s). Undo log: {folder / core.UNDO_FILENAME}")
    if not args.copy:
        print("Reverse with: tidy-files undo \"%s\"" % folder)
    return 0


def _cmd_scan(args) -> int:
    results = suggest(paths=args.paths or None, config=args.config)
    _render_scan(results)
    return 0


def _cmd_undo(args) -> int:
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Error: not a directory: {folder}", file=sys.stderr)
        return 2
    managed = core.managed_names(core.load_category_map(args.config))
    result = core.undo(folder, managed)
    if result is None:
        print(f"No undo log found in {folder}.")
        return 0
    restored, skipped, was_copy = result
    action = "removed" if was_copy else "restored"
    print(f"Undo complete: {restored} file(s) {action}, {skipped} skipped.")
    return 0


def _cmd_gui(args) -> int:
    from .gui import main as gui_main  # lazy import so CLI works headless

    gui_main()
    return 0


# --------------------------------------------------------------------------- #
# Parser.
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tidy-files",
        description="Rule-based folder auto-organizer (dry-run by default).",
    )
    parser.add_argument("--version", action="version", version=f"tidy-files {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--config", metavar="FILE", help="JSON overriding/extending the category map.")

    p_org = sub.add_parser("organize", help="Organize a folder into category subfolders.")
    p_org.add_argument("folder", help="Folder to organize.")
    p_org.add_argument("--apply", action="store_true", help="Actually move files (default: dry-run).")
    p_org.add_argument("--by-date", action="store_true", help="Nest as Category/YYYY/MM using mtime.")
    p_org.add_argument("--copy", action="store_true", help="Copy instead of move (keep originals).")
    p_org.add_argument("--recursive", action="store_true", help="Descend into sub-directories.")
    p_org.add_argument("--include-hidden", action="store_true", help="Include dotfiles.")
    p_org.add_argument("--exclude", action="append", default=[], metavar="PATTERN",
                       help="Glob to skip (repeatable).")
    add_common(p_org)
    p_org.set_defaults(func=_cmd_organize)

    p_scan = sub.add_parser("scan", help="Suggest which folders are worth tidying.")
    p_scan.add_argument("paths", nargs="*", help="Folders to assess (default: Downloads, Desktop, Documents).")
    add_common(p_scan)
    p_scan.set_defaults(func=_cmd_scan)

    p_undo = sub.add_parser("undo", help="Reverse the most recent run in a folder.")
    p_undo.add_argument("folder", help="Folder whose last run to undo.")
    add_common(p_undo)
    p_undo.set_defaults(func=_cmd_undo)

    p_gui = sub.add_parser("gui", help="Launch the desktop GUI.")
    p_gui.set_defaults(func=_cmd_gui)

    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Convenience: `tidy <folder>` is shorthand for `tidy organize <folder>`.
    if argv and argv[0] not in _SUBCOMMANDS and argv[0] not in ("-h", "--help", "--version"):
        argv = ["organize"] + argv
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
