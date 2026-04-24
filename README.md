# deepLuna

A translation tool for **Tsukihime Remake** (`allscr.mrg` / `script_text.mrg`) with a modern GUI and CLI suite. Based on the original [Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation) toolchain, improved with a cleaner interface, inline editing, tag validation, and a linter.

> ⚠️ **This tool targets the Japanese version of Tsukihime Remake only.** It will not work with other releases or languages.

---

## Requirements

- Python 3.10+
- `tkinter` (bundled with standard Python)
- `Pillow` (optional, legacy only)

```bash
pip install -r requirements.txt
```

---

## Quick Start

```bash
python deepLuna.py                    # open GUI
python deepLuna.py deepluna_db.json   # auto-load an existing DB
```

---

## GUI Workflow

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [📂 Open DB] [⚙ Extract MRGs]  allscr.mrg: [__]  script_text.mrg: [__]  │
│                                              [▶ PATCH MRG]  [💾 Save DB] │
├──────────────────┬───────────────────────────────────────────────────────┤
│ SCENES           │  [🔍 search...]  ○ All  ○ Untranslated  ○ Translated  │
│ ► Arcueid  45%  ├───────────────────────────────────────────────────────│
│   ► Day 1       │  #  │  JP ORIGINAL         │  EN TRANSLATION           │
│     SCENE_001   │  1  │  彼女の声が…         │  Her voice…               │
│   ► Day 2       │  2  │  また明日            │  (untranslated)            │
│ ► Ciel  30%     │                                                         │
├──────────────────┴───────────────────────────────────────────────────────┤
│  Status message                                         Global: 38.4%    │
└──────────────────────────────────────────────────────────────────────────┘
```

1. **Extract MRGs** — set paths to `allscr.mrg` and `script_text.mrg`, click ⚙ Extract MRGs. Or open an existing `deepluna_db.json` with 📂 Open DB.
2. Click any scene in the left panel to load it.
3. **Double-click** a translation cell to edit. `Enter` saves, `Esc` cancels, `Tab` saves and moves to the next line.
4. **💾 Save DB** to persist your work as JSON.
5. **▶ Patch MRG** to generate the patched `script_text.mrg` ready for the game.

---

## CLI Tools

```bash
# Export / import / patch without the GUI
python luna_cli.py --help

# Lint the entire translation DB for tag issues
python luna_linter.py
```

---

## Tag Reference

### Translation Format Tags

These are written in your English translation text.

| Tag | Effect | Notes |
|-----|--------|-------|
| `%{i}…%{/i}` | Italic | PUA-encoded into final MRG |
| `%{g}…%{/g}` | Gray / inner monologue | Must start at position 0 of the entry |
| `%{ri}…%{/ri}` | Reverse italic | Write text normally; encoder reverses it |
| `%{b}…%{/b}` | Bold | Legacy — identical to italic in-engine |
| `%{u}…%{/u}` | Underline | Stripped (no engine support) |
| `%{s}…%{/s}` | Strikethrough | Stripped (no engine support) |
| `%{n}` | Forced line break | Becomes `\r\n` in MRG |
| `#` | Line glue | Merges two consecutive MRG entries as one |

### Ruby Text (Furigana)

```
<display|reading>
```

**Example:** `<彼女|かのじょ>` renders as 彼女 with かのじょ above it.

> ⚠️ **The reading field is stripped during MRG injection.** Only the display text is kept in the final binary. Do **not** put ASCII characters in the reading field — this causes a HuneX engine layout **freeze**.

### Game-Engine Tags (JP original, read-only)

These appear in the source JP text. Do not inject them manually in translations; use the format tags above instead.

| Tag | Meaning |
|-----|---------|
| `@g` | Gray / inner-monologue style |
| `@b` | Bold + gray (always paired with `@g`) |
| `@t` | Tab / column alignment |
| `@k` | Pause / wait marker |
| `[ber00]` | Beep / screech sound-FX placeholder |
| `[zap00]` | Zap sound-FX placeholder |
| `^` | Column separator / emphasis (dual-choice display) |
| `■` (U+25A0) | Intentionally-blank / censored text |

---

## Tag Validation

`tag_validator.py` is run automatically before MRG injection. It also backs the **Linter** (`Ctrl+L` in the GUI).

| Severity | Examples |
|----------|---------|
| **CRITICAL** | Ruby reading field contains ASCII → engine freeze |
| **ERROR** | Unclosed `%{i}`, `%{g}`, `%{ri}` pairs; nested `%{ri}` |
| **WARNING** | Malformed ruby (missing `\|`); `%{g}` mixed with `%{ri}`; strings > 512 bytes |
| **INFO** | Ruby tags stripped on injection; `%{b}` identical to `%{i}` |

---

## File Structure

```
deepLuna.py               ← entry point
luna_cli.py               ← headless CLI
luna_linter.py            ← translation linter
mrg_io.py                 ← MZP binary parser & packer
pua_encode.py             ← PUA font encoding
tag_validator.py          ← pre-injection tag checker
text_utils.py             ← tag registry & search helpers
scene_map.json            ← scene-to-offset mapping
luna/
  constants.py            ← paths & settings
  mrg_parser.py           ← MZP container parser
  mzx.py                  ← MZX decompressor
  ruby_utils.py           ← ruby text & line-break logic
  readable_exporter.py    ← human-readable export format
  translation_db.py       ← core DB (content-addressed by hash)
  ui/
    modern_window.py      ← main GUI
    information_window.py ← about dialog
tests/
  test_ruby_utils.py
  test_translation_db.py
```

---

## Credits

Based on the original toolchain by [Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation). This fork improves the GUI, adds inline editing, tag validation, and a linter for easier use.
