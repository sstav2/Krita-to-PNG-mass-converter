#!/usr/bin/env python3
"""
KRA → PNG Batch Converter
Converts Krita (.kra) files to PNG by extracting the merged image inside each archive.

0. have python

1. pip install pillow ( if it doesnt work - pip -m install pillow )
2. py kra_to_png_converter.py

"""

import os
import zipfile
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from PIL import Image
import io


# ── Palette ──────────────────────────────────────────────────────────────────
BG        = "#1A1A2E"
SURFACE   = "#16213E"
CARD      = "#0F3460"
ACCENT    = "#E94560"
ACCENT2   = "#533483"
FG        = "#E0E0E0"
FG_DIM    = "#8892A4"
SUCCESS   = "#4CAF50"
WARNING   = "#FF9800"
FONT_UI   = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_BIG  = ("Segoe UI", 13, "bold")
FONT_MONO = ("Consolas", 9)

# ─────────────────────────────────────────────────────────────────────────────

def extract_kra_to_png(kra_path: Path, out_dir: Path) -> tuple[bool, str]:
    """Extract the merged PNG from a .kra file."""
    try:
        with zipfile.ZipFile(kra_path, "r") as z:
            names = z.namelist()
            # Krita stores the flat composite as mergedimage.png
            target = next((n for n in names if n.lower() == "mergedimage.png"), None)
            if target is None:
                return False, "No mergedimage.png found inside archive"
            data = z.read(target)

        img = Image.open(io.BytesIO(data))
        out_path = out_dir / (kra_path.stem + ".png")
        img.save(out_path, "PNG")
        return True, str(out_path)
    except zipfile.BadZipFile:
        return False, "Not a valid .kra file"
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KRA → PNG Converter")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(700, 540)

        self._input_dir  = tk.StringVar()
        self._output_dir = tk.StringVar()
        self._same_dir   = tk.BooleanVar(value=True)
        self._status     = tk.StringVar(value="Choose a folder to get started.")
        self._running    = False
        self._files: list[Path] = []

        self._build()
        self.geometry("800x600")
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=CARD, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="KRA → PNG  Batch Converter", font=("Segoe UI", 16, "bold"),
                 bg=CARD, fg=FG).pack()
        tk.Label(hdr, text="Convert Krita files to PNG in bulk",
                 font=FONT_UI, bg=CARD, fg=FG_DIM).pack()

        body = tk.Frame(self, bg=BG, padx=24, pady=18)
        body.pack(fill="both", expand=True)

        # Input folder
        self._section(body, "1  Source Folder", 0)
        row1 = tk.Frame(body, bg=BG)
        row1.pack(fill="x", pady=(4, 12))
        tk.Entry(row1, textvariable=self._input_dir, font=FONT_UI,
                 bg=SURFACE, fg=FG, insertbackground=FG,
                 relief="flat", bd=6).pack(side="left", fill="x", expand=True)
        self._btn(row1, "Browse…", self._pick_input).pack(side="left", padx=(8, 0))

        # Output folder
        self._section(body, "2  Output Folder", 0)
        ck = tk.Checkbutton(body, text="Save PNGs in same folder as source files",
                             variable=self._same_dir, command=self._toggle_output,
                             bg=BG, fg=FG_DIM, selectcolor=CARD,
                             activebackground=BG, activeforeground=FG,
                             font=FONT_UI, cursor="hand2")
        ck.pack(anchor="w", pady=(4, 4))

        self._out_row = tk.Frame(body, bg=BG)
        self._out_row.pack(fill="x", pady=(0, 12))
        self._out_entry = tk.Entry(self._out_row, textvariable=self._output_dir,
                                   font=FONT_UI, bg=SURFACE, fg=FG,
                                   insertbackground=FG, relief="flat", bd=6,
                                   state="disabled")
        self._out_entry.pack(side="left", fill="x", expand=True)
        self._out_btn = self._btn(self._out_row, "Browse…", self._pick_output)
        self._out_btn.pack(side="left", padx=(8, 0))
        self._out_btn.configure(state="disabled")

        # File list
        self._section(body, "3  Files Found", 0)
        list_frame = tk.Frame(body, bg=SURFACE, bd=0)
        list_frame.pack(fill="both", expand=True, pady=(4, 12))

        cols = ("file", "size", "status")
        self._tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                   height=8, selectmode="none")
        self._style_tree()
        self._tree.heading("file",   text="File")
        self._tree.heading("size",   text="Size")
        self._tree.heading("status", text="Status")
        self._tree.column("file",   width=400, stretch=True)
        self._tree.column("size",   width=80,  anchor="e", stretch=False)
        self._tree.column("status", width=200, stretch=False)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Progress
        self._progress = ttk.Progressbar(body, mode="determinate",
                                          style="Accent.Horizontal.TProgressbar")
        self._progress.pack(fill="x", pady=(0, 8))

        # Status + convert button
        foot = tk.Frame(body, bg=BG)
        foot.pack(fill="x")
        tk.Label(foot, textvariable=self._status, font=FONT_UI,
                 bg=BG, fg=FG_DIM, anchor="w").pack(side="left", fill="x", expand=True)
        self._convert_btn = self._btn(foot, "Convert All", self._start_conversion,
                                       color=ACCENT, width=14)
        self._convert_btn.pack(side="right")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section(self, parent, text, pady_top=8):
        tk.Label(parent, text=text, font=FONT_BOLD,
                 bg=BG, fg=ACCENT2).pack(anchor="w", pady=(pady_top, 0))

    def _btn(self, parent, text, cmd, color=CARD, width=9):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=color, fg=FG, activebackground=ACCENT2, activeforeground=FG,
                      relief="flat", bd=0, padx=12, pady=6,
                      font=FONT_BOLD, cursor="hand2", width=width)
        return b

    def _style_tree(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
                         background=SURFACE, foreground=FG,
                         fieldbackground=SURFACE, rowheight=24,
                         font=FONT_MONO, borderwidth=0)
        style.configure("Treeview.Heading",
                         background=CARD, foreground=FG_DIM,
                         font=FONT_BOLD, relief="flat")
        style.map("Treeview", background=[("selected", CARD)])
        style.configure("Accent.Horizontal.TProgressbar",
                         troughcolor=SURFACE, background=ACCENT,
                         bordercolor=SURFACE, lightcolor=ACCENT, darkcolor=ACCENT)

    # ── Interactions ──────────────────────────────────────────────────────────

    def _toggle_output(self):
        same = self._same_dir.get()
        state = "disabled" if same else "normal"
        self._out_entry.configure(state=state)
        self._out_btn.configure(state=state)

    def _pick_input(self):
        d = filedialog.askdirectory(title="Select source folder")
        if d:
            self._input_dir.set(d)
            self._scan_folder(Path(d))

    def _pick_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self._output_dir.set(d)

    def _scan_folder(self, folder: Path):
        self._files = sorted(folder.rglob("*.kra"))
        self._tree.delete(*self._tree.get_children())
        for f in self._files:
            size = f.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size < 1_048_576 else f"{size/1_048_576:.1f} MB"
            self._tree.insert("", "end", iid=str(f),
                               values=(f.name, size_str, "Pending"))
        n = len(self._files)
        self._status.set(f"Found {n} .kra file{'s' if n != 1 else ''}.")
        self._progress["value"] = 0

    # ── Conversion ────────────────────────────────────────────────────────────

    def _start_conversion(self):
        if self._running:
            return
        if not self._files:
            self._status.set("No .kra files found. Pick a folder first.")
            return

        self._running = True
        self._convert_btn.configure(state="disabled", text="Converting…")
        threading.Thread(target=self._convert_worker, daemon=True).start()

    def _convert_worker(self):
        total = len(self._files)
        done = ok = fail = 0

        for f in self._files:
            out_dir = f.parent if self._same_dir.get() else Path(self._output_dir.get() or f.parent)
            out_dir.mkdir(parents=True, exist_ok=True)

            success, msg = extract_kra_to_png(f, out_dir)
            done += 1
            if success:
                ok += 1
                tag = "ok"
                label = "✓ Done"
            else:
                fail += 1
                tag = "fail"
                label = f"✗ {msg[:40]}"

            self.after(0, self._update_row, str(f), label, tag)
            pct = int(done / total * 100)
            self.after(0, self._set_progress, pct, done, total, ok, fail)

        self.after(0, self._done, ok, fail)

    def _update_row(self, iid, label, tag):
        if self._tree.exists(iid):
            vals = list(self._tree.item(iid, "values"))
            vals[2] = label
            self._tree.item(iid, values=vals)
            color = SUCCESS if tag == "ok" else ACCENT
            self._tree.tag_configure(tag, foreground=color)
            self._tree.item(iid, tags=(tag,))

    def _set_progress(self, pct, done, total, ok, fail):
        self._progress["value"] = pct
        self._status.set(f"Converting… {done}/{total}  ✓ {ok}  ✗ {fail}")

    def _done(self, ok, fail):
        self._running = False
        self._convert_btn.configure(state="normal", text="Convert All")
        msg = f"Done! {ok} converted"
        if fail:
            msg += f", {fail} failed."
        else:
            msg += " successfully."
        self._status.set(msg)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
