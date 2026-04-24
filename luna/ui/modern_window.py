#!/usr/bin/env python3
"""
deepLuna Modern GUI  — v3.3
UI refactored to match Tsuki's clean, consistent design system.

Layout (mirrors tsuki_trans.py structure):
  Menu   — File / Edit / Tools menu bar
  Top    — Slim toolbar: Open DB · Save DB · Extract MRGs · Linter · Patch MRG
  Left   — Route / Day / Scene tree + global progress footer
  Right  — Search bar + scope breadcrumb + ttk.Treeview grid (JP | EN)
           + bottom detail panel with read-only JP box and editable EN box
             (Ctrl+Enter to save, Escape to cancel)

Design system aligned with tsuki_trans.py:
  • Near-black tonal background layers (#0a0a0a → #1c1c1c)
  • Flat relief on every widget; accent = #d0d0d0
  • ttk.Treeview for the translation grid (replaces slow canvas+frames)
  • Detail panel for rich editing (replaces floating CellEditor)
  • ttk.Scrollbars throughout (thin, consistent)
  • All dialogs share the same dark palette
"""

import os
import re
import sys
import time
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from luna.constants import Constants
from luna.translation_db import TranslationDb

try:
    from pua_encode import pua_to_fmt_tags as _pua_to_fmt
except ImportError:
    def _pua_to_fmt(t): return t   # graceful fallback


# ════════════════════════════════════════════════════════════════════════════
#  TAG PARSING UTILITIES
# ════════════════════════════════════════════════════════════════════════════

# Matches ALL supported format tags including g (gray) and b (bold)
_TAG_TOKEN = re.compile(
    r'%\{(/?(?:ri|[gibn s]))\}'        # style / control tags
    r'|<([^|>\n]+)\|([^>\n]*)>'        # ruby: <base|rt>
)

_STYLE_OPEN  = {"i": "italic", "b": "italic",
                "r": "rev",    "ri": "rev_ital",
                "g": "gray"}
_STYLE_CLOSE = {"/i", "/r", "/ri", "/g", "/b"}


def _parse_tagged(text: str):
    """Tokenise a JP line into (segment_text, style, ruby_rt | None) triples.

    style is one of: None | 'italic' | 'rev' | 'rev_ital'
    ruby_rt is not None only for ruby segments (annotate the base text).
    """
    style_stack: list[str | None] = []
    pos = 0
    for m in _TAG_TOKEN.finditer(text):
        # Plain text before this match
        if m.start() > pos:
            seg = text[pos:m.start()]
            if seg:
                yield (seg, style_stack[-1] if style_stack else None, None)
        pos = m.end()

        cc, rb_base, rb_rt = m.group(1), m.group(2), m.group(3)
        if cc is not None:
            if cc == "n":
                yield ("\n", style_stack[-1] if style_stack else None, None)
            elif cc == "s":
                yield (" ",  style_stack[-1] if style_stack else None, None)
            elif cc in _STYLE_OPEN:
                style_stack.append(_STYLE_OPEN[cc])
            elif cc in _STYLE_CLOSE and style_stack:
                style_stack.pop()
        else:
            # Ruby token
            cur = style_stack[-1] if style_stack else None
            yield (rb_base, cur, rb_rt)

    if pos < len(text):
        seg = text[pos:]
        if seg:
            yield (seg, style_stack[-1] if style_stack else None, None)


def _strip_trailing_n_tags(text: str) -> str:
    """Remove trailing %{n} newline tags for display purposes only.

    %{n} is a line-terminator added by the engine at the end of most lines.
    It should not clutter the editor view — it is shown as a clickable button
    in the tag-shortcuts bar.  Raw stored data is never touched by this helper.

    Handles:
      • Single or repeated  %{n}  at end
      • %{n} followed by whitespace / real newlines from the DB
      • Mixed  %{n}\n  endings
    """
    # Rstrip real whitespace/newlines first, then strip any trailing %{n} blocks,
    # then rstrip any whitespace that was hiding between the last tag and the end.
    text = text.rstrip()
    text = re.sub(r'(\s*%\{n\})+$', '', text)
    return text.rstrip()


def _clean_for_grid(text: str, maxlen: int = 110) -> str:
    """Return a compact one-line preview for the grid cell.

    • Trailing %{n} tags are stripped (line-terminators, not display content).
    • PUA italic characters (U+E020–U+E07E) are decoded back to %{i}…%{/i}
      so translators can see which format tags are active.
    • Ruby annotations are kept as <base|rt>.
    • Internal newlines become the ↵ indicator; \\r is stripped.
    """
    # Decode PUA italic chars → %{i}…%{/i} so they show readable in grid
    text = _pua_to_fmt(text)
    # Strip trailing %{n} — these are engine line-terminators, not content
    text = _strip_trailing_n_tags(text)
    # Normalise remaining line endings for one-line display
    text = text.replace("\r\n", " %{n} ").replace("\r", "").replace("\n", "↵")
    if len(text) > maxlen:
        return text[:maxlen] + "…"
    return text


# ════════════════════════════════════════════════════════════════════════════
#  FONT DETECTION
# ════════════════════════════════════════════════════════════════════════════

def _detect_font() -> str:
    import tkinter.font as tkf
    if sys.platform.startswith("win"):
        preferred = ["Meiryo UI", "Meiryo", "Yu Gothic UI", "Yu Gothic",
                     "MS Gothic", "Arial Unicode MS"]
    elif sys.platform == "darwin":
        preferred = ["Hiragino Kaku Gothic Pro", "Hiragino Sans", "Osaka",
                     "Arial Unicode MS"]
    else:
        preferred = ["Noto Sans CJK JP", "Noto Sans JP", "IPAGothic",
                     "TakaoGothic", "VL Gothic", "WenQuanYi Micro Hei"]
    try:
        available = set(tkf.families())
        for fam in preferred:
            if any(fam.lower() == a.lower() for a in available):
                return fam
    except Exception:
        pass
    return "TkDefaultFont"


# ════════════════════════════════════════════════════════════════════════════
#  COLOUR PALETTE  (aligned with tsuki_trans.py _build_palette)
# ════════════════════════════════════════════════════════════════════════════

def _build_palette(font_family: str) -> dict:
    UI      = (font_family, 9)
    MONO    = (font_family, 10)
    MONO_SM = (font_family, 9)
    TITLE   = (font_family, 13, "bold")
    return {
        # Backgrounds — near-black tonal layers
        "bg":       "#0a0a0a",   # root / chrome
        "bg2":      "#111111",   # search bar, detail panel base
        "bg3":      "#1a1a1a",   # input fields, tag bar
        "bg4":      "#242424",   # buttons, hover states
        "panel":    "#0d0d0d",   # left sidebar
        "alt":      "#161616",   # alternating grid row
        "border":   "#2a2a2a",   # thin separators (1 px)
        "divider":  "#383838",   # heavier panel dividers (2 px)
        "tag_bar":  "#131313",   # tag shortcut strip — deliberately distinct
        # Text
        "fg":     "#efefef",
        "fg2":    "#808080",
        "fg3":    "#404040",
        # Accent / selection
        "accent": "#c8c8c8",
        "sel":    "#2a2a2a",
        "sel_fg": "#ffffff",
        # Status colours
        "ok":     "#7ec98a",
        "warn":   "#e0a060",
        "err":    "#e06060",
        # Route colours (muted, readable on dark)
        "arc":    "#e0d8c8",
        "ciel":   "#c8d8e0",
        "qa":     "#a8a8a8",
        "misc":   "#c0c0b8",
        # Fonts
        "ui":      UI,
        "mono":    MONO,
        "mono_sm": MONO_SM,
        "title":   TITLE,
    }


C: dict = {}
ROUTE_COLORS: dict = {}


# ════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ════════════════════════════════════════════════════════════════════════════

