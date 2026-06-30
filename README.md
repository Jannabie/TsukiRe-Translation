# deepLuna

A translation tool for **Tsukihime Remake** (`allscr.mrg` / `script_text.mrg`) with a modern GUI and CLI. Built based on concepts from the toolchain by [Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation), but rebuilt with a more intuitive interface, inline editing, tag validation, and a built-in linter.

>  **This tool only works on the Japanese version of Tsukihime Remake.** Other versions are not supported.

---

## Requirements

- Python 3.10+
- `tkinter` (already bundled with standard Python)
- `Pillow` (optional, only for legacy components)

```bash
pip install -r requirements.txt
```

---

## How to Run

```bash
python deepLuna.py                    # open GUI
python deepLuna.py deepluna_db.json   # load an existing DB directly
```

---

## GUI Workflow

After opening the application, there are two ways to start: if this is your first time, fill in the path to `allscr.mrg` and `script_text.mrg`, then click ** Extract MRGs** to create a new database. If you already have a previous `deepluna_db.json` file, click ** Open DB** directly.

Select a scene from the left panel to load it into the grid. **Double-click** a translation cell to edit it inline — `Enter` to save, `Esc` to cancel, `Tab` to save and move to the next line.

Click ** Save DB** to save progress to JSON, and ** Patch MRG** once ready to generate a patched `script_text.mrg` ready to use in the game.

---

## CLI Tools

```bash
python luna_cli.py --help     # export / import / patch without GUI
python luna_linter.py         # check the entire DB for tag issues
```

---

## Tag Reference

### Translation Format Tags

These tags are written inside the translated text.

| Tag | Effect | Notes |
|-----|------|---------|
| `%{i}…%{/i}` | Italic | Encoded to PUA in the final MRG |
| `%{g}…%{/g}` | Gray / inner monologue | Must be placed at the start of the entry |
| `%{ri}…%{/ri}` | Reverse italic | Write normal text; the encoder reverses it |
| `%{b}…%{/b}` | Bold | Legacy — identical to italic in the engine |
| `%{u}…%{/u}` | Underline | Removed during injection (engine doesn't support it) |
| `%{s}…%{/s}` | Strikethrough | Removed during injection (engine doesn't support it) |
| `%{n}` | Force line break | Becomes `\r\n` in the MRG |
| `#` | Line glue | Merges two consecutive MRG entries into one |

### Ruby Text (Furigana)

```
<text|reading>
```

**Example:** `<彼女|かのじょ>` will render 彼女 with かのじょ displayed above it.

>  **The reading field (right side of `|`) is removed during injection into the MRG** — only the display text makes it into the final binary. Do not put ASCII characters in the reading field, as this will cause a **freeze** on the HuneX engine.

### Game-Engine Tags (from the original JP text)

These tags already exist in the source JP text. Do not inject them manually into the translation — use the format tags above instead.

| Tag | Function |
|-----|------|
| `@g` | Gray style / inner monologue |
| `@b` | Bold + gray (always paired with `@g`) |
| `@t` | Tab / column alignment |
| `@k` | Pause/wait marker |
| `[ber00]` | Beep sound effect placeholder |
| `[zap00]` | Zap sound effect placeholder |
| `^` | Column separator / emphasis (multiple-choice display) |
| `■` (U+25A0) | Intentionally blanked out / censored text |

---

## Tag Validation

`tag_validator.py` runs automatically before MRG injection and also serves as the basis for the **Linter** feature (`Ctrl+L` in the GUI).

| Level | Example |
|---------|--------|
| **CRITICAL** | Ruby reading field contains ASCII → engine freeze |
| **ERROR** | `%{i}`, `%{g}`, `%{ri}` tags not closed; nested `%{ri}` |
| **WARNING** | Ruby without `\|` separator; `%{g}` mixed with `%{ri}`; string > 512 bytes |
| **INFO** | Ruby tag removed during injection; `%{b}` identical to `%{i}` |

---

## File Structure

```
deepLuna.py               ← entry point
luna_cli.py               ← headless CLI
luna_linter.py            ← translation linter
mrg_io.py                 ← MZP binary parser & packer
pua_encode.py             ← PUA font encoding
tag_validator.py          ← tag checker before injection
text_utils.py             ← tag registry & search helper
scene_map.json            ← scene-to-offset mapping
luna/
  constants.py            ← paths & configuration
  mrg_parser.py            ← MZP container parser
  mzx.py                  ← MZX decompressor
  ruby_utils.py            ← ruby text & line-break logic
  readable_exporter.py    ← easy-to-read export format
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

Built based on concepts from the original toolchain by [Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation).
