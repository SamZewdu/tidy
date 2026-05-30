# tidy — folder auto-organizer

A small, dependency-free Python tool that tidies a folder by filing loose files into
category subfolders (Images, Documents, Code, Archives, …) based on file extension —
optionally split further by date. Comes as a **CLI**, a **scan** mode that suggests which
folders need attention, and a simple **desktop GUI**.

Pure standard library (CLI + GUI both). Requires Python 3.9+.

The command is **`tidy-files`** (the plain name `tidy` belongs to macOS's built-in HTML Tidy).

**Safe by default:** organizing runs as a *dry-run* (shows what it would do, changes
nothing) unless you pass `--apply`. Every applied run writes an undo log so it can be reversed.

## Install

```bash
# Recommended: isolated global install (gives you `tidy-files` and `tidy-files-gui` commands)
pipx install git+https://github.com/SamZewdu/tidy.git

# Or from a local clone
git clone https://github.com/SamZewdu/tidy.git && cd tidy
pipx install .        # or:  pip install --user .
```

Don't have pipx? Install it once with `brew install pipx && pipx ensurepath` (macOS) or
`python3 -m pip install --user pipx`. Or run from a clone via an editable install:

```bash
pip install -e .
tidy-files --help
```

## Usage

```bash
tidy-files scan                   # which folders are messy? (Downloads, Desktop, Documents)
tidy-files ~/Downloads            # dry-run preview — nothing moves
tidy-files ~/Downloads --apply    # actually organize
tidy-files undo ~/Downloads       # reverse the most recent run
tidy-files gui                    # launch the desktop app
```

`tidy-files ~/Downloads` is shorthand for `tidy-files organize ~/Downloads`.

### Commands

| Command | What it does |
|---------|--------------|
| `tidy-files organize <folder>` | Sort loose files into category subfolders. Dry-run unless `--apply`. |
| `tidy-files scan [paths...]` | Rank folders by messiness and suggest which to tidy. Defaults to Downloads/Desktop/Documents. |
| `tidy-files undo <folder>` | Reverse the most recent run in that folder. |
| `tidy-files gui` | Open the desktop GUI (also installed as the `tidy-files-gui` command). |

### `organize` options

| Flag | Effect |
|------|--------|
| `--apply` | Actually move files. Without it, dry-run preview only. |
| `--by-date` | Nest inside each category as `Category/YYYY/MM` (by file modified time). |
| `--copy` | Copy instead of move (originals stay in place). |
| `--recursive` | Also descend into sub-directories. |
| `--include-hidden` | Include dotfiles (skipped by default). |
| `--exclude PATTERN` | Glob to skip, repeatable. e.g. `--exclude '*.part' --exclude '*.crdownload'`. |
| `--config FILE` | JSON that overrides/extends the category map. |

## GUI

`tidy-files gui` (or the `tidy-files-gui` launcher) opens a window where you pick a folder, hit
**Preview** to see the exact planned moves, then **Apply** or **Undo**. A **Suggest…**
button fills in the messiest common folder for you. It calls the same core as the CLI,
so behavior is identical.

## Categories

Files are matched by extension into: **Images, Videos, Audio, Documents, Spreadsheets,
Presentations, Archives, Installers, Code, Fonts**. Anything unmatched (or extension-less)
goes to **Other**.

### Custom categories

Pass `--config map.json` to override or add categories. Keys are folder names, values are
lists of extensions:

```json
{
  "Design": ["psd", "ai", "sketch", "fig"],
  "Data": ["csv", "parquet", "json"]
}
```

Provided categories replace the built-in entry of the same name; new categories are added.

## Safety details

- **Files only** — directories in the target are never moved.
- **Idempotent** — files already inside a managed category folder are skipped, so re-running
  is a no-op.
- **No clobbering** — name collisions get a ` (1)`, ` (2)`, … suffix.
- **Undo** — `--apply`/`--copy` write `.organize-undo.json` in the target folder. `tidy-files undo`
  reads it, moves files back (or deletes copies), prunes now-empty category folders, and
  removes the log. The log holds only the most recent run.

## Project layout

```
src/tidy/
├── core.py   # categorization, plan, apply, undo (shared engine)
├── scan.py   # folder-suggestion logic
├── cli.py    # command-line interface
└── gui.py    # tkinter desktop app
```

## License

MIT — see [LICENSE](LICENSE).
