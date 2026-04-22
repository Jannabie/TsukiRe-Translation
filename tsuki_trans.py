#!/usr/bin/env python3
"""
tsuki_trans.py  —  Tsukihime Remake Script Translator
A Translator++-style GUI for translating script_text.mrg directly.

Layout:
  Left  — Route / Day / Scene tree + progress
  Right — Two-column translation grid (Original | Translation)
          with inline cell editing, live search, status filter

Workflow:
  1. Open script_text.mrg
  2. Click a scene in the tree
  3. Double-click any Translation cell → type → Enter to save
  4. File > Save Project (.tsproj) to keep your work
  5. File > Patch MRG to write a new script_text.mrg

Requires: Python 3.8+, tkinter (standard library)
Ships with: scene_map.json  (same folder as this script)
"""

import io, json, os, re, struct, sys, datetime, tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ═══════════════════════════════════════════════════════════════════════════
#  FONT DETECTION  —  find a font that can render Japanese + Latin on any OS
# ═══════════════════════════════════════════════════════════════════════════
def _detect_font(size=10):
    """Return a font family name that supports CJK + Latin on Windows/Mac/Linux."""
    import tkinter.font as tkf
    if sys.platform.startswith("win"):
        preferred = ["Meiryo UI", "Meiryo", "Yu Gothic UI", "Yu Gothic",
                     "MS Gothic", "MS Mincho", "Arial Unicode MS"]
    elif sys.platform == "darwin":
        preferred = ["Hiragino Kaku Gothic Pro", "Hiragino Sans",
                     "Osaka", "Arial Unicode MS"]
    else:
        preferred = ["Noto Sans CJK JP", "Noto Sans JP",
                     "IPAGothic", "TakaoGothic", "VL Gothic",
                     "WenQuanYi Micro Hei", "unifont"]

    try:
        available = set(tkf.families())
        for fam in preferred:
            # case-insensitive match
            if any(fam.lower() == a.lower() for a in available):
                return fam
    except Exception:
        pass
    return "TkDefaultFont"

# ═══════════════════════════════════════════════════════════════════════════
#  MZP BINARY PARSER / PACKER
# ═══════════════════════════════════════════════════════════════════════════
class _Mzp:
    MAGIC = b"mrgd00"; SEC = 0x800; FMT = "<HHHH"
    def __init__(self, path):
        raw = open(path, "rb").read()
        magic, n = struct.unpack_from("<6sH", raw, 0)
        assert magic == self.MAGIC, f"Not a valid MRG: {magic!r}"
        hdrs = [struct.unpack_from(self.FMT, raw, 8+8*i) for i in range(n)]
        base = 8 + 8*n
        self.data = []
        for so, bo, ss, sb in hdrs:
            start = base + so*self.SEC + bo
            size  = (ss*self.SEC & ~0xFFFF) | sb
            self.data.append(raw[start:start+size])

    @classmethod
    def pack(cls, sections):
        hdr = io.BytesIO(); hdr.write(struct.pack("<6sH", cls.MAGIC, len(sections)))
        body = io.BytesIO()
        for s in sections:
            while body.tell() % 16: body.write(b"\xff")
            p = body.tell()
            so, bo = p//cls.SEC, p%cls.SEC
            ss = len(s)//cls.SEC + (1 if len(s)%cls.SEC else 0)
            sb = len(s) & 0xFFFF
            hdr.write(struct.pack(cls.FMT, so, bo, ss, sb)); body.write(s)
        while (hdr.tell()+body.tell()) % 8: body.write(b"\xff")
        body.seek(0); hdr.write(body.read()); hdr.seek(0)
        return hdr.read()

def _parse_strings(path):
    m = _Mzp(path); ot, st = m.data[0], m.data[1]
    out = {}
    for i in range(len(ot)//4 - 1):
        ds, = struct.unpack(">I", ot[i*4:i*4+4])
        de_r = ot[(i+1)*4:(i+1)*4+4]
        if len(de_r) < 4: break
        de, = struct.unpack(">I", de_r)
        if ds == de or de == 0xFFFFFFFF: break
        out[i] = st[ds:de].decode("utf-8", errors="replace")
    return out

def _build_mrg(originals, translations, max_offset):
    ot_buf = io.BytesIO(); st_buf = io.BytesIO()
    for o in range(max_offset + 1):
        text = translations.get(o) or originals.get(o, "")
        if not text: continue
        ot_buf.write(struct.pack(">I", st_buf.tell()))
        st_buf.write(text.encode("utf-8"))
    ep = st_buf.tell()
    for _ in range(2): ot_buf.write(struct.pack(">I", ep))
    ot_buf.write(struct.pack(">I", 0xFFFFFFFF))
    ot, st = ot_buf.getvalue(), st_buf.getvalue()
    ec = max_offset + 1
    def pad(b):
        po, ps = io.BytesIO(), io.BytesIO()
        for _ in range(ec):
            po.write(struct.pack(">I", ps.tell())); ps.write(b)
        e = ps.tell()
        for _ in range(2): po.write(struct.pack(">I", e))
        po.write(struct.pack(">I", 0xFFFFFFFF))
        return po.getvalue(), ps.getvalue()
    nl_o, nl_s = pad(b"  \r\n")
    sp_o, sp_s = pad("\u3000\r\n".encode())
    return _Mzp.pack([ot,st, nl_o,nl_s, sp_o,sp_s, sp_o,sp_s, sp_o,sp_s])

# ═══════════════════════════════════════════════════════════════════════════
#  SCENE MAP
# ═══════════════════════════════════════════════════════════════════════════
def _load_scene_map():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scene_map.json")
    if not os.path.exists(p): return {}, {}, {}
    raw = json.load(open(p, encoding="utf-8"))
    o2s, sc_off = {}, {}
    for key, ranges in raw.items():
        parts = key.split("|")
        route, day, fname = parts[0], parts[1], parts[2]
        sk = (route, day, fname)
        sc_off[sk] = []
        for s, e in ranges:
            for o in range(s, e+1):
                o2s[o] = sk; sc_off[sk].append(o)
    RORDER = ["Common","Arcueid","Ciel","QA"]
    def dkey(d): m=re.search(r"(\d+)",d); return int(m.group(1)) if m else -1
    tree = {}
    for sk in sc_off:
        r,d,f = sk
        tree.setdefault(r,{}).setdefault(d,[]).append(f)
    for r in tree:
        for d in tree[r]: tree[r][d].sort()
        tree[r] = dict(sorted(tree[r].items(), key=lambda x: dkey(x[0])))
    return o2s, {r:tree[r] for r in RORDER if r in tree}, sc_off

# ═══════════════════════════════════════════════════════════════════════════
#  TEXT NORMALISATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _decode_pua(text):
    """Convert PUA chars (U+E000–U+E07F) back to their ASCII equivalents.

    The game engine encodes certain words in the Private Use Area to render
    them in a highlight colour at runtime:  U+E061 → 'a', U+E062 → 'b', …
    (each code point is the ASCII value + 0xE000).  Without decoding these,
    the characters appear as empty boxes in the GUI and are invisible to the
    search engine."""
    return ''.join(
        chr(ord(c) - 0xE000) if 0xE000 <= ord(c) <= 0xE07F else c
        for c in text
    )



# ═══════════════════════════════════════════════════════════════════════════
#  INLINE TAG REGISTRY
#  All tag types found in script_text.mrg + Tsukihimates translation format
# ═══════════════════════════════════════════════════════════════════════════
#
#  GAME-ENGINE TAGS (in ORIGINAL JP text)
#  @g        gray/inner-monologue style          127 occurrences, 131 strings
#  @b        bold style (always combined w/@g)     4 occurrences
#  @t        tab/column alignment (dual choices)   3 occurrences
#  @k        pause/wait marker                     1 occurrence
#  [ber00]   beep/screech sound-FX placeholder    52 occurrences
#  [zap00]   zap sound-FX placeholder              8 occurrences
#  ^         column-separator / emphasis marker    4 strings
#  ■ U+25A0  censored / intentionally-blank text  83 strings
#
#  TRANSLATION FORMAT TAGS (written by the translator)
#  %{i}…%{/i}  italic
#  %{b}…%{/b}  bold
#  %{u}…%{/u}  underline   (Tsukihimates spec)
#  %{s}…%{/s}  strikethrough (Tsukihimates spec)
#  #           line-glue marker (deepLuna: two consecutive MRG entries)
#  <text|ruby> furigana / ruby (allowed in EN per Tsukihimates guidelines)

_AT_TAG_RE   = re.compile(r'@[gbkt]')
_GAME_CMD_RE = re.compile(r'\[[a-z]{3}\d{2}\]')
_CARET_RE    = re.compile(r'\^')
_FMT_TAG_RE  = re.compile(r'%\{/?[a-z]\}')
_HASH_RE     = re.compile(r'#')

_FMT_PAIRS = {
    '%{i}': '%{/i}',
    '%{b}': '%{/b}',
    '%{u}': '%{/u}',
    '%{s}': '%{/s}',
}


def _strip_all_tags(text):
    """Strip every category of inline tag, leaving only readable content.
    Used for grid display and search normalisation.
    ■ (U+25A0) is intentional content and is preserved."""
    text = re.sub(r'<([^|>]+)\|[^>]*>', r'\1', text)  # <kanji|reading> → kanji
    text = _AT_TAG_RE.sub('', text)
    text = _GAME_CMD_RE.sub('', text)
    text = _CARET_RE.sub('', text)
    text = _FMT_TAG_RE.sub('', text)
    text = _HASH_RE.sub('', text)
    return text


def _validate_format_tags(text):
    """Return human-readable warnings for every mismatched %{x}…%{/x} pair."""
    warnings = []
    for open_tag, close_tag in _FMT_PAIRS.items():
        n_open  = len(re.findall(re.escape(open_tag),  text))
        n_close = len(re.findall(re.escape(close_tag), text))
        if n_open != n_close:
            name = open_tag[2:-1].upper()
            warnings.append(
                f'%{{{name}}}: {n_open} opening, {n_close} closing')
    return warnings

def _normalize_for_search(text):
    """Normalised, lowercased copy of *text* for substring search.
    Pipeline: decode PUA → strip ALL inline tags → collapse whitespace.
    Both the indexed strings AND the user query go through this function."""
    text = _decode_pua(text)
    text = _strip_all_tags(text)
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    text = text.replace('\u3000', ' ')
    text = re.sub(r' {2,}', ' ', text)
    return text.lower()


# ═══════════════════════════════════════════════════════════════════════════
#  COLOUR SCHEME  —  clean black & white, minimal
#  All colours are set after font detection in TsukiTrans.__init__
# ═══════════════════════════════════════════════════════════════════════════
def _build_palette(font_family):
    """Return a flat colour+font dict. Call once after font detection."""
    UI   = (font_family, 9)
    MONO = (font_family, 10)
    MONO_SM = (font_family, 9)
    MONO_LG = (font_family, 11)
    TITLE   = (font_family, 13, "bold")
    return {
        # backgrounds — range of near-blacks
        "bg":     "#0a0a0a",
        "bg2":    "#141414",
        "bg3":    "#1c1c1c",
        "bg4":    "#242424",
        "panel":  "#0f0f0f",
        "alt":    "#181818",   # alternating row tint
        # borders & separators
        "border": "#303030",
        # foreground
        "fg":     "#efefef",   # primary text  (bright white)
        "fg2":    "#888888",   # secondary text (mid gray)
        "fg3":    "#444444",   # tertiary  (dim gray)
        # interaction
        "accent": "#d0d0d0",   # selected/active (light gray)
        "sel":    "#2c2c2c",   # selection background
        "sel_fg": "#ffffff",
        # status
        "ok":     "#c8c8c8",
        "warn":   "#ffffff",
        "match":  "#ffffff",
        # route — keep very subtle so they don't distract
        "arc":    "#e0e0e0",
        "ciel":   "#cccccc",
        "common": "#b8b8b8",
        "qa":     "#a8a8a8",
        # fonts
        "ui":      UI,
        "mono":    MONO,
        "mono_sm": MONO_SM,
        "mono_lg": MONO_LG,
        "title":   TITLE,
    }

# Will be populated in TsukiTrans.__init__ after font detection
C = {}
ROUTE_C = {}

# ═══════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════
class TsukiTrans:
    VERSION = "1.0"

    def __init__(self, root, mrg_arg=None):
        self.root = root
        root.title("Tsukihime Script Translator")

        # ── font + palette (must happen before any widget) ──
        global C, ROUTE_C
        _font = _detect_font(10)
        C = _build_palette(_font)
        ROUTE_C = {
            "Arcueid": C["arc"],
            "Ciel":    C["ciel"],
            "Common":  C["common"],
            "QA":      C["qa"],
        }

        root.configure(bg=C["bg"]); root.geometry("1280x760"); root.minsize(960,600)

        # ── data ──
        self.originals     : dict[int,str] = {}     # offset → original text from MRG
        self.translations  : dict[int,str] = {}     # offset → user translation
        self.mrg_path      : str|None      = None
        self.proj_path     : str|None      = None
        self.o2s           : dict          = {}     # offset → (route,day,file)
        self.scene_tree    : dict          = {}
        self.scene_offsets : dict          = {}
        self.modified      : bool          = False

        # ── ui state ──
        self.current_scope : tuple|None    = None   # (route,day,file)|partial|None
        self._visible_rows : list[int]     = []     # offsets currently in table
        self._edit_widget  : tk.Widget|None= None
        self._edit_offset  : int|None      = None
        self._search_job   : str|None      = None
        self.search_var    = tk.StringVar()
        self.filter_var    = tk.StringVar(value="All")
        self.status_var    = tk.StringVar(value="Open a script_text.mrg to begin.")
        self.search_var.trace_add("write", self._on_search_change)
        self.filter_var.trace_add("write", self._refresh_table)

        # ── load scene map ──
        self.o2s, self.scene_tree, self.scene_offsets = _load_scene_map()

        self._build_menu()
        self._build_ui()
        self._apply_styles()

        if mrg_arg and os.path.exists(mrg_arg):
            root.after(120, lambda: self._load_mrg(mrg_arg))

    # ─────────────────────────── MENU ───────────────────────────────────
    def _build_menu(self):
        mb = tk.Menu(self.root, bg=C["bg2"], fg=C["fg"],
                     activebackground=C["accent"], activeforeground="#fff",
                     relief="flat", bd=0)
        self.root.configure(menu=mb)

        fm = tk.Menu(mb, tearoff=False, bg=C["bg2"], fg=C["fg"],
                     activebackground=C["accent"], activeforeground="#fff")
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="Open MRG…          Ctrl+O", command=self._open_mrg)
        fm.add_command(label="Open Project…      Ctrl+Shift+O", command=self._open_proj)
        fm.add_separator()
        fm.add_command(label="Save Project        Ctrl+S", command=self._save_proj)
        fm.add_command(label="Save Project As…   Ctrl+Shift+S", command=self._save_proj_as)
        fm.add_separator()
        fm.add_command(label="Patch MRG (Repack)  Ctrl+P", command=self._patch_mrg)
        fm.add_separator()
        fm.add_command(label="Quit", command=self._on_quit)

        em = tk.Menu(mb, tearoff=False, bg=C["bg2"], fg=C["fg"],
                     activebackground=C["accent"], activeforeground="#fff")
        mb.add_cascade(label="Edit", menu=em)
        em.add_command(label="Find…              Ctrl+F", command=self._focus_search)
        em.add_command(label="Find & Replace…    Ctrl+H", command=self._find_replace_dialog)
        em.add_separator()
        em.add_command(label="Jump to Offset…    Ctrl+G", command=self._jump_dialog)

        self.root.bind_all("<Control-o>", lambda e: self._open_mrg())
        self.root.bind_all("<Control-s>", lambda e: self._save_proj())
        self.root.bind_all("<Control-p>", lambda e: self._patch_mrg())
        self.root.bind_all("<Control-f>", lambda e: self._focus_search())
        self.root.bind_all("<Control-g>", lambda e: self._jump_dialog())
        self.root.bind_all("<Control-h>", lambda e: self._find_replace_dialog())
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

    # ─────────────────────────── UI BUILD ───────────────────────────────
    def _build_ui(self):
        # ── top bar ──
        top = tk.Frame(self.root, bg=C["bg"], height=42); top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="  Tsukihime Script Translator",
                 font=C["title"], bg=C["bg"], fg=C["fg"]).pack(side="left", padx=(12,0), pady=8)

        def tbtn(text, cmd, color=C["bg4"]):
            b = tk.Button(top, text=text, command=cmd, font=C["ui"],
                          bg=color, fg=C["fg"], activebackground=C["accent"],
                          activeforeground=C["bg"], relief="flat", bd=0,
                          cursor="hand2", padx=12, pady=3)
            b.pack(side="left", padx=3, pady=8); return b

        tbtn("Open MRG", self._open_mrg)
        tbtn("Save",     self._save_proj)
        tbtn("Patch MRG", self._patch_mrg, C["border"])

        self.mod_lbl = tk.Label(top, text="", font=C["ui"],
                                bg=C["bg"], fg=C["fg2"]); self.mod_lbl.pack(side="left", padx=4)
        self.status_lbl = tk.Label(top, textvariable=self.status_var, font=C["ui"],
                                   bg=C["bg"], fg=C["fg2"], anchor="e")
        self.status_lbl.pack(side="right", padx=16)

        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x")

        # ── main body ──
        body = tk.Frame(self.root, bg=C["bg"]); body.pack(fill="both", expand=True)

        # left panel
        self.left_panel = tk.Frame(body, bg=C["panel"], width=230)
        self.left_panel.pack(side="left", fill="y"); self.left_panel.pack_propagate(False)
        tk.Frame(body, bg=C["border"], width=1).pack(side="left", fill="y")

        # right panel
        right = tk.Frame(body, bg=C["bg"]); right.pack(side="left", fill="both", expand=True)

        self._build_left()
        self._build_right(right)

    def _build_left(self):
        P = self.left_panel
        # header
        hdr = tk.Frame(P, bg=C["bg3"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="  SCENES", font=C["ui"], bg=C["bg3"],
                 fg=C["fg2"]).pack(side="left", padx=6, pady=7)
        tk.Button(hdr, text="ALL", font=C["ui"], bg=C["bg4"], fg=C["fg"],
                  activebackground=C["accent"], activeforeground=C["bg"],
                  relief="flat", bd=0, cursor="hand2", padx=8, pady=2,
                  command=self._show_all).pack(side="right", padx=6, pady=5)

        # tree
        tf = tk.Frame(P, bg=C["panel"]); tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, style="L.Treeview", show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_sel)

        # progress section
        tk.Frame(P, bg=C["border"], height=1).pack(fill="x")
        self.prog_frame = tk.Frame(P, bg=C["panel"]); self.prog_frame.pack(fill="x", pady=4)

    def _build_right(self, parent):
        # ── search / filter bar ──
        bar = tk.Frame(parent, bg=C["bg2"], height=36); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="  Search:", font=C["ui"], bg=C["bg2"], fg=C["fg2"]
                 ).pack(side="left", padx=(8,0))
        self.search_entry = tk.Entry(bar, textvariable=self.search_var, font=C["mono_sm"],
                                     bg=C["bg3"], fg=C["fg"], insertbackground=C["fg"],
                                     relief="flat", bd=0,
                                     highlightthickness=1,
                                     highlightbackground=C["border"],
                                     highlightcolor=C["accent"])
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=6, pady=5)
        self.search_entry.bind("<Return>", self._search_next)
        self.search_entry.bind("<Escape>", lambda e: self.search_var.set(""))

        tk.Label(bar, text="Show:", font=C["ui"], bg=C["bg2"], fg=C["fg2"]
                 ).pack(side="left", padx=(8,2))
        flt = ttk.Combobox(bar, textvariable=self.filter_var, width=13,
                           values=["All","Untranslated","Translated"], state="readonly",
                           font=C["ui"])
        flt.pack(side="left", padx=(0,8), pady=4)
        self.match_lbl = tk.Label(bar, text="", font=C["ui"], bg=C["bg2"],
                                  fg=C["fg2"], width=20, anchor="e")
        self.match_lbl.pack(side="right", padx=10)

        # ── scope bar ──
        self.scope_bar = tk.Frame(parent, bg=C["bg3"], height=22); self.scope_bar.pack(fill="x")
        self.scope_bar.pack_propagate(False)
        self.scope_lbl = tk.Label(self.scope_bar, text="  All strings",
                                  font=C["ui"], bg=C["bg3"], fg=C["fg2"], anchor="w")
        self.scope_lbl.pack(fill="x", padx=8)

        # ── translation grid ──
        gf = tk.Frame(parent, bg=C["bg"]); gf.pack(fill="both", expand=True)

        # "div" is a narrow 1-px visual separator column between Original and Translation
        cols = ("status", "offset", "original", "div", "translation")
        self.grid = ttk.Treeview(gf, columns=cols, show="headings",
                                  style="G.Treeview", selectmode="browse")
        self.grid.heading("status",      text=" ",          anchor="center")
        self.grid.heading("offset",      text="#",          anchor="center")
        self.grid.heading("original",    text="Original",   anchor="w")
        self.grid.heading("div",         text="",           anchor="center")
        self.grid.heading("translation", text="Translation", anchor="w")

        self.grid.column("status",      width=24,  minwidth=24,  stretch=False, anchor="center")
        self.grid.column("offset",      width=64,  minwidth=52,  stretch=False, anchor="center")
        self.grid.column("original",    width=490, minwidth=180, stretch=True)
        self.grid.column("div",         width=14,  minwidth=14,  stretch=False, anchor="center")
        self.grid.column("translation", width=490, minwidth=180, stretch=True)

        vsb2 = ttk.Scrollbar(gf, orient="vertical",   command=self.grid.yview)
        hsb2 = ttk.Scrollbar(gf, orient="horizontal", command=self.grid.xview)
        self.grid.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        vsb2.pack(side="right", fill="y"); hsb2.pack(side="bottom", fill="x")
        self.grid.pack(fill="both", expand=True)

        self.grid.bind("<Double-Button-1>",  self._on_grid_double)
        self.grid.bind("<Return>",           self._on_grid_enter)
        self.grid.bind("<<TreeviewSelect>>", self._on_grid_sel)
        self.grid.bind("<Tab>",              self._on_tab)

        # ── detail / edit panel ──
        tk.Frame(parent, bg=C["border"], height=1).pack(fill="x")
        self.detail = tk.Frame(parent, bg=C["bg2"]); self.detail.pack(fill="x")
        self._build_detail()

    def _build_detail(self):
        D = self.detail
        top = tk.Frame(D, bg=C["bg2"]); top.pack(fill="x", padx=8, pady=(5,0))
        self.det_lbl = tk.Label(top, text="Select a row to view and edit",
                                font=C["ui"], bg=C["bg2"], fg=C["fg2"], anchor="w")
        self.det_lbl.pack(side="left", fill="x", expand=True)

        kbhint = tk.Label(top, text="Double-click / Enter = edit   Tab = next   Ctrl+Enter = save",
                          font=(C["ui"][0], 8), bg=C["bg2"], fg=C["fg3"])
        kbhint.pack(side="right", padx=4)

        # two-column detail: original (left) | translation edit (right)
        cols = tk.Frame(D, bg=C["bg2"]); cols.pack(fill="x", padx=8, pady=(3,6))

        # original — read only
        lf = tk.Frame(cols, bg=C["bg2"]); lf.pack(side="left", fill="both", expand=True, padx=(0,3))
        tk.Label(lf, text="Original", font=(C["ui"][0], 8, "bold"),
                 bg=C["bg2"], fg=C["fg3"]).pack(anchor="w")
        self.orig_box = tk.Text(lf, font=C["mono"], bg=C["bg3"], fg=C["fg2"],
                                relief="flat", bd=0, wrap="word", height=3,
                                state="disabled", cursor="arrow",
                                highlightthickness=1, highlightbackground=C["border"])
        self.orig_box.pack(fill="x")

        # translation — editable
        rf = tk.Frame(cols, bg=C["bg2"]); rf.pack(side="left", fill="both", expand=True, padx=(3,0))
        tlbl = tk.Frame(rf, bg=C["bg2"]); tlbl.pack(fill="x")
        tk.Label(tlbl, text="Translation", font=(C["ui"][0], 8, "bold"),
                 bg=C["bg2"], fg=C["fg3"]).pack(side="left")
        tk.Button(tlbl, text="Save  Ctrl+Enter", font=(C["ui"][0], 8),
                  bg=C["bg4"], fg=C["fg"], activebackground=C["accent"],
                  activeforeground=C["bg"], relief="flat", bd=0, cursor="hand2",
                  padx=8, pady=1, command=self._save_detail
                  ).pack(side="right")
        tk.Button(tlbl, text="Clear", font=(C["ui"][0], 8),
                  bg=C["bg3"], fg=C["fg2"], activebackground=C["bg4"],
                  activeforeground=C["fg"], relief="flat", bd=0, cursor="hand2",
                  padx=6, pady=1, command=self._clear_detail
                  ).pack(side="right", padx=4)
        # ── Format tag toolbar ──────────────────────────────────────────────
        ttbar = tk.Frame(rf, bg=C["bg2"])
        ttbar.pack(fill="x", pady=(2, 0))
        _tbtn_cfg = dict(
            font=(C["ui"][0], 8), bg=C["bg3"], fg=C["fg2"],
            activebackground=C["sel"], activeforeground=C["fg"],
            relief="flat", bd=0, cursor="hand2", padx=7, pady=1
        )
        tk.Button(ttbar, text="𝘐  Italic",  command=lambda: self._insert_fmt_tag("%{i}", "%{/i}"), **_tbtn_cfg).pack(side="left", padx=(0,2))
        tk.Button(ttbar, text="𝐁  Bold",    command=lambda: self._insert_fmt_tag("%{b}", "%{/b}"), **_tbtn_cfg).pack(side="left", padx=(0,2))
        tk.Button(ttbar, text="U  Under",   command=lambda: self._insert_fmt_tag("%{u}", "%{/u}"), **_tbtn_cfg).pack(side="left", padx=(0,2))
        tk.Button(ttbar, text="#  Glue",    command=lambda: self._insert_fmt_tag("#",    ""),       **_tbtn_cfg).pack(side="left", padx=(0,2))
        tk.Button(ttbar, text="<ruby|>",    command=self._insert_ruby_tag,                          **_tbtn_cfg).pack(side="left", padx=(0,2))
        self._tag_warn_lbl = tk.Label(ttbar, text="", font=(C["ui"][0], 8),
                                      bg=C["bg2"], fg="#cc7744", anchor="e")
        self._tag_warn_lbl.pack(side="right", padx=4)

        self.trans_box = tk.Text(rf, font=C["mono"], bg=C["bg3"], fg=C["fg"],
                                  insertbackground=C["fg"], relief="flat", bd=0,
                                  wrap="word", height=3, undo=True,
                                  highlightthickness=1, highlightbackground=C["border"],
                                  highlightcolor=C["accent"])
        self.trans_box.pack(fill="x")
        self.trans_box.bind("<Control-Return>", lambda e: self._save_detail())
        self.trans_box.bind("<Escape>",         lambda e: self._cancel_detail())
        self.trans_box.bind("<<Modified>>",     self._on_trans_modified)

    # ─────────────────────────── TTK STYLES ─────────────────────────────
    def _apply_styles(self):
        s = ttk.Style(); s.theme_use("default")
        fnt = C["ui"][0]   # detected CJK family

        # ── Left scene tree ──
        s.configure("L.Treeview",
                     background=C["panel"], foreground=C["fg"],
                     fieldbackground=C["panel"],
                     rowheight=22, font=(fnt, 9), borderwidth=0)
        s.map("L.Treeview",
              background=[("selected", C["sel"])],
              foreground=[("selected", C["sel_fg"])])

        # ── Translation grid ──
        # rowheight=24 → enough space for Japanese characters + some padding
        s.configure("G.Treeview",
                     background=C["bg2"], foreground=C["fg"],
                     fieldbackground=C["bg2"],
                     rowheight=24, font=(fnt, 10), borderwidth=0)
        s.map("G.Treeview",
              background=[("selected", C["sel"])],
              foreground=[("selected", C["sel_fg"])])
        s.configure("G.Treeview.Heading",
                     background=C["bg3"], foreground=C["fg2"],
                     font=(fnt, 9, "bold"), borderwidth=0, relief="flat")
        s.map("G.Treeview.Heading", relief=[("active", "flat")])

        # Alternating row colours — makes every other row slightly distinguishable
        self.grid.tag_configure("row_odd",  background=C["bg2"])
        self.grid.tag_configure("row_even", background=C["alt"])
        # Status tags (done/todo) control text brightness
        self.grid.tag_configure("done", foreground=C["fg"])
        self.grid.tag_configure("todo", foreground=C["fg2"])
        # Divider column "|" character — dim so it reads as a border, not content
        self.grid.tag_configure("div_col", foreground=C["fg3"])

        # ── Scrollbars ──
        for n in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            s.configure(n, background=C["bg4"], troughcolor=C["bg2"],
                        bordercolor=C["bg2"], arrowcolor=C["fg3"], relief="flat")

        # ── Combobox ──
        s.configure("TCombobox",
                     fieldbackground=C["bg3"], background=C["bg3"],
                     foreground=C["fg"], selectbackground=C["sel"],
                     arrowcolor=C["fg2"], borderwidth=0)
        s.map("TCombobox",
              fieldbackground=[("readonly", C["bg3"])],
              foreground=[("readonly", C["fg"])])

        # ── orig_box: game-engine inline tag colours ──
        fam = C["mono"][0]; sz = C["mono"][1]
        #  @g / @b marker characters — dim them so they don't distract
        self.orig_box.tag_configure("ot_marker",  foreground=C["fg3"])
        #  Content rendered in @g style (gray inner-monologue)
        self.orig_box.tag_configure("ot_gray",    foreground="#8090a0")
        #  Content rendered in @g @b style (bold gray)
        self.orig_box.tag_configure("ot_bold",    foreground="#8090a0", font=(fam, sz, "bold"))
        #  [ber00] / [zap00] sound-FX placeholders
        self.orig_box.tag_configure("ot_game",    foreground="#5588bb", background="#151e2a",
                                    font=(fam, sz, "bold"))
        #  ■ censored/blank text — muted with a visible tint
        self.orig_box.tag_configure("ot_black",   foreground="#666666", background="#1e1e1e")

        # ── trans_box: translation format tag colours ──
        #  %{i} %{/i} … — the marker tokens themselves are dimmed
        self.trans_box.tag_configure("ft_marker", foreground=C["fg3"])
        #  Italic region between %{i}…%{/i}
        self.trans_box.tag_configure("ft_italic", font=(fam, sz, "italic"), foreground=C["fg"])
        #  Bold region between %{b}…%{/b}
        self.trans_box.tag_configure("ft_bold",   font=(fam, sz, "bold"),   foreground=C["fg"])
        #  Bold+italic overlap
        self.trans_box.tag_configure("ft_ib",     font=(fam, sz, "bold italic"), foreground=C["fg"])
        #  # glue markers — tinted blue so translator notices them
        self.trans_box.tag_configure("ft_hash",   foreground="#5599cc", font=(fam, sz, "bold"))
        #  <text|ruby> in translation — amber tint
        self.trans_box.tag_configure("ft_ruby",   foreground="#aa9944")
        #  Unbalanced-tag warning highlight
        self.trans_box.tag_configure("ft_warn",   background="#2a1a00")

    # ─────────────────────────── TREE POPULATION ────────────────────────
    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self.scene_tree: return
        for route, days in self.scene_tree.items():
            rc = ROUTE_C.get(route, C["fg2"])
            n_route = sum(len(self.scene_offsets.get((route,d,f),[]))
                          for d,files in days.items() for f in files)
            rid = self.tree.insert("", "end", iid=f"R:{route}",
                                   text=f"  {route}  ({n_route:,})",
                                   tags=(f"rt_{route}",))
            self.tree.tag_configure(f"rt_{route}", foreground=rc)
            for day, files in days.items():
                dlabel = day if day else "root"
                did = self.tree.insert(rid, "end", iid=f"D:{route}:{day}",
                                       text=f"    {dlabel}", tags=("day",))
                self.tree.tag_configure("day", foreground=C["fg2"])
                for fname in files:
                    sk = (route, day, fname)
                    n = len(self.scene_offsets.get(sk, []))
                    short = fname.replace(".txt","")
                    self.tree.insert(did, "end", iid=f"F:{route}:{day}:{fname}",
                                     text=f"      {short}  ({n})", tags=("scene",))
                self.tree.tag_configure("scene", foreground=C["fg3"])

    def _update_progress(self):
        for w in self.prog_frame.winfo_children(): w.destroy()
        if not self.scene_tree: return
        fnt = C["ui"][0]
        tk.Label(self.prog_frame, text="  Progress", font=(fnt, 8, "bold"),
                 bg=C["panel"], fg=C["fg3"]).pack(anchor="w", padx=6, pady=(4,2))
        total_all = len(self.originals)
        done_all  = sum(1 for o,t in self.translations.items() if t and t.strip())
        for route in self.scene_tree:
            offsets = [o for o in self.originals
                       if self.o2s.get(o, (None,))[0] == route]
            total = len(offsets)
            if total == 0: continue
            done = sum(1 for o in offsets if self.translations.get(o,"").strip())
            pct  = done / total
            row  = tk.Frame(self.prog_frame, bg=C["panel"]); row.pack(fill="x", padx=6, pady=1)
            tk.Label(row, text=route, font=(fnt, 8), bg=C["panel"],
                     fg=C["fg2"], width=9, anchor="w").pack(side="left")
            # bar
            pb_out = tk.Frame(row, bg=C["bg3"], height=5, width=100)
            pb_out.pack(side="left", padx=3); pb_out.pack_propagate(False)
            if pct > 0:
                tk.Frame(pb_out, bg=C["fg2"], height=5,
                         width=max(2, int(100*pct))).place(x=0, y=0)
            tk.Label(row, text=f"{done}/{total}", font=(fnt, 8),
                     bg=C["panel"], fg=C["fg3"]).pack(side="left")
        if total_all:
            pct_all = done_all / total_all
            tk.Label(self.prog_frame,
                     text=f"  Total: {done_all:,}/{total_all:,}  ({pct_all:.1%})",
                     font=(fnt, 8), bg=C["panel"], fg=C["fg2"]
                     ).pack(anchor="w", padx=6, pady=(2,4))

    # ─────────────────────────── GRID POPULATION ────────────────────────
    def _get_scope_offsets(self):
        if self.current_scope is None:
            return sorted(self.originals.keys())
        route, day, fname = self.current_scope
        result = []
        for sk, offs in self.scene_offsets.items():
            r, d, f = sk
            if (r == route and
                (day  is None or d == day) and
                (fname is None or f == fname)):
                result.extend(offs)
        return sorted(set(result))

    def _refresh_table(self, *_):
        if self._search_job:
            self.root.after_cancel(self._search_job)
        self._search_job = self.root.after(120, self._do_refresh)

    def _on_search_change(self, *_):
        self._refresh_table()

    def _do_refresh(self):
        self._close_inline_editor(save=False)
        self.grid.delete(*self.grid.get_children())
        offsets = self._get_scope_offsets()

        sq   = self.search_var.get().strip().lower()
        # Normalise the query the same way we normalise source strings so that
        # ideographic spaces / whitespace differences are transparent.
        sq = sq.replace('\u3000', ' ')
        sq = re.sub(r' {2,}', ' ', sq)
        filt = self.filter_var.get()
        rows = []

        for o in offsets:
            orig    = self.originals.get(o, "")
            trans   = self.translations.get(o, "")
            is_done = bool(trans and trans.strip())

            if filt == "Untranslated" and is_done:     continue
            if filt == "Translated"   and not is_done: continue
            if sq:
                # Search normalised text so that:
                #   • PUA highlight chars (U+E0xx) are visible as plain ASCII
                #   • <kanji|reading> markup is transparent
                #   • internal \n / \r\n / \u3000 act as ordinary spaces
                orig_n  = _normalize_for_search(orig)
                trans_n = _normalize_for_search(trans)
                if sq not in orig_n and sq not in trans_n:
                    continue
            rows.append((o, orig, trans, is_done))

        self._visible_rows = [r[0] for r in rows]

        for idx, (o, orig, trans, is_done) in enumerate(rows):
            st_icon  = "+" if is_done else " "
            done_tag = "done" if is_done else "todo"
            row_tag  = "row_even" if idx % 2 == 0 else "row_odd"
            # Decode PUA + strip all inline tags for clean grid display.
            orig_disp = _strip_all_tags(_decode_pua(orig))
            orig_d = orig_disp.replace("\r\n", " / ").replace("\n", " / ").replace("\r", "").strip()[:120]
            tran_disp = _strip_all_tags(trans) if trans else ""
            tran_d = (tran_disp.replace("\r\n", " / ").replace("\n", " / ").replace("\r", "").strip()[:120]
                      if tran_disp else "")
            self.grid.insert("", "end", iid=f"O:{o}",
                             values=(st_icon, o, orig_d, "|", tran_d),
                             tags=(done_tag, row_tag))

        # Divider column: style it with dim color so "|" acts as visual separator
        self.grid.tag_configure("div_col", foreground=C["border"])

        total = len(offsets)
        shown = len(rows)
        done  = sum(1 for o in offsets if self.translations.get(o, "").strip())
        if sq or filt != "All":
            self.match_lbl.config(
                text=f"{shown:,} / {total:,} shown",
                fg=C["fg"] if shown else C["fg2"])
        else:
            self.match_lbl.config(
                text=f"{done:,} / {total:,} translated",
                fg=C["fg2"])

    # ─────────────────────────── TREE EVENTS ────────────────────────────
    def _show_all(self):
        self.current_scope = None
        self.scope_lbl.config(text="  All strings", fg=C["fg2"])
        self._do_refresh()

    def _on_tree_sel(self, _event):
        sel = self.tree.focus()
        if not sel: return
        if sel.startswith("R:"):
            route = sel[2:]
            self.current_scope = (route, None, None)
            self.scope_lbl.config(text=f"  Route: {route}", fg=C["fg2"])
        elif sel.startswith("D:"):
            _, route, day = sel.split(":", 2)
            self.current_scope = (route, day, None)
            self.scope_lbl.config(text=f"  {route}  /  {day or 'root'}", fg=C["fg2"])
        elif sel.startswith("F:"):
            _, route, day, fname = sel.split(":", 3)
            self.current_scope = (route, day, fname)
            self.scope_lbl.config(
                text=f"  {route}  /  {day or 'root'}  /  {fname.replace('.txt','')}",
                fg=C["fg2"])
        self._do_refresh()

    # ─────────────────────────── GRID EVENTS ────────────────────────────
    def _on_grid_sel(self, _):
        sel = self.grid.focus()
        if not sel or not sel.startswith("O:"): return
        o = int(sel[2:])
        self._load_detail(o)

    def _on_grid_double(self, event):
        col = self.grid.identify_column(event.x)
        # col "#5" = translation (was "#4" before adding the "div" column)
        if col == "#5":
            self._open_inline_editor()
        # clicking original or div column just loads detail (via sel event)

    def _on_grid_enter(self, _):
        self._open_inline_editor()

    def _on_tab(self, _):
        self._close_inline_editor(save=True)
        self._move_selection(+1)
        return "break"

    def _move_selection(self, delta):
        rows = self.grid.get_children()
        if not rows: return
        sel = self.grid.focus()
        if sel in rows:
            idx = rows.index(sel)
            nxt = rows[(idx + delta) % len(rows)]
        else:
            nxt = rows[0]
        self.grid.selection_set(nxt); self.grid.focus(nxt); self.grid.see(nxt)
        o = int(nxt[2:]); self._load_detail(o)

    # ─────────────────────────── INLINE EDITOR ──────────────────────────
    def _open_inline_editor(self):
        sel = self.grid.focus()
        if not sel or not sel.startswith("O:"): return
        o = int(sel[2:])
        bbox = self.grid.bbox(sel, "#5")   # "#5" = translation column (after div)
        if not bbox: return
        self._close_inline_editor(save=False)
        x, y, w, h = bbox
        current = self.translations.get(o, "")
        ent = tk.Entry(self.grid, font=C["mono_sm"],
                       bg=C["sel"], fg=C["sel_fg"],
                       insertbackground=C["fg"],
                       relief="flat", bd=0,
                       highlightthickness=1,
                       highlightbackground=C["accent"],
                       highlightcolor=C["accent"])
        ent.place(x=x, y=y, width=w, height=h)
        ent.insert(0, current); ent.select_range(0, "end"); ent.focus_set()
        self._edit_widget = ent; self._edit_offset = o
        ent.bind("<Return>",   lambda e: self._close_inline_editor(save=True))
        ent.bind("<Escape>",   lambda e: self._close_inline_editor(save=False))
        ent.bind("<Tab>",      lambda e: (self._close_inline_editor(save=True),
                                          self._move_selection(+1), "break"))
        ent.bind("<FocusOut>", lambda e: self._close_inline_editor(save=True))

    def _close_inline_editor(self, save=True):
        if self._edit_widget is None: return
        if save and self._edit_offset is not None:
            val = self._edit_widget.get().strip()
            self._set_translation(self._edit_offset, val if val else "")
        try: self._edit_widget.destroy()
        except: pass
        self._edit_widget = None; self._edit_offset = None

    # ─────────────────────────── DETAIL PANEL ───────────────────────────
    def _load_detail(self, offset):
        orig  = self.originals.get(offset, "")
        trans = self.translations.get(offset, "")
        sk    = self.o2s.get(offset, (None, None, None))
        loc   = " / ".join(p for p in sk if p)
        self.det_lbl.config(text=f"  #{offset}   {loc}", fg=C["fg2"])

        self.orig_box.config(state="normal")
        self.orig_box.delete("1.0","end")
        self.orig_box.insert("1.0", _decode_pua(orig))
        self._highlight_orig()         # apply game-engine tag colours
        self.orig_box.config(state="disabled")

        self.trans_box.delete("1.0","end")
        if trans: self.trans_box.insert("1.0", trans)
        self.trans_box.edit_reset()
        self.trans_box.edit_modified(False)
        self._highlight_trans()        # apply format tag colours
        self._editing_detail_offset = offset

    def _save_detail(self):
        o = getattr(self, "_editing_detail_offset", None)
        if o is None: return
        val = self.trans_box.get("1.0","end-1c").strip()
        self._set_translation(o, val)

    def _clear_detail(self):
        o = getattr(self, "_editing_detail_offset", None)
        if o is None: return
        self.trans_box.delete("1.0","end")
        self._set_translation(o, "")

    def _cancel_detail(self):
        o = getattr(self, "_editing_detail_offset", None)
        if o is not None: self._load_detail(o)

    # ─────────────────────────── FORMAT TAG HIGHLIGHTING ────────────────

    def _on_trans_modified(self, event=None):
        """Called by tk whenever trans_box text changes."""
        if self.trans_box.edit_modified():
            self._highlight_trans()
            self._live_validate_trans()
            self.trans_box.edit_modified(False)

    def _highlight_trans(self):
        """Render %{i}/%{b}/#/<ruby> tags visually inside trans_box."""
        tb = self.trans_box
        for tag in ("ft_marker","ft_italic","ft_bold","ft_ib","ft_hash","ft_ruby","ft_warn"):
            tb.tag_remove(tag, "1.0", "end")

        text = tb.get("1.0", "end-1c")
        if not text: return

        def pos(char_idx): return f"1.0+{char_idx}c"

        # Dim every %{x} / %{/x} marker token
        for m in _FMT_TAG_RE.finditer(text):
            tb.tag_add("ft_marker", pos(m.start()), pos(m.end()))

        # Highlight # glue marker
        for m in _HASH_RE.finditer(text):
            tb.tag_add("ft_hash", pos(m.start()), pos(m.end()))

        # <text|ruby> annotation in EN translation
        for m in re.finditer(r'<[^|>]+\|[^>]*>', text):
            tb.tag_add("ft_ruby", pos(m.start()), pos(m.end()))

        # Collect italic / bold ranges for overlap detection
        italic_set = set()
        bold_set   = set()

        for m in re.finditer(r'%\{i\}([\s\S]*?)%\{/i\}', text):
            cs, ce = m.start(1), m.end(1)
            italic_set.update(range(cs, ce))
            tb.tag_add("ft_italic", pos(cs), pos(ce))

        for m in re.finditer(r'%\{b\}([\s\S]*?)%\{/b\}', text):
            cs, ce = m.start(1), m.end(1)
            bold_set.update(range(cs, ce))
            tb.tag_add("ft_bold", pos(cs), pos(ce))

        # Upgrade overlapping bold+italic ranges to ft_ib
        overlap = sorted(italic_set & bold_set)
        if overlap:
            run_s = overlap[0]
            for k, p in enumerate(overlap[1:], 1):
                if p != overlap[k-1] + 1:
                    tb.tag_add("ft_ib", pos(run_s), pos(overlap[k-1]+1))
                    run_s = p
            tb.tag_add("ft_ib", pos(run_s), pos(overlap[-1]+1))

        # Warn on unmatched tags (paint background but don't remove highlights)
        warnings = _validate_format_tags(text)
        if warnings:
            for open_tag in _FMT_PAIRS:
                tag_name = open_tag[2:-1]     # 'i', 'b', …
                for m in re.finditer(re.escape(open_tag)
                                     + r'|' + re.escape(_FMT_PAIRS[open_tag]), text):
                    tb.tag_add("ft_warn", pos(m.start()), pos(m.end()))

    def _highlight_orig(self):
        """Apply game-engine tag colours inside orig_box (read-only).
        orig_box must already have its text inserted when this is called."""
        ob = self.orig_box
        for tag in ("ot_marker","ot_gray","ot_bold","ot_game","ot_black"):
            ob.tag_remove(tag, "1.0", "end")

        text = ob.get("1.0", "end-1c")
        if not text: return

        def pos(char_idx): return f"1.0+{char_idx}c"

        # [ber00] / [zap00] sound-FX placeholders
        for m in _GAME_CMD_RE.finditer(text):
            ob.tag_add("ot_game", pos(m.start()), pos(m.end()))

        # ■ censored text
        for m in re.finditer("■", text):
            ob.tag_add("ot_black", pos(m.start()), pos(m.end()))

        # @g, @b, @t, @k markers — dim the marker token itself
        for m in _AT_TAG_RE.finditer(text):
            ob.tag_add("ot_marker", pos(m.start()), pos(m.end()))

        # Content after @g is rendered gray in-game
        for m in re.finditer(r'@g', text):
            ob.tag_add("ot_gray", pos(m.end()), "end-1c")

        # Content after @b inside an @g block is bold-gray
        for m in re.finditer(r'@b', text):
            ob.tag_add("ot_bold", pos(m.end()), "end-1c")

    def _live_validate_trans(self):
        """Update the inline warning label while the translator types."""
        text = self.trans_box.get("1.0", "end-1c")
        warnings = _validate_format_tags(text)
        if warnings:
            self._tag_warn_lbl.config(text="⚠ " + "  ".join(warnings))
        else:
            self._tag_warn_lbl.config(text="")

    # ─────────────────────────── FORMAT TAG INSERTION ───────────────────

    def _insert_fmt_tag(self, open_tag, close_tag):
        """Wrap selected text (or a placeholder) with open_tag/close_tag."""
        tb = self.trans_box
        try:
            sel_s    = tb.index("sel.first")
            sel_e    = tb.index("sel.last")
            selected = tb.get(sel_s, sel_e)
            tb.delete(sel_s, sel_e)
            tb.insert(sel_s, open_tag + selected + close_tag)
            # Move cursor to end of inserted block
            tb.mark_set("insert", f"{sel_s}+{len(open_tag)+len(selected)+len(close_tag)}c")
        except tk.TclError:
            # No selection — insert at cursor with "text" placeholder
            cursor = tb.index("insert")
            if close_tag:
                placeholder = "text"
                tb.insert(cursor, open_tag + placeholder + close_tag)
                p_start = f"{cursor}+{len(open_tag)}c"
                p_end   = f"{cursor}+{len(open_tag)+len(placeholder)}c"
                tb.tag_add("sel", p_start, p_end)
                tb.mark_set("insert", p_end)
            else:
                tb.insert(cursor, open_tag)
        self._highlight_trans()
        self._live_validate_trans()
        tb.focus_set()

    def _insert_ruby_tag(self):
        """Insert a <text|reading> ruby annotation around the selection."""
        tb = self.trans_box
        try:
            sel_s    = tb.index("sel.first")
            sel_e    = tb.index("sel.last")
            selected = tb.get(sel_s, sel_e)
            tb.delete(sel_s, sel_e)
            inserted = f"<{selected}|reading>"
            tb.insert(sel_s, inserted)
            # Select the "reading" placeholder
            base = f"{sel_s}+{len(selected)+2}c"
            tb.tag_add("sel", base, f"{sel_s}+{len(inserted)-1}c")
            tb.mark_set("insert", f"{sel_s}+{len(inserted)-1}c")
        except tk.TclError:
            cursor = tb.index("insert")
            tb.insert(cursor, "<text|reading>")
            tb.tag_add("sel", f"{cursor}+6c", f"{cursor}+13c")
            tb.mark_set("insert", f"{cursor}+13c")
        self._highlight_trans()
        tb.focus_set()

    # ─────────────────────────── SAVE TRANSLATION ───────────────────────
    def _set_translation(self, offset, value):
        old = self.translations.get(offset, "")
        if old == value: return
        # ── Validate format tags before committing ──
        if value:
            warnings = _validate_format_tags(value)
            if warnings:
                msg = ("Mismatched format tags in translation:\n"
                       + "\n".join(f"  • {w}" for w in warnings)
                       + "\n\nSave anyway?")
                if not messagebox.askyesno("Tag Warning", msg, parent=self.root):
                    return
        if value:
            self.translations[offset] = value
        else:
            self.translations.pop(offset, None)
        self.modified = True
        self.mod_lbl.config(text="* unsaved")
        # Update grid row display
        iid = f"O:{offset}"
        if self.grid.exists(iid):
            is_done  = bool(value and value.strip())
            st_icon  = "+" if is_done else " "
            done_tag = "done" if is_done else "todo"
            tran_d   = (_strip_all_tags(value).replace("\r\n"," / ").replace("\n"," / ").strip()[:120]
                        if value else "")
            old_vals = list(self.grid.item(iid, "values"))
            # preserve alternating row tag
            old_tags = self.grid.item(iid, "tags")
            row_tag  = next((t for t in old_tags if t.startswith("row_")), "row_even")
            old_vals[0] = st_icon
            old_vals[4] = tran_d     # index 4 = translation (index 3 is now the "div" column)
            self.grid.item(iid, values=old_vals, tags=(done_tag, row_tag))
        self._set_status(f"Saved offset #{offset}  ({len(value)} chars)", C["fg"])
        self._update_progress()

    # ─────────────────────────── FILE OPERATIONS ────────────────────────
    def _open_mrg(self):
        p = filedialog.askopenfilename(title="Open script_text.mrg",
                                       filetypes=[("MRG","*.mrg"),("All","*.*")])
        if p: self._load_mrg(p)

    def _load_mrg(self, path):
        self._set_status("Loading MRG…", C["fg2"]); self.root.update_idletasks()
        try:
            self.originals    = _parse_strings(path)
            self.mrg_path     = path
            self.translations = {}
            self.modified     = False
            self.mod_lbl.config(text="")
            self._populate_tree(); self._show_all(); self._update_progress()
            self.root.title(f"Tsukihime Script Translator — {os.path.basename(path)}")
            self._set_status(f"Loaded {len(self.originals):,} strings from {os.path.basename(path)}")
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            self._set_status(f"Error: {ex}")

    def _open_proj(self):
        p = filedialog.askopenfilename(title="Open Project",
                                       filetypes=[("Project","*.tsproj"),("All","*.*")])
        if not p: return
        try:
            data = json.load(open(p, encoding="utf-8"))
            mrg  = data.get("mrg_path","")
            if not os.path.isabs(mrg):
                mrg = os.path.join(os.path.dirname(p), mrg)
            if not os.path.exists(mrg):
                mrg = filedialog.askopenfilename(
                    title="Locate script_text.mrg (moved?)",
                    filetypes=[("MRG","*.mrg"),("All","*.*")])
                if not mrg: return
            self._load_mrg(mrg)
            self.translations = {int(k):v for k,v in data.get("translations",{}).items()}
            self.proj_path    = p
            self.modified     = False; self.mod_lbl.config(text="")
            self._do_refresh(); self._update_progress()
            self.root.title(f"Tsukihime Script Translator — {os.path.basename(p)}")
            self._set_status(f"Project loaded: {len(self.translations):,} translations")
        except Exception as ex:
            messagebox.showerror("Open Error", str(ex)); self._set_status(f"Error: {ex}")

    def _save_proj(self):
        if not self.proj_path: self._save_proj_as(); return
        self._write_proj(self.proj_path)

    def _save_proj_as(self):
        if not self.mrg_path:
            messagebox.showwarning("No MRG", "Open an MRG first."); return
        default = os.path.splitext(self.mrg_path)[0] + ".tsproj"
        p = filedialog.asksaveasfilename(title="Save Project As",
                                          defaultextension=".tsproj",
                                          initialfile=os.path.basename(default),
                                          filetypes=[("Project","*.tsproj"),("All","*.*")])
        if p: self.proj_path = p; self._write_proj(p)

    def _write_proj(self, path):
        try:
            rel_mrg = os.path.relpath(self.mrg_path, os.path.dirname(path))
            data = {
                "version":      1,
                "mrg_path":     rel_mrg,
                "saved":        datetime.datetime.now().isoformat(),
                "translations": {str(k):v for k,v in self.translations.items()},
            }
            json.dump(data, open(path,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
            self.modified = False; self.mod_lbl.config(text="")
            done = sum(1 for v in self.translations.values() if v and v.strip())
            self._set_status(f"Project saved: {done:,} translations → {os.path.basename(path)}")
            self.root.title(f"Tsukihime Script Translator — {os.path.basename(path)}")
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex)); self._set_status(f"Error: {ex}")

    def _patch_mrg(self):
        if not self.originals:
            messagebox.showwarning("No data","Open an MRG first."); return
        done = sum(1 for v in self.translations.values() if v and v.strip())
        if done == 0:
            if not messagebox.askyesno("Patch MRG",
                    "No translations entered yet.\nPatch MRG with original text only?"): return
        p = filedialog.asksaveasfilename(
            title="Save Patched MRG As",
            defaultextension=".mrg",
            initialfile="script_text_patched.mrg",
            filetypes=[("MRG","*.mrg"),("All","*.*")])
        if not p: return
        self._set_status("Building MRG…", C["fg2"]); self.root.update_idletasks()
        try:
            packed = _build_mrg(self.originals, self.translations, max(self.originals.keys()))
            open(p,"wb").write(packed)
            sz = len(packed)/1024/1024
            self._set_status(
                f"Patched MRG written: {done:,} translations, {sz:.2f} MB → {os.path.basename(p)}")
        except Exception as ex:
            messagebox.showerror("Patch Error", str(ex)); self._set_status(f"Error: {ex}")

    # ─────────────────────────── SEARCH / NAV ───────────────────────────
    def _focus_search(self):
        self.search_entry.focus_set(); self.search_entry.select_range(0,"end")

    def _search_next(self, _=None):
        rows = self.grid.get_children()
        if not rows: return
        sel = self.grid.focus()
        if sel in rows:
            idx = rows.index(sel); nxt = rows[(idx+1) % len(rows)]
        else:
            nxt = rows[0]
        self.grid.selection_set(nxt); self.grid.focus(nxt); self.grid.see(nxt)

    def _jump_dialog(self):
        if not self.originals: return
        dlg = tk.Toplevel(self.root); dlg.title("Jump to Offset")
        dlg.geometry("300x110"); dlg.configure(bg=C["bg2"]); dlg.resizable(False,False)
        dlg.transient(self.root); dlg.grab_set()
        fnt = C["ui"][0]
        tk.Label(dlg, text="Go to offset #:", font=(fnt,10), bg=C["bg2"], fg=C["fg"]
                 ).pack(pady=(14,2))
        var = tk.StringVar()
        e = tk.Entry(dlg, textvariable=var, font=(fnt,10), bg=C["bg3"], fg=C["fg"],
                     insertbackground=C["fg"], relief="flat", bd=0,
                     highlightthickness=1, highlightcolor=C["accent"],
                     highlightbackground=C["border"])
        e.pack(padx=20, fill="x", ipady=4); e.focus_set()
        def go():
            try:
                o = int(var.get()); dlg.destroy(); self._jump_to_offset(o)
            except ValueError:
                messagebox.showerror("Bad input", "Enter a number.", parent=dlg)
        e.bind("<Return>", lambda _: go())
        tk.Button(dlg, text="Go", command=go, font=(fnt,9),
                  bg=C["bg4"], fg=C["fg"], activebackground=C["accent"],
                  activeforeground=C["bg"], relief="flat", bd=0,
                  cursor="hand2", padx=16, pady=3).pack(pady=8)

    def _jump_to_offset(self, offset):
        sk = self.o2s.get(offset)
        if sk:
            route, day, fname = sk
            self.current_scope = (route, day, fname)
            sel_key = f"F:{route}:{day}:{fname}"
            self.scope_lbl.config(
                text=f"  {route}  /  {day or 'root'}  /  {fname.replace('.txt','')}",
                fg=C["fg2"])
            try: self.tree.see(sel_key); self.tree.selection_set(sel_key)
            except: pass
        self._do_refresh()
        iid = f"O:{offset}"
        if self.grid.exists(iid):
            self.grid.selection_set(iid); self.grid.focus(iid); self.grid.see(iid)
            self._load_detail(offset)
        else:
            self._set_status(f"Offset #{offset} not in current view", C["fg2"])

    def _find_replace_dialog(self):
        if not self.originals: return
        dlg = tk.Toplevel(self.root); dlg.title("Find & Replace")
        dlg.geometry("480x200"); dlg.configure(bg=C["bg2"]); dlg.resizable(False,False)
        dlg.transient(self.root)
        fnt = C["ui"][0]

        def row(label):
            f = tk.Frame(dlg, bg=C["bg2"]); f.pack(fill="x", padx=16, pady=3)
            tk.Label(f, text=label, width=10, anchor="w", font=(fnt,10),
                     bg=C["bg2"], fg=C["fg"]).pack(side="left")
            v = tk.StringVar()
            e = tk.Entry(f, textvariable=v, font=(fnt,10), bg=C["bg3"], fg=C["fg"],
                         insertbackground=C["fg"], relief="flat", bd=0,
                         highlightthickness=1, highlightcolor=C["accent"],
                         highlightbackground=C["border"])
            e.pack(side="left", fill="x", expand=True, ipady=3)
            return v, e

        tk.Label(dlg, text="Find & Replace in Translations", font=(fnt,9,"bold"),
                 bg=C["bg2"], fg=C["fg2"]).pack(pady=(12,4))
        fv, fe = row("Find:")
        rv, _  = row("Replace:")
        fe.focus_set()
        res_lbl = tk.Label(dlg, text="", font=(fnt,9), bg=C["bg2"], fg=C["fg2"])
        res_lbl.pack()

        def do_replace():
            find = fv.get(); repl = rv.get()
            if not find: return
            count = 0
            for o, t in list(self.translations.items()):
                if find in t:
                    self.translations[o] = t.replace(find, repl); count += 1
                    self.modified = True; self.mod_lbl.config(text="* unsaved")
            self._do_refresh(); self._update_progress()
            res_lbl.config(text=f"Replaced {count} occurrence(s).", fg=C["fg"])

        bf = tk.Frame(dlg, bg=C["bg2"]); bf.pack(pady=8)
        tk.Button(bf, text="Replace All", command=do_replace, font=(fnt,9),
                  bg=C["bg4"], fg=C["fg"], activebackground=C["accent"],
                  activeforeground=C["bg"], relief="flat", bd=0,
                  cursor="hand2", padx=16, pady=4).pack(side="left", padx=4)
        tk.Button(bf, text="Close", command=dlg.destroy, font=(fnt,9),
                  bg=C["bg3"], fg=C["fg2"], activebackground=C["bg4"],
                  activeforeground=C["fg"], relief="flat", bd=0,
                  cursor="hand2", padx=12, pady=4).pack(side="left", padx=4)

    # ─────────────────────────── HELPERS ────────────────────────────────
    def _set_status(self, msg, color=None):
        self.status_var.set(msg)
        self.status_lbl.config(fg=color if color else C["fg2"])
        self.root.update_idletasks()

    def _on_quit(self):
        if self.modified:
            ans = messagebox.askyesnocancel(
                "Unsaved changes",
                "You have unsaved changes.\nSave before quitting?")
            if ans is None: return
            if ans: self._save_proj()
        self.root.destroy()

# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
def main():
    root = tk.Tk()
    app = TsukiTrans(root, mrg_arg=sys.argv[1] if len(sys.argv)>1 else None)
    root.mainloop()

if __name__ == "__main__":
    main()