class ModernWindow:
    VERSION = "3.3"

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(f"deepLuna {self.VERSION}")

        global C, ROUTE_COLORS
        _font = _detect_font()
        C = _build_palette(_font)
        ROUTE_COLORS = {
            "Arcueid": C["arc"],
            "Ciel":    C["ciel"],
            "QA":      C["qa"],
            "Misc":    C["misc"],
        }

        root.configure(bg=C["bg"])
        root.geometry("1320x800")
        root.minsize(1000, 640)

        # ── State ──────────────────────────────────────────────────────────
        self._tl_db:          TranslationDb | None = None
        self._db_path:        str | None = None
        self._allscr_path:    str | None = None
        self._script_path:    str | None = None
        self._current_scene:  str | None = None
        self._modified:       bool = False

        # Grid data for currently loaded scope
        self._grid_rows:    list[dict] = []   # [{offset, jp_hash, jp, en, done, is_override}]
        self._visible_rows: list[int]  = []   # indices into _grid_rows
        self._editing_offset: int | None = None
        self._search_job:   str | None = None

        # Search / filter vars
        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="All")
        self.status_var = tk.StringVar(value="Open a DB to begin.")
        self.search_var.trace_add("write", self._on_search_change)
        self.filter_var.trace_add("write", lambda *_: self._refresh_grid())

        self._build_menu()
        self._build_ui()
        self._apply_styles()
        root.protocol("WM_DELETE_WINDOW", self._on_quit)

    # ─────────────────────────── MENU ──────────────────────────────────────

    def _build_menu(self):
        mb = tk.Menu(self.root, bg=C["bg2"], fg=C["fg"],
                     activebackground=C["sel"], activeforeground=C["fg"],
                     relief="flat", bd=0)
        self.root.configure(menu=mb)

        def _menu(label):
            m = tk.Menu(mb, tearoff=False, bg=C["bg2"], fg=C["fg"],
                        activebackground=C["sel"], activeforeground=C["fg"])
            mb.add_cascade(label=label, menu=m)
            return m

        fm = _menu("File")
        fm.add_command(label="Open DB…          Ctrl+O", command=self._open_db)
        fm.add_command(label="Save DB            Ctrl+S", command=self._save_db)
        fm.add_separator()
        fm.add_command(label="Extract MRGs…",            command=self._extract_mrgs_dialog)
        fm.add_separator()
        fm.add_command(label="Export Scene…     Ctrl+E", command=self._export_scene)
        fm.add_command(label="Export All…",              command=self._export_all)
        fm.add_separator()
        fm.add_command(label="Patch MRG…        Ctrl+P", command=self._patch_mrg)
        fm.add_separator()
        fm.add_command(label="Quit",                      command=self._on_quit)

        em = _menu("Edit")
        em.add_command(label="Find…              Ctrl+F", command=self._focus_search)
        em.add_command(label="Find & Replace…    Ctrl+H", command=self._find_replace_dialog)
        em.add_separator()
        em.add_command(label="Jump to Offset…    Ctrl+G", command=self._jump_dialog)

        tm = _menu("Tools")
        tm.add_command(label="Linter…            Ctrl+L", command=self._linter_dialog)

        for key, cmd in [
            ("<Control-o>", self._open_db),
            ("<Control-s>", self._save_db),
            ("<Control-p>", self._patch_mrg),
            ("<Control-f>", self._focus_search),
            ("<Control-g>", self._jump_dialog),
            ("<Control-h>", self._find_replace_dialog),
            ("<Control-e>", self._export_scene),
            ("<Control-l>", self._linter_dialog),
        ]:
            self.root.bind_all(key, lambda e, c=cmd: c())

    # ─────────────────────────── UI BUILD ──────────────────────────────────

    def _build_ui(self):
        # ── Title bar + toolbar ────────────────────────────────────────────
        top = tk.Frame(self.root, bg=C["bg"], height=44)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(top, text="  deepLuna",
                 font=C["title"], bg=C["bg"], fg=C["fg"]
                 ).pack(side="left", padx=(12, 0), pady=8)

        def _tbtn(text, cmd, color=C["bg4"]):
            b = tk.Button(top, text=text, command=cmd, font=C["ui"],
                          bg=color, fg=C["fg"],
                          activebackground=C["accent"], activeforeground=C["bg"],
                          relief="flat", bd=0, cursor="hand2",
                          padx=12, pady=3)
            b.pack(side="left", padx=3, pady=8)
            return b

        def _sep():
            tk.Frame(top, bg=C["border"], width=1).pack(
                side="left", fill="y", padx=4, pady=10)

        _tbtn("Open DB",      self._open_db)
        _tbtn("Save DB",      self._save_db)
        _sep()
        _tbtn("Extract MRGs", self._extract_mrgs_dialog)
        _sep()
        _tbtn("Linter",       self._linter_dialog,       C["bg3"])
        _tbtn("Patch MRG",    self._patch_mrg,           C["border"])

        self.mod_lbl = tk.Label(top, text="", font=C["ui"],
                                bg=C["bg"], fg=C["warn"])
        self.mod_lbl.pack(side="left", padx=4)

        self.status_lbl = tk.Label(top, textvariable=self.status_var,
                                   font=C["ui"], bg=C["bg"], fg=C["fg2"],
                                   anchor="e")
        self.status_lbl.pack(side="right", padx=16)

        tk.Frame(self.root, bg=C["divider"], height=2).pack(fill="x")

        # ── Body ──────────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill="both", expand=True)

        self._left_panel = tk.Frame(body, bg=C["panel"], width=240)
        self._left_panel.pack(side="left", fill="y")
        self._left_panel.pack_propagate(False)

        # Heavier vertical divider between sidebar and content area
        tk.Frame(body, bg=C["divider"], width=2).pack(side="left", fill="y")

        right = tk.Frame(body, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        self._build_left()
        self._build_right(right)

    def _build_left(self):
        P = self._left_panel

        # Header — slightly taller, with a stronger bottom separator
        hdr = tk.Frame(P, bg=C["bg3"], height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  SCENES", font=(C["ui"][0], 8, "bold"),
                 bg=C["bg3"], fg=C["fg3"]).pack(side="left", padx=10, pady=0)
        tk.Button(hdr, text="ALL", font=(C["ui"][0], 8),
                  bg=C["bg4"], fg=C["fg"],
                  activebackground=C["accent"], activeforeground=C["bg"],
                  relief="flat", bd=0, cursor="hand2", padx=8, pady=2,
                  command=self._show_all_scenes
                  ).pack(side="right", padx=8, pady=7)
        tk.Frame(P, bg=C["divider"], height=2).pack(fill="x")

        # Tree
        tf = tk.Frame(P, bg=C["panel"])
        tf.pack(fill="both", expand=True)

        self._tree = ttk.Treeview(tf, style="L.Treeview",
                                  show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Progress footer
        tk.Frame(P, bg=C["divider"], height=2).pack(fill="x")
        self._prog_frame = tk.Frame(P, bg=C["panel"])
        self._prog_frame.pack(fill="x", pady=6)

    def _build_right(self, parent):
        # ── Search / filter bar ────────────────────────────────────────────
        bar = tk.Frame(parent, bg=C["bg2"], height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="  Search:", font=C["ui"],
                 bg=C["bg2"], fg=C["fg2"]).pack(side="left", padx=(12, 0))

        self._search_entry = tk.Entry(
            bar, textvariable=self.search_var, font=C["mono_sm"],
            bg=C["bg3"], fg=C["fg"], insertbackground=C["fg"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=C["border"],
            highlightcolor=C["accent"])
        self._search_entry.pack(side="left", fill="x", expand=True,
                                ipady=5, padx=10, pady=7)
        self._search_entry.bind("<Return>", self._search_next)
        self._search_entry.bind("<Escape>", lambda e: self.search_var.set(""))

        tk.Label(bar, text="Show:", font=C["ui"],
                 bg=C["bg2"], fg=C["fg2"]).pack(side="left", padx=(8, 2))
        flt = ttk.Combobox(bar, textvariable=self.filter_var, width=13,
                           values=["All", "Untranslated", "Translated"],
                           state="readonly", font=C["ui"])
        flt.pack(side="left", padx=(0, 8), pady=7)

        self._match_lbl = tk.Label(bar, text="", font=C["ui"],
                                   bg=C["bg2"], fg=C["fg2"],
                                   width=22, anchor="e")
        self._match_lbl.pack(side="right", padx=12)

        # ── Scope breadcrumb — heavier top/bottom dividers ─────────────────
        tk.Frame(parent, bg=C["divider"], height=2).pack(fill="x")
        self._scope_bar = tk.Frame(parent, bg=C["bg3"], height=26)
        self._scope_bar.pack(fill="x")
        self._scope_bar.pack_propagate(False)
        self._scope_lbl = tk.Label(self._scope_bar, text="  All scenes",
                                   font=(C["ui"][0], 8), bg=C["bg3"], fg=C["fg2"],
                                   anchor="w")
        self._scope_lbl.pack(fill="x", padx=12, pady=4)
        tk.Frame(parent, bg=C["divider"], height=2).pack(fill="x")

        # ── Translation grid (ttk.Treeview) ───────────────────────────────
        gf = tk.Frame(parent, bg=C["bg"])
        gf.pack(fill="both", expand=True)

        cols = ("status", "offset", "sep1", "jp", "sep2", "en")
        self._grid = ttk.Treeview(gf, columns=cols, show="headings",
                                  style="G.Treeview", selectmode="browse")

        for col, hdr_text, w, stretch, anchor in [
            ("status", "✓",              28,  False, "center"),
            ("offset", "#",              72,  False, "center"),
            ("sep1",   "",               8,   False, "center"),
            ("jp",     "JP Original",   470,  True,  "w"),
            ("sep2",   "",               8,   False, "center"),
            ("en",     "EN Translation", 470, True,  "w"),
        ]:
            self._grid.heading(col, text=hdr_text, anchor=anchor)
            self._grid.column(col, width=w, minwidth=max(w - 8, 8),
                              stretch=stretch, anchor=anchor)

        vsb2 = ttk.Scrollbar(gf, orient="vertical",   command=self._grid.yview)
        hsb2 = ttk.Scrollbar(gf, orient="horizontal",  command=self._grid.xview)
        self._grid.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        vsb2.pack(side="right", fill="y")
        hsb2.pack(side="bottom", fill="x")
        self._grid.pack(fill="both", expand=True)

        self._grid.bind("<<TreeviewSelect>>", self._on_grid_sel)
        self._grid.bind("<Double-Button-1>",  self._on_grid_double)
        self._grid.bind("<Return>",           self._on_grid_enter)
        self._grid.bind("<Tab>",              self._on_tab)

        # ── Detail / edit panel ────────────────────────────────────────────
        tk.Frame(parent, bg=C["border"], height=2).pack(fill="x")
        self._detail = tk.Frame(parent, bg=C["bg2"])
        self._detail.pack(fill="x")
        self._build_detail()

    def _build_detail(self):
        D = self._detail

        # Info row
        info_row = tk.Frame(D, bg=C["bg2"])
        info_row.pack(fill="x", padx=10, pady=(7, 0))
        self._det_lbl = tk.Label(info_row,
                                 text="Select a row to view and edit",
                                 font=C["ui"], bg=C["bg2"], fg=C["fg2"],
                                 anchor="w")
        self._det_lbl.pack(side="left", fill="x", expand=True)
        tk.Label(info_row,
                 text="Double-click / Enter = edit   Tab = next   Ctrl+Enter = save",
                 font=(C["ui"][0], 8), bg=C["bg2"], fg=C["fg3"]
                 ).pack(side="right", padx=4)

        # Two columns
        cols = tk.Frame(D, bg=C["bg2"])
        cols.pack(fill="x", padx=10, pady=(6, 0))

        # Left — JP Original (read-only, rich-rendered)
        lf = tk.Frame(cols, bg=C["bg2"])
        lf.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(lf, text="JP Original", font=(C["ui"][0], 8, "bold"),
                 bg=C["bg2"], fg=C["fg3"]).pack(anchor="w")
        self._orig_box = tk.Text(
            lf, font=C["mono"], bg=C["bg3"], fg=C["fg2"],
            relief="flat", bd=0, wrap="word", height=3,
            state="disabled", cursor="arrow",
            highlightthickness=1, highlightbackground=C["border"])
        self._orig_box.pack(fill="x")

        # Right — EN Translation (editable)
        rf = tk.Frame(cols, bg=C["bg2"])
        rf.pack(side="left", fill="both", expand=True, padx=(6, 0))

        tlbl = tk.Frame(rf, bg=C["bg2"])
        tlbl.pack(fill="x")
        tk.Label(tlbl, text="EN Translation", font=(C["ui"][0], 8, "bold"),
                 bg=C["bg2"], fg=C["fg3"]).pack(side="left")
        tk.Button(tlbl, text="Save  Ctrl+Enter",
                  font=(C["ui"][0], 8),
                  bg=C["bg4"], fg=C["fg"],
                  activebackground=C["accent"], activeforeground=C["bg"],
                  relief="flat", bd=0, cursor="hand2", padx=8, pady=1,
                  command=self._save_detail).pack(side="right")
        tk.Button(tlbl, text="Clear",
                  font=(C["ui"][0], 8),
                  bg=C["bg3"], fg=C["fg2"],
                  activebackground=C["bg4"], activeforeground=C["fg"],
                  relief="flat", bd=0, cursor="hand2", padx=6, pady=1,
                  command=self._clear_detail).pack(side="right", padx=4)

        # ── Tag shortcut toolbar ───────────────────────────────────────────
        tag_bar = tk.Frame(rf, bg=C["bg2"])
        tag_bar.pack(fill="x", pady=(4, 2))

        tk.Label(tag_bar, text="Tags:", font=(C["ui"][0], 8),
                 bg=C["bg2"], fg=C["fg3"]).pack(side="left", padx=(0, 4))

        _BTN_FONT = (C["mono"][0], 8)   # monospace so %{…} aligns properly

        def _tag_btn(label, open_tag, close_tag):
            b = tk.Button(
                tag_bar, text=label,
                font=_BTN_FONT,
                bg=C["bg3"], fg=C["accent"],
                activebackground=C["bg4"], activeforeground=C["fg"],
                relief="flat", bd=0, cursor="hand2", padx=6, pady=2,
                command=lambda: self._insert_tag(open_tag, close_tag))
            b.pack(side="left", padx=2)
            return b

        _tag_btn("%{i}  Ctrl+I",        "%{i}",  "%{/i}")
        _tag_btn("%{ri}  Ctrl+Shift+I", "%{ri}", "%{/ri}")
        _tag_btn("%{r}  Ctrl+Shift+R",  "%{r}",  "%{/r}")
        _tag_btn("%{g}  Ctrl+Shift+G",  "%{g}",  "%{/g}")

        # Ruby button (special: <base|rt>)
        tk.Button(
            tag_bar, text="<ruby>  Ctrl+Shift+U",
            font=_BTN_FONT,
            bg=C["bg3"], fg=C["warn"],
            activebackground=C["bg4"], activeforeground=C["fg"],
            relief="flat", bd=0, cursor="hand2", padx=6, pady=2,
            command=self._insert_ruby).pack(side="left", padx=2)

        # %{n} newline tag — proper button, not a dead label
        tk.Button(
            tag_bar, text="%{n} ↵",
            font=_BTN_FONT,
            bg=C["bg3"], fg=C["accent"],
            activebackground=C["bg4"], activeforeground=C["fg"],
            relief="flat", bd=0, cursor="hand2", padx=6, pady=2,
            command=lambda: self._insert_tag("%{n}", "")).pack(side="left", padx=2)

        # %{s} hint only (rarely typed manually)
        tk.Label(tag_bar, text="%{s}=space",
                 font=(C["ui"][0], 8), bg=C["bg2"], fg=C["fg3"]
                 ).pack(side="left", padx=(6, 0))

        self._trans_box = tk.Text(
            rf, font=C["mono"], bg=C["bg3"], fg=C["fg"],
            insertbackground=C["fg"], relief="flat", bd=0,
            wrap="word", height=3, undo=True,
            highlightthickness=1, highlightbackground=C["border"],
            highlightcolor=C["accent"])
        self._trans_box.pack(fill="x", pady=(0, 8))
        self._trans_box.bind("<Control-Return>",    lambda e: self._save_detail())
        self._trans_box.bind("<Escape>",            lambda e: self._cancel_detail())
        self._trans_box.bind("<Control-i>",         lambda e: (self._insert_tag("%{i}", "%{/i}"), "break")[1])
        self._trans_box.bind("<Control-I>",         lambda e: (self._insert_tag("%{ri}", "%{/ri}"), "break")[1])
        self._trans_box.bind("<Control-R>",         lambda e: (self._insert_tag("%{r}", "%{/r}"), "break")[1])
        self._trans_box.bind("<Control-U>",         lambda e: (self._insert_ruby(), "break")[1])
        self._trans_box.bind("<Control-G>",         lambda e: (self._insert_tag("%{g}", "%{/g}"), "break")[1])

    # ─────────────────────────── TTK STYLES ────────────────────────────────

    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("default")
        fnt = C["ui"][0]

        # Scene tree (left panel)
        s.configure("L.Treeview",
                    background=C["panel"], foreground=C["fg"],
                    fieldbackground=C["panel"],
                    rowheight=24, font=(fnt, 9), borderwidth=0)
        s.map("L.Treeview",
              background=[("selected", C["sel"])],
              foreground=[("selected", C["sel_fg"])])

        # Translation grid
        s.configure("G.Treeview",
                    background=C["bg2"], foreground=C["fg"],
                    fieldbackground=C["bg2"],
                    rowheight=28, font=(fnt, 10), borderwidth=0)
        s.map("G.Treeview",
              background=[("selected", C["sel"])],
              foreground=[("selected", C["sel_fg"])])
        s.configure("G.Treeview.Heading",
                    background=C["bg3"], foreground=C["fg2"],
                    font=(fnt, 9, "bold"), borderwidth=0, relief="flat")
        s.map("G.Treeview.Heading", relief=[("active", "flat")])

        # Row tags — done rows get a slightly lighter fg so translated lines read cleaner
        self._grid.tag_configure("row_odd",  background=C["bg2"])
        self._grid.tag_configure("row_even", background=C["alt"])
        self._grid.tag_configure("done",     foreground=C["fg"])
        self._grid.tag_configure("todo",     foreground=C["fg2"])

        # Separator columns — dim pipe char
        self._grid.column("sep1", width=8,  minwidth=8,  stretch=False, anchor="center")
        self._grid.column("sep2", width=8,  minwidth=8,  stretch=False, anchor="center")
        self._grid.heading("sep1", text="")
        self._grid.heading("sep2", text="")

        # Scrollbars
        for n in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            s.configure(n, background=C["bg4"], troughcolor=C["bg2"],
                        bordercolor=C["bg2"], arrowcolor=C["fg3"],
                        relief="flat")

        # Combobox
        s.configure("TCombobox",
                    fieldbackground=C["bg3"], background=C["bg3"],
                    foreground=C["fg"], selectbackground=C["sel"],
                    arrowcolor=C["fg2"], borderwidth=0)
        s.map("TCombobox",
              fieldbackground=[("readonly", C["bg3"])],
              foreground=[("readonly", C["fg"])])

    # ─────────────────────────── SCENE TREE ────────────────────────────────

    def _populate_scene_tree(self):
        if not self._tl_db:
            return
        for item in self._tree.get_children():
            self._tree.delete(item)

        scene_names = self._tl_db.scene_names()

        arc_scenes  = sorted(n for n in scene_names if "_ARC"  in n)
        ciel_scenes = sorted(n for n in scene_names if "_CIEL" in n)
        qa_scenes   = sorted(n for n in scene_names
                             if "QA_" in n or n.startswith("QA"))
        misc_scenes = sorted(n for n in scene_names
                             if n not in set(arc_scenes + ciel_scenes + qa_scenes))

        def _pct(scene):
            lines = self._tl_db.lines_for_scene(scene)
            if not lines:
                return 0.0
            done = sum(
                1 for line in lines
                if self._tl_db.tl_line_with_hash(line.jp_hash).en_text)
            return done * 100 / len(lines)

        def _insert_route(route_id, route_name, scenes, by_day=True):
            total = sum(len(self._tl_db.lines_for_scene(s)) for s in scenes)
            done  = sum(
                sum(1 for l in self._tl_db.lines_for_scene(s)
                    if self._tl_db.tl_line_with_hash(l.jp_hash).en_text)
                for s in scenes)
            pct   = (done * 100 / total) if total else 0.0

            rid = self._tree.insert(
                "", "end", iid=f"R:{route_id}",
                text=f"  {route_name}  ({pct:.1f}%)",
                open=False, tags=(f"rt_{route_id}",))
            self._tree.tag_configure(
                f"rt_{route_id}",
                foreground=ROUTE_COLORS.get(route_name, C["fg"]))

            if by_day:
                days = sorted(set(s.split("_")[0] for s in scenes))
                for day in days:
                    day_scenes = [s for s in scenes if s.split("_")[0] == day]
                    day_id = f"D:{route_id}:{day}"
                    day_total = sum(len(self._tl_db.lines_for_scene(s))
                                    for s in day_scenes)
                    day_done  = sum(
                        sum(1 for l in self._tl_db.lines_for_scene(s)
                            if self._tl_db.tl_line_with_hash(l.jp_hash).en_text)
                        for s in day_scenes)
                    day_pct = (day_done * 100 / day_total) if day_total else 0.0
                    self._tree.insert(
                        f"R:{route_id}", "end", iid=day_id,
                        text=f"  Day {day}  ({day_pct:.1f}%)",
                        open=False, tags=("day",))
                    self._tree.tag_configure("day", foreground=C["fg2"])
                    for scene in day_scenes:
                        self._tree.insert(
                            day_id, "end", iid=f"F:{scene}",
                            text=f"  {scene}  ({_pct(scene):.1f}%)",
                            tags=("scene",))
            else:
                for scene in scenes:
                    self._tree.insert(
                        f"R:{route_id}", "end", iid=f"F:{scene}",
                        text=f"  {scene}  ({_pct(scene):.1f}%)",
                        tags=("scene",))

            self._tree.tag_configure("scene", foreground=C["fg"],
                                     font=(C["ui"][0], 9))

        _insert_route("arc",  "Arcueid", arc_scenes,  by_day=True)
        _insert_route("ciel", "Ciel",    ciel_scenes, by_day=True)
        _insert_route("qa",   "QA",      qa_scenes,   by_day=False)
        _insert_route("misc", "Misc",    misc_scenes,  by_day=False)

    def _update_progress(self):
        for w in self._prog_frame.winfo_children():
            w.destroy()
        if not self._tl_db:
            return
        pct = self._tl_db.translated_percent()
        scene_names = self._tl_db.scene_names()
        total = sum(len(self._tl_db.lines_for_scene(s)) for s in scene_names)
        done  = sum(
            sum(1 for l in self._tl_db.lines_for_scene(s)
                if self._tl_db.tl_line_with_hash(l.jp_hash).en_text)
            for s in scene_names)
        tk.Label(self._prog_frame,
                 text=f"  Global: {done:,} / {total:,}  ({pct:.1f}%)",
                 font=C["ui"], bg=C["panel"], fg=C["fg2"]
                 ).pack(anchor="w", padx=6)

    # ─────────────────────────── GRID REFRESH ──────────────────────────────

    def _on_search_change(self, *_):
        if self._search_job:
            try:
                self.root.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.root.after(80, self._refresh_grid)

    def _refresh_grid(self, *_):
        self._grid.delete(*self._grid.get_children())

        if not self._grid_rows:
            self._match_lbl.config(text="")
            return

        query = self.search_var.get().strip().lower()
        filt  = self.filter_var.get()

        visible = []
        for i, row in enumerate(self._grid_rows):
            if filt == "Translated"   and not row["done"]:
                continue
            if filt == "Untranslated" and row["done"]:
                continue
            if query and query not in row["jp"].lower() \
                     and query not in row["en"].lower():
                continue
            visible.append(i)

        self._visible_rows = visible

        def _clip(text: str, maxlen: int = 110) -> str:
            return _clean_for_grid(text, maxlen)

        for vis_idx, row_idx in enumerate(visible):
            row      = self._grid_rows[row_idx]
            iid      = f"O:{row['offset']}"
            st       = "✓" if row["done"] else " "
            row_tag  = "row_even" if vis_idx % 2 == 0 else "row_odd"
            done_tag = "done" if row["done"] else "todo"

            self._grid.insert("", "end", iid=iid,
                              values=(st, row["offset"], "│",
                                      _clip(row["jp"]), "│",
                                      _clip(row["en"]) if row["en"] else ""),
                              tags=(done_tag, row_tag))

        total   = len(self._grid_rows)
        shown   = len(visible)
        done_c  = sum(1 for r in self._grid_rows if r["done"])

        if query or filt != "All":
            self._match_lbl.config(
                text=f"{shown:,} / {total:,} shown",
                fg=C["fg"] if shown else C["fg2"])
        else:
            self._match_lbl.config(
                text=f"{done_c:,} / {total:,} translated",
                fg=C["fg2"])

    # ─────────────────────────── TREE EVENTS ───────────────────────────────

    def _show_all_scenes(self):
        if not self._tl_db:
            return
        rows = []
        for scene in self._tl_db.scene_names():
            for cmd in self._tl_db.lines_for_scene(scene):
                tl = self._tl_db.tl_line_for_cmd(cmd)
                rows.append({
                    "offset":      cmd.offset,
                    "jp_hash":     cmd.jp_hash,
                    "jp":          tl.jp_text,
                    "en":          tl.en_text or "",
                    "done":        bool(tl.en_text),
                    "is_override": self._tl_db.tl_override_for_offset(
                                       cmd.offset) is not None,
                })
        self._grid_rows    = rows
        self._visible_rows = list(range(len(rows)))
        self._current_scene = None
        self._scope_lbl.config(text="  All scenes", fg=C["fg2"])
        self._refresh_grid()

    def _on_tree_select(self, _event=None):
        sel = self._tree.focus()
        if not sel or not self._tl_db:
            return

        if sel.startswith("F:"):
            scene_name = sel[2:]
            if scene_name not in self._tl_db.scene_names():
                return
            self._load_scene(scene_name)

        elif sel.startswith("D:"):
            _, route_id, day = sel.split(":", 2)
            scenes = [n for n in self._tl_db.scene_names()
                      if n.split("_")[0] == day]
            self._load_scenes(scenes, label=f"  Day {day}")

        elif sel.startswith("R:"):
            route_id = sel[2:]
            if route_id == "misc":
                exc = set(
                    n for n in self._tl_db.scene_names()
                    if "_ARC" in n or "_CIEL" in n
                    or "QA_" in n or n.startswith("QA"))
                scenes = [n for n in self._tl_db.scene_names()
                          if n not in exc]
            elif route_id == "qa":
                scenes = [n for n in self._tl_db.scene_names()
                          if "QA_" in n or n.startswith("QA")]
            elif route_id == "ciel":
                scenes = [n for n in self._tl_db.scene_names()
                          if "_CIEL" in n]
            else:  # arc
                scenes = [n for n in self._tl_db.scene_names()
                          if "_ARC" in n]
            names = {"arc": "Arcueid", "ciel": "Ciel",
                     "qa": "QA",       "misc": "Misc"}
            self._load_scenes(scenes, label=f"  {names.get(route_id, route_id)}")

    def _load_scene(self, scene_name: str):
        self._current_scene = scene_name
        rows = []
        for cmd in self._tl_db.lines_for_scene(scene_name):
            tl = self._tl_db.tl_line_for_cmd(cmd)
            rows.append({
                "offset":      cmd.offset,
                "jp_hash":     cmd.jp_hash,
                "jp":          tl.jp_text,
                "en":          tl.en_text or "",
                "done":        bool(tl.en_text),
                "is_override": self._tl_db.tl_override_for_offset(
                                   cmd.offset) is not None,
            })
        self._grid_rows = rows
        total = len(rows)
        done  = sum(1 for r in rows if r["done"])
        pct   = (done * 100 / total) if total else 0.0
        self._scope_lbl.config(
            text=f"  {scene_name}  —  {done}/{total}  ({pct:.1f}%)",
            fg=C["fg2"])
        self._refresh_grid()
        self._set_status(f"Loaded '{scene_name}'  ({done}/{total} translated)")

    def _load_scenes(self, scene_list: list[str], label: str = ""):
        self._current_scene = None
        rows = []
        for scene in scene_list:
            for cmd in self._tl_db.lines_for_scene(scene):
                tl = self._tl_db.tl_line_for_cmd(cmd)
                rows.append({
                    "offset":      cmd.offset,
                    "jp_hash":     cmd.jp_hash,
                    "jp":          tl.jp_text,
                    "en":          tl.en_text or "",
                    "done":        bool(tl.en_text),
                    "is_override": self._tl_db.tl_override_for_offset(
                                       cmd.offset) is not None,
                })
        self._grid_rows = rows
        total = len(rows)
        done  = sum(1 for r in rows if r["done"])
        pct   = (done * 100 / total) if total else 0.0
        self._scope_lbl.config(
            text=f"{label}  —  {done}/{total}  ({pct:.1f}%)",
            fg=C["fg2"])
        self._refresh_grid()

    # ─────────────────────────── GRID EVENTS ───────────────────────────────

    def _on_grid_sel(self, _=None):
        sel = self._grid.focus()
        if not sel or not sel.startswith("O:"):
            return
        self._load_detail(int(sel[2:]))

    def _on_grid_double(self, event):
        col = self._grid.identify_column(event.x)
        if col == "#6":   # EN Translation column (sep1=3, jp=4, sep2=5, en=6)
            self._focus_trans_box()

    def _on_grid_enter(self, _=None):
        self._focus_trans_box()

    def _on_tab(self, _=None):
        self._save_detail()
        self._move_selection(+1)
        self._focus_trans_box()
        return "break"

    def _focus_trans_box(self):
        self._trans_box.focus_set()
        self._trans_box.tag_add("sel", "1.0", "end")

    def _move_selection(self, delta: int):
        rows = self._grid.get_children()
        if not rows:
            return
        sel = self._grid.focus()
        idx = rows.index(sel) if sel in rows else -1
        nxt = rows[(idx + delta) % len(rows)]
        self._grid.selection_set(nxt)
        self._grid.focus(nxt)
        self._grid.see(nxt)
        self._load_detail(int(nxt[2:]))

    # ─────────────────────────── DETAIL PANEL ──────────────────────────────

    def _render_jp_rich(self, widget: tk.Text, text: str):
        """Render a JP/EN line with visual tag formatting into a tk.Text widget.

        PUA italic characters are first decoded to %{i}…%{/i} so the renderer
        can apply the italic style.  Gray (%{g}) and bold (%{b}) are also
        handled.
        """
        # Convert PUA italic chars → %{i}…%{/i} format tags
        text = _pua_to_fmt(text)

        fnt = C["mono"][0]
        sz  = C["mono"][1]

        # Configure display tags (safe to call repeatedly)
        widget.tag_configure("italic",
                             font=(fnt, sz, "italic"),
                             foreground=C["fg"])
        widget.tag_configure("gray",
                             foreground=C["fg2"])
        widget.tag_configure("rev",
                             background=C["fg"], foreground=C["bg"])
        widget.tag_configure("rev_ital",
                             background=C["fg"], foreground=C["bg"],
                             font=(fnt, sz, "italic"))
        widget.tag_configure("ruby_rt",
                             foreground=C["accent"],
                             font=(fnt, max(sz - 3, 6)))
        widget.tag_configure("tag_marker",
                             foreground=C["warn"],
                             font=(fnt, max(sz - 1, 7)))

        widget.config(state="normal")
        widget.delete("1.0", "end")

        _STYLE_TAG = {
            "italic":   "italic",
            "gray":     "gray",
            "rev":      "rev",
            "rev_ital": "rev_ital",
            None:       "",
        }

        for seg_text, style, ruby_rt in _parse_tagged(text):
            tk_tag = _STYLE_TAG.get(style, "")
            widget.insert("end", seg_text,
                          (tk_tag,) if tk_tag else ())
            if ruby_rt is not None:
                widget.insert("end", f"[{ruby_rt}]", ("ruby_rt",))

        widget.config(state="disabled")

    def _load_detail(self, offset: int):
        row = next((r for r in self._grid_rows if r["offset"] == offset), None)
        if row is None:
            return
        self._editing_offset = offset
        scene_label = self._current_scene or "—"
        self._det_lbl.config(text=f"  #{offset}   {scene_label}", fg=C["fg2"])

        # Strip trailing %{n} for display — raw data is never modified here
        self._render_jp_rich(self._orig_box, _strip_trailing_n_tags(row["jp"]))

        self._trans_box.delete("1.0", "end")
        if row["en"]:
            self._trans_box.insert("1.0", row["en"])
        self._trans_box.edit_reset()
        self._trans_box.edit_modified(False)

    def _save_detail(self):
        offset = self._editing_offset
        if offset is None or not self._tl_db:
            return
        val = self._trans_box.get("1.0", "end-1c").strip()
        self._commit_translation(offset, val)

    def _clear_detail(self):
        if self._editing_offset is None:
            return
        self._trans_box.delete("1.0", "end")
        self._commit_translation(self._editing_offset, "")

    def _cancel_detail(self):
        if self._editing_offset is not None:
            self._load_detail(self._editing_offset)

    # ─────────────────────────── TAG INSERTION ─────────────────────────────

    def _insert_tag(self, open_tag: str, close_tag: str):
        """Wrap selected text in open/close tags, or insert pair at cursor."""
        tb = self._trans_box
        try:
            sel_start = tb.index("sel.first")
            sel_end   = tb.index("sel.last")
            sel_text  = tb.get(sel_start, sel_end)
            tb.delete(sel_start, sel_end)
            tb.insert(sel_start, f"{open_tag}{sel_text}{close_tag}")
            # Leave cursor after the inserted block
            tb.mark_set("insert",
                        f"{sel_start}+{len(open_tag) + len(sel_text) + len(close_tag)}c")
        except tk.TclError:
            # No selection — insert pair and leave cursor between them
            idx = tb.index("insert")
            tb.insert(idx, open_tag + close_tag)
            tb.mark_set("insert", f"{idx}+{len(open_tag)}c")
        tb.focus_set()

    def _insert_ruby(self):
        """Insert a ruby annotation template <base|rt> around selected text."""
        tb = self._trans_box
        try:
            sel_text = tb.get("sel.first", "sel.last")
            start    = tb.index("sel.first")
            tb.delete("sel.first", "sel.last")
            tb.insert(start, f"<{sel_text}|>")
            # Place cursor before the closing >  so translator can type the ruby
            tb.mark_set("insert", f"{start}+{len(sel_text) + 2}c")
        except tk.TclError:
            idx = tb.index("insert")
            tb.insert(idx, "<|>")
            tb.mark_set("insert", f"{idx}+1c")
        tb.focus_set()

    def _commit_translation(self, offset: int, new_text: str):
        row = next((r for r in self._grid_rows if r["offset"] == offset), None)
        if row is None or not self._tl_db:
            return
        if row["en"] == new_text:
            return

        # Write to DB
        if row["is_override"]:
            self._tl_db.override_translation_and_comment_for_offset(
                offset, new_text or None, None)
        else:
            self._tl_db.set_translation_and_comment_for_hash(
                row["jp_hash"], new_text or None, None)

        row["en"]   = new_text
        row["done"] = bool(new_text)

        self._modified = True
        self.mod_lbl.config(text="● unsaved", fg=C["warn"])

        # Patch grid row in-place (no full re-render)
        iid = f"O:{offset}"
        if self._grid.exists(iid):
            old_vals  = list(self._grid.item(iid, "values"))
            old_tags  = self._grid.item(iid, "tags")
            row_tag   = next((t for t in old_tags if t.startswith("row_")), "row_even")
            done_tag  = "done" if row["done"] else "todo"
            en_raw    = row["en"]
            disp_en   = _clean_for_grid(en_raw) if en_raw else ""
            old_vals[0] = "✓" if row["done"] else " "
            old_vals[5] = disp_en          # EN is column index 5 (sep1 at 2, sep2 at 4)
            self._grid.item(iid, values=old_vals, tags=(done_tag, row_tag))

        # Update scope bar progress
        total = len(self._grid_rows)
        done  = sum(1 for r in self._grid_rows if r["done"])
        pct   = (done * 100 / total) if total else 0.0
        scene = self._current_scene or "view"
        self._scope_lbl.config(
            text=f"  {scene}  —  {done}/{total}  ({pct:.1f}%)")

        self._set_status(f"Saved #{offset}  ({len(new_text)} chars)")
        self._update_progress()

    # ─────────────────────────── SEARCH / NAV ──────────────────────────────

    def _focus_search(self):
        self._search_entry.focus_set()
        self._search_entry.select_range(0, "end")

    def _search_next(self, _=None):
        rows = self._grid.get_children()
        if not rows:
            return
        sel = self._grid.focus()
        idx = rows.index(sel) if sel in rows else -1
        nxt = rows[(idx + 1) % len(rows)]
        self._grid.selection_set(nxt)
        self._grid.focus(nxt)
        self._grid.see(nxt)

    def _jump_dialog(self):
        if not self._tl_db:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Jump to Offset")
        dlg.geometry("300x110")
        dlg.configure(bg=C["bg2"])
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        fnt = C["ui"][0]

        tk.Label(dlg, text="Go to offset #:", font=(fnt, 10),
                 bg=C["bg2"], fg=C["fg"]).pack(pady=(14, 2))
        var = tk.StringVar()
        e   = tk.Entry(dlg, textvariable=var, font=(fnt, 10),
                       bg=C["bg3"], fg=C["fg"], insertbackground=C["fg"],
                       relief="flat", bd=0, highlightthickness=1,
                       highlightcolor=C["accent"],
                       highlightbackground=C["border"])
        e.pack(padx=20, fill="x", ipady=4)
        e.focus_set()

        def go():
            try:
                offset = int(var.get())
                dlg.destroy()
                self._jump_to_offset(offset)
            except ValueError:
                messagebox.showerror("Bad input", "Enter a number.", parent=dlg)

        e.bind("<Return>", lambda _: go())
        tk.Button(dlg, text="Go", command=go, font=(fnt, 9),
                  bg=C["bg4"], fg=C["fg"],
                  activebackground=C["accent"], activeforeground=C["bg"],
                  relief="flat", bd=0, cursor="hand2", padx=16, pady=3
                  ).pack(pady=8)

    def _jump_to_offset(self, offset: int):
        iid = f"O:{offset}"
        if self._grid.exists(iid):
            self._grid.selection_set(iid)
            self._grid.focus(iid)
            self._grid.see(iid)
            self._load_detail(offset)
        else:
            self._set_status(
                f"Offset #{offset} not in current view — try pressing ALL",
                C["warn"])

    def _find_replace_dialog(self):
        if not self._tl_db:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Find & Replace")
        dlg.geometry("480x200")
        dlg.configure(bg=C["bg2"])
        dlg.resizable(False, False)
        dlg.transient(self.root)
        fnt = C["ui"][0]

        def _row(label):
            f = tk.Frame(dlg, bg=C["bg2"])
            f.pack(fill="x", padx=16, pady=3)
            tk.Label(f, text=label, width=10, anchor="w",
                     font=(fnt, 10), bg=C["bg2"], fg=C["fg"]).pack(side="left")
            v = tk.StringVar()
            e = tk.Entry(f, textvariable=v, font=(fnt, 10),
                         bg=C["bg3"], fg=C["fg"], insertbackground=C["fg"],
                         relief="flat", bd=0, highlightthickness=1,
                         highlightcolor=C["accent"],
                         highlightbackground=C["border"])
            e.pack(side="left", fill="x", expand=True, ipady=3)
            return v, e

        tk.Label(dlg, text="Find & Replace in Translations",
                 font=(fnt, 9, "bold"), bg=C["bg2"], fg=C["fg2"]
                 ).pack(pady=(12, 4))
        fv, fe = _row("Find:")
        rv, _  = _row("Replace:")
        fe.focus_set()
        res_lbl = tk.Label(dlg, text="", font=(fnt, 9),
                           bg=C["bg2"], fg=C["fg2"])
        res_lbl.pack()

        def do_replace():
            find = fv.get()
            repl = rv.get()
            if not find:
                return
            count = 0
            for scene in self._tl_db.scene_names():
                for cmd in self._tl_db.lines_for_scene(scene):
                    tl = self._tl_db.tl_line_for_cmd(cmd)
                    if tl.en_text and find in tl.en_text:
                        new_t = tl.en_text.replace(find, repl)
                        if self._tl_db.tl_override_for_offset(cmd.offset):
                            self._tl_db.override_translation_and_comment_for_offset(
                                cmd.offset, new_t, None)
                        else:
                            self._tl_db.set_translation_and_comment_for_hash(
                                cmd.jp_hash, new_t, None)
                        count += 1
                        self._modified = True
            if count:
                self.mod_lbl.config(text="● unsaved", fg=C["warn"])
            # Refresh local cache
            for row in self._grid_rows:
                if row["en"] and find in row["en"]:
                    row["en"] = row["en"].replace(find, repl)
            self._refresh_grid()
            res_lbl.config(text=f"Replaced in {count} line(s).", fg=C["fg"])

        bf = tk.Frame(dlg, bg=C["bg2"])
        bf.pack(pady=8)
        tk.Button(bf, text="Replace All", command=do_replace, font=(fnt, 9),
                  bg=C["bg4"], fg=C["fg"],
                  activebackground=C["accent"], activeforeground=C["bg"],
                  relief="flat", bd=0, cursor="hand2", padx=16, pady=4
                  ).pack(side="left", padx=4)
        tk.Button(bf, text="Close", command=dlg.destroy, font=(fnt, 9),
                  bg=C["bg3"], fg=C["fg2"],
                  activebackground=C["bg4"], activeforeground=C["fg"],
                  relief="flat", bd=0, cursor="hand2", padx=12, pady=4
                  ).pack(side="left", padx=4)

    # ─────────────────────────── LINTER ────────────────────────────────────

    def _linter_dialog(self):
        if not self._tl_db:
            messagebox.showwarning("No DB", "Open a DB first.")
            return

        self._set_status("Running linter…")
        self.root.update_idletasks()
        issues = self._run_lint()

        scene_names = self._tl_db.scene_names()
        total = sum(len(self._tl_db.lines_for_scene(s)) for s in scene_names)
        done  = sum(
            sum(1 for l in self._tl_db.lines_for_scene(s)
                if self._tl_db.tl_line_with_hash(l.jp_hash).en_text)
            for s in scene_names)
        pct   = (done * 100 / total) if total else 0.0

        dlg = tk.Toplevel(self.root)
        dlg.title("Linter / Pre-patch Check")
        dlg.geometry("620x440")
        dlg.configure(bg=C["bg2"])
        dlg.transient(self.root)
        fnt = C["ui"][0]

        tk.Label(dlg,
                 text=(f"Translation Stats:  {done:,} / {total:,}  ({pct:.1f}%)   "
                       f"|   {len(issues)} issue(s) found"),
                 font=(fnt, 10, "bold"), bg=C["bg2"], fg=C["fg"]
                 ).pack(pady=(12, 4))

        txt = tk.Text(dlg, font=(fnt, 9), bg=C["bg3"], fg=C["fg"],
                      relief="flat", bd=0, state="normal")
        vsb = ttk.Scrollbar(dlg, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 8), pady=8)
        txt.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 8))

        if issues:
            txt.insert("end", "\n".join(issues))
        else:
            txt.insert("end", "✓ No issues found.  Safe to patch!")
        txt.config(state="disabled")

        tk.Button(dlg, text="Close", command=dlg.destroy, font=(fnt, 9),
                  bg=C["bg4"], fg=C["fg"],
                  activebackground=C["accent"], activeforeground=C["bg"],
                  relief="flat", bd=0, cursor="hand2", padx=16, pady=4
                  ).pack(pady=(0, 12))
        self._set_status("Linter done.")

    def _run_lint(self) -> list[str]:
        issues = []
        try:
            _root_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sys.path.insert(0, _root_dir)
            from luna_linter import (LintAmericanSpelling,
                                     LintLineLength,
                                     LintUntranslatedJapanese)
            linters = [LintAmericanSpelling(), LintLineLength(),
                       LintUntranslatedJapanese()]
        except ImportError:
            linters = []

        for scene in self._tl_db.scene_names():
            for cmd in self._tl_db.lines_for_scene(scene):
                tl = self._tl_db.tl_line_for_cmd(cmd)
                if not tl.en_text:
                    continue
                en = tl.en_text
                # Built-in: flag leftover CJK characters
                for ch in en:
                    if "\u3000" <= ch <= "\u9fff":
                        issues.append(
                            f"#{cmd.offset} [{scene}]: "
                            f"Possible untranslated Japanese: "
                            f"{en[:60]}…")
                        break
                for linter in linters:
                    try:
                        results = linter.lint(
                            scene, cmd.offset, en,
                            getattr(tl, "comment", None))
                        issues.extend(str(r) for r in results)
                    except Exception:
                        pass
        return issues

    # ─────────────────────────── DB OPERATIONS ─────────────────────────────

    def _open_db_path(self, path: str):
        """Load a DB from a known path (used for CLI arg or drag-drop)."""
        try:
            self._tl_db    = TranslationDb.from_file(path)
            self._db_path  = path
            self._modified = False
            self.mod_lbl.config(text="")
            self._populate_scene_tree()
            self._update_progress()
            self.root.title(
                f"deepLuna {self.VERSION}  —  {os.path.basename(path)}")
            self._set_status(f"Loaded: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _open_db(self):
        path = filedialog.askopenfilename(
            title="Open Translation DB",
            filetypes=[("JSON DB", "*.json"), ("All files", "*.*")],
            initialfile=Constants.DATABASE_PATH)
        if path:
            self._open_db_path(path)

    def _save_db(self):
        if not self._tl_db:
            messagebox.showwarning("No DB", "No translation DB loaded.")
            return
        path = self._db_path or Constants.DATABASE_PATH
        try:
            self._tl_db.to_file(path)
            self._modified = False
            self.mod_lbl.config(text="")
            self._set_status(f"Saved → {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ─────────────────────────── EXTRACT MRGs ──────────────────────────────

    def _extract_mrgs_dialog(self):
        """Dialog for selecting MRG files and running extraction."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Extract MRGs")
        dlg.geometry("520x230")
        dlg.configure(bg=C["bg2"])
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        fnt = C["ui"][0]

        tk.Label(dlg, text="Extract from MRG files",
                 font=(fnt, 11, "bold"), bg=C["bg2"], fg=C["fg"]
                 ).pack(pady=(14, 2))
        tk.Label(dlg,
                 text="Select both MRG files to build a new translation DB.",
                 font=(fnt, 9), bg=C["bg2"], fg=C["fg2"]).pack()

        allscr_var = tk.StringVar(value=self._allscr_path or Constants.ALLSCR_MRG)
        script_var = tk.StringVar(value=self._script_path or Constants.SCRIPT_TEXT_MRG)

        def _path_row(parent, label, var, title, sibling_var=None):
            f = tk.Frame(parent, bg=C["bg2"])
            f.pack(fill="x", padx=16, pady=4)
            tk.Label(f, text=label, width=16, anchor="w",
                     font=(fnt, 9), bg=C["bg2"], fg=C["fg"]).pack(side="left")
            e = tk.Entry(f, textvariable=var, font=(fnt, 9),
                         bg=C["bg3"], fg=C["fg2"], insertbackground=C["fg"],
                         relief="flat", bd=0, highlightthickness=1,
                         highlightcolor=C["accent"],
                         highlightbackground=C["border"])
            e.pack(side="left", fill="x", expand=True, ipady=3)

            def browse():
                p = filedialog.askopenfilename(
                    title=title,
                    filetypes=[("MRG files", "*.mrg"), ("All files", "*.*")])
                if p:
                    var.set(p)
                    if sibling_var:
                        sib = ("script_text.mrg"
                               if "allscr" in label.lower() else "allscr.mrg")
                        s = os.path.join(os.path.dirname(p), sib)
                        if os.path.exists(s) and not os.path.exists(
                                sibling_var.get().strip()):
                            sibling_var.set(s)

            tk.Button(f, text="…", font=(fnt, 9),
                      bg=C["bg3"], fg=C["fg2"],
                      relief="flat", bd=0, cursor="hand2", padx=6, pady=2,
                      command=browse).pack(side="left", padx=(4, 0))

        _path_row(dlg, "allscr.mrg:",      allscr_var,
                  "Select allscr.mrg",      script_var)
        _path_row(dlg, "script_text.mrg:", script_var,
                  "Select script_text.mrg", allscr_var)

        def do_extract():
            allscr = allscr_var.get().strip()
            script = script_var.get().strip()
            if not os.path.exists(allscr):
                messagebox.showerror("Not found",
                                     f"allscr.mrg not found:\n{allscr}",
                                     parent=dlg)
                return
            if not os.path.exists(script):
                messagebox.showerror("Not found",
                                     f"script_text.mrg not found:\n{script}",
                                     parent=dlg)
                return
            out_path = filedialog.asksaveasfilename(
                title="Save Translation DB As",
                defaultextension=".json",
                initialfile=Constants.DATABASE_PATH,
                filetypes=[("JSON DB", "*.json"), ("All files", "*.*")])
            if not out_path:
                return
            dlg.destroy()
            self._allscr_path = allscr
            self._script_path = script
            self._set_status("Extracting from MRG files… please wait")
            self.root.update_idletasks()

            def _do():
                try:
                    db = TranslationDb.from_mrg(allscr, script)
                    db.to_file(out_path)
                    self.root.after(0, lambda: self._on_extract_done(db, out_path))
                except Exception as exc:
                    tb = traceback.format_exc()
                    self.root.after(0, lambda: self._on_extract_error(exc, tb))

            threading.Thread(target=_do, daemon=True).start()

        bf = tk.Frame(dlg, bg=C["bg2"])
        bf.pack(pady=10)
        tk.Button(bf, text="Extract & Save…", command=do_extract, font=(fnt, 9),
                  bg=C["bg4"], fg=C["fg"],
                  activebackground=C["accent"], activeforeground=C["bg"],
                  relief="flat", bd=0, cursor="hand2", padx=16, pady=4
                  ).pack(side="left", padx=4)
        tk.Button(bf, text="Cancel", command=dlg.destroy, font=(fnt, 9),
                  bg=C["bg3"], fg=C["fg2"],
                  activebackground=C["bg4"], activeforeground=C["fg"],
                  relief="flat", bd=0, cursor="hand2", padx=12, pady=4
                  ).pack(side="left", padx=4)

    def _on_extract_done(self, db, out_path: str):
        self._tl_db    = db
        self._db_path  = out_path
        self._modified = False
        self.mod_lbl.config(text="")
        self._populate_scene_tree()
        self._update_progress()
        self.root.title(
            f"deepLuna {self.VERSION}  —  {os.path.basename(out_path)}")
        self._set_status(
            f"Extracted & saved → {os.path.basename(out_path)}", C["ok"])

    def _on_extract_error(self, exc: Exception, tb: str):
        self._set_status(f"Extract failed: {exc}", C["err"])
        messagebox.showerror("Extract Error", str(exc) + "\n\n" + tb)

    # ─────────────────────────── PATCH MRG ─────────────────────────────────

    def _patch_mrg(self):
        if not self._tl_db:
            messagebox.showwarning("No DB", "Load a DB first.")
            return
        out_path = filedialog.asksaveasfilename(
            title="Save Patched MRG",
            defaultextension=".mrg",
            initialfile=f"script_text_patched_{time.strftime('%Y%m%d-%H%M%S')}.mrg",
            filetypes=[("MRG files", "*.mrg"), ("All files", "*.*")])
        if not out_path:
            return
        self._set_status("Generating patched MRG…")
        self.root.update_idletasks()
        try:
            data = self._tl_db.generate_script_text_mrg()
            with open(out_path, "wb") as f:
                f.write(data)
            self._set_status(
                f"✔ Patched MRG saved → {os.path.basename(out_path)}", C["ok"])
            messagebox.showinfo("Done", f"Patched MRG written to:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Patch Error",
                                 f"{e}\n\n{traceback.format_exc()}")

    # ─────────────────────────── EXPORT ────────────────────────────────────

    def _export_scene(self):
        if not self._tl_db or not self._current_scene:
            messagebox.showwarning("No scene", "Select a scene first.")
            return
        out_dir = filedialog.askdirectory(title="Export Scene To Directory")
        if not out_dir:
            return
        self._tl_db.export_scene(self._current_scene, out_dir)
        self._set_status(f"Exported '{self._current_scene}' → {out_dir}")

    def _export_all(self):
        if not self._tl_db:
            messagebox.showwarning("No DB", "Load a DB first.")
            return
        out_dir = filedialog.askdirectory(title="Export All Scenes To Directory")
        if not out_dir:
            return
        self._set_status("Exporting all scenes…")
        self.root.update_idletasks()
        for scene in self._tl_db.scene_names():
            self._tl_db.export_scene(scene, out_dir)
        self._set_status(f"Exported all scenes → {out_dir}")

    # ─────────────────────────── HELPERS ───────────────────────────────────

    def _set_status(self, msg: str, color=None):
        self.status_var.set(msg)
        self.status_lbl.config(fg=color or C["fg2"])
        self.root.update_idletasks()

    def _on_quit(self):
        if self._modified:
            ans = messagebox.askyesnocancel(
                "Unsaved changes",
                "You have unsaved changes.\nSave before quitting?")
            if ans is None:
                return
            if ans:
                self._save_db()
        self.root.destroy()