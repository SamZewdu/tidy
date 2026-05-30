"""A small tkinter desktop GUI for tidy.

Pick a folder, preview the planned moves (dry-run), then Apply or Undo.
Reuses the same core functions as the CLI, so behavior is identical.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import core
from .scan import suggest


class TidyApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("tidy — folder organizer")
        root.minsize(640, 460)

        self.folder_var = tk.StringVar()
        self.by_date = tk.BooleanVar(value=False)
        self.copy = tk.BooleanVar(value=False)
        self.recursive = tk.BooleanVar(value=False)
        self.include_hidden = tk.BooleanVar(value=False)
        self._moves: list[tuple[Path, Path]] = []

        self._build()

    # ----- layout ----- #
    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Folder:").pack(side="left")
        ttk.Entry(top, textvariable=self.folder_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Browse…", command=self._browse).pack(side="left")
        ttk.Button(top, text="Suggest…", command=self._suggest).pack(side="left", padx=(6, 0))

        opts = ttk.Frame(self.root)
        opts.pack(fill="x", **pad)
        ttk.Checkbutton(opts, text="By date (YYYY/MM)", variable=self.by_date).pack(side="left")
        ttk.Checkbutton(opts, text="Copy (keep originals)", variable=self.copy).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="Recursive", variable=self.recursive).pack(side="left")
        ttk.Checkbutton(opts, text="Include hidden", variable=self.include_hidden).pack(side="left", padx=8)

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", **pad)
        ttk.Button(actions, text="Preview", command=self._preview).pack(side="left")
        ttk.Button(actions, text="Apply", command=self._apply).pack(side="left", padx=6)
        ttk.Button(actions, text="Undo last run", command=self._undo).pack(side="left")

        cols = ("file", "dest")
        self.tree = ttk.Treeview(self.root, columns=cols, show="headings", height=14)
        self.tree.heading("file", text="File")
        self.tree.heading("dest", text="Will move to")
        self.tree.column("file", width=240)
        self.tree.column("dest", width=360)
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)

        self.status = ttk.Label(self.root, text="Pick a folder and click Preview.", anchor="w")
        self.status.pack(fill="x", padx=8, pady=(0, 8))

    # ----- helpers ----- #
    def _folder(self) -> Path | None:
        raw = self.folder_var.get().strip()
        if not raw:
            messagebox.showwarning("tidy", "Choose a folder first.")
            return None
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            messagebox.showerror("tidy", f"Not a folder:\n{folder}")
            return None
        return folder.resolve()

    def _set_status(self, text: str) -> None:
        self.status.config(text=text)

    def _clear_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def _maps(self):
        category_map = core.load_category_map()
        return core.build_ext_lookup(category_map), core.managed_names(category_map)

    # ----- actions ----- #
    def _browse(self) -> None:
        chosen = filedialog.askdirectory()
        if chosen:
            self.folder_var.set(chosen)

    def _suggest(self) -> None:
        results = suggest()
        if not results:
            messagebox.showinfo("tidy", "No common folders found to suggest.")
            return
        top = results[0]
        self.folder_var.set(str(top.folder))
        tag = "looks messy" if top.messy else "looks okay"
        self._set_status(f"Suggested: {top.folder} ({top.loose_files} loose files — {tag}). Click Preview.")

    def _preview(self) -> None:
        folder = self._folder()
        if not folder:
            return
        ext_lookup, managed = self._maps()
        self._moves, counts = core.plan(
            folder,
            ext_lookup=ext_lookup,
            managed=managed,
            by_date=self.by_date.get(),
            recursive=self.recursive.get(),
            include_hidden=self.include_hidden.get(),
        )
        self._clear_tree()
        for src, dest in self._moves:
            self.tree.insert("", "end", values=(src.name, str(dest.relative_to(folder))))
        if self._moves:
            summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
            self._set_status(f"{len(self._moves)} file(s) planned — {summary}. Click Apply to move.")
        else:
            self._set_status(f"Nothing to organize in {folder} — already tidy.")

    def _apply(self) -> None:
        folder = self._folder()
        if not folder:
            return
        if not self._moves:
            messagebox.showinfo("tidy", "Click Preview first to see what will move.")
            return
        verb = "Copy" if self.copy.get() else "Move"
        if not messagebox.askyesno("tidy", f"{verb} {len(self._moves)} file(s)?"):
            return
        log = core.apply_moves(folder, self._moves, copy=self.copy.get())
        self._moves = []
        self._clear_tree()
        done = "Copied" if self.copy.get() else "Moved"
        self._set_status(f"{done} {len(log)} file(s). Use 'Undo last run' to reverse.")

    def _undo(self) -> None:
        folder = self._folder()
        if not folder:
            return
        _, managed = self._maps()
        result = core.undo(folder, managed)
        if result is None:
            messagebox.showinfo("tidy", "No undo log found in that folder.")
            return
        restored, skipped, was_copy = result
        action = "removed" if was_copy else "restored"
        self._clear_tree()
        self._set_status(f"Undo complete: {restored} {action}, {skipped} skipped.")


def main() -> None:
    root = tk.Tk()
    TidyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
