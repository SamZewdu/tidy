# organize.py — folder auto-organizer

A small, dependency-free Python 3 CLI that tidies a folder by filing loose files into
category subfolders (Images, Documents, Code, Archives, …) based on file extension,
optionally split further by date.

Requires Python 3.9+ — no third-party packages.

**Safe by default:** it runs as a *dry-run* (prints what it would do, changes nothing)
unless you pass `--apply`. Every applied run writes an undo log so it can be reversed.

## Usage

```bash
# Preview only — nothing is moved
python3 organize.py ~/Downloads

# Actually move files into category folders
python3 organize.py ~/Downloads --apply

# Reverse the most recent run in that folder
python3 organize.py ~/Downloads --undo
```

### Options

| Flag | Effect |
|------|--------|
| `--apply` | Actually move files. Without it, dry-run preview only. |
| `--by-date` | Nest inside each category as `Category/YYYY/MM` (by file modified time). |
| `--copy` | Copy instead of move (originals stay in place). |
| `--recursive` | Also descend into sub-directories. |
| `--include-hidden` | Include dotfiles (skipped by default). |
| `--exclude PATTERN` | Glob to skip, repeatable. e.g. `--exclude '*.part' --exclude '*.crdownload'`. |
| `--undo` | Reverse the most recent run in the folder, then exit. |
| `--config FILE` | JSON that overrides/extends the category map. |

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
- **Undo** — `--apply`/`--copy` write `.organize-undo.json` in the target folder. `--undo`
  reads it, moves files back (or deletes copies), prunes now-empty category folders, and
  removes the log. The log holds only the most recent run.

## License

MIT — see [LICENSE](LICENSE).
