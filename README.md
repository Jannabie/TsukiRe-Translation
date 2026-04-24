# deepLuna

Tool terjemahan untuk **Tsukihime Remake** (`allscr.mrg` / `script_text.mrg`) dengan GUI modern dan CLI. Dibuat berdasarkan konsep dari toolchain milik [Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation), namun dibangun ulang dengan tampilan yang lebih mudah dipahami, editing inline, validasi tag, dan linter bawaan.

> ⚠️ **Tool ini hanya bekerja pada versi Jepang dari Tsukihime Remake.** Versi lain tidak didukung.

---

## Persyaratan

- Python 3.10+
- `tkinter` (sudah bundled di Python standar)
- `Pillow` (opsional, hanya untuk komponen legacy)

```bash
pip install -r requirements.txt
```

---

## Cara Menjalankan

```bash
python deepLuna.py                    # buka GUI
python deepLuna.py deepluna_db.json   # langsung load DB yang sudah ada
```

---

## Alur Kerja GUI

Setelah membuka aplikasi, ada dua cara untuk mulai: jika baru pertama kali, isi path ke `allscr.mrg` dan `script_text.mrg` lalu klik **⚙ Extract MRGs** untuk membuat database baru. Jika sudah punya file `deepluna_db.json` sebelumnya, langsung klik **📂 Open DB**.

Pilih scene dari panel kiri untuk memuatnya ke grid. **Double-click** cell terjemahan untuk mengedit secara inline — `Enter` untuk simpan, `Esc` untuk batal, `Tab` untuk simpan dan lanjut ke baris berikutnya.

Klik **💾 Save DB** untuk menyimpan progress ke JSON, dan **▶ Patch MRG** saat sudah siap untuk menghasilkan `script_text.mrg` yang sudah ditambal dan siap dipakai di game.

---

## CLI Tools

```bash
python luna_cli.py --help     # export / import / patch tanpa GUI
python luna_linter.py         # cek seluruh DB untuk masalah tag
```

---

## Referensi Tag

### Tag Format Terjemahan

Tag-tag ini ditulis di dalam teks terjemahan.

| Tag | Efek | Catatan |
|-----|------|---------|
| `%{i}…%{/i}` | Italic | Di-encode ke PUA di MRG final |
| `%{g}…%{/g}` | Abu-abu / inner monologue | Harus diletakkan di awal entry |
| `%{ri}…%{/ri}` | Reverse italic | Tulis teks normal, encoder yang membalik |
| `%{b}…%{/b}` | Bold | Legacy — identik dengan italic di engine |
| `%{u}…%{/u}` | Underline | Dihapus saat injeksi (engine tidak mendukung) |
| `%{s}…%{/s}` | Strikethrough | Dihapus saat injeksi (engine tidak mendukung) |
| `%{n}` | Paksa ganti baris | Menjadi `\r\n` di MRG |
| `#` | Line glue | Menggabungkan dua entry MRG berurutan menjadi satu |

### Ruby Text (Furigana)

```
<teks|bacaan>
```

**Contoh:** `<彼女|かのじょ>` akan merender 彼女 dengan かのじょ di atasnya.

> ⚠️ **Field bacaan (kanan dari `|`) dihapus saat injeksi ke MRG** — hanya teks tampilan yang masuk ke binary final. Jangan menaruh karakter ASCII di field bacaan karena akan menyebabkan **freeze** pada HuneX engine.

### Tag Game-Engine (dari teks JP asli)

Tag ini sudah ada di teks sumber JP. Jangan diinject secara manual di terjemahan — gunakan tag format di atas sebagai gantinya.

| Tag | Fungsi |
|-----|--------|
| `@g` | Gaya abu-abu / inner monologue |
| `@b` | Bold + abu-abu (selalu berpasangan dengan `@g`) |
| `@t` | Tab / perataan kolom |
| `@k` | Penanda jeda / tunggu |
| `[ber00]` | Placeholder efek suara beep |
| `[zap00]` | Placeholder efek suara zap |
| `^` | Pemisah kolom / penekanan (tampilan pilihan ganda) |
| `■` (U+25A0) | Teks yang sengaja dikosongkan / disensor |

---

## Validasi Tag

`tag_validator.py` dijalankan otomatis sebelum injeksi MRG dan juga menjadi dasar fitur **Linter** (`Ctrl+L` di GUI).

| Tingkat | Contoh |
|---------|--------|
| **CRITICAL** | Field bacaan ruby berisi ASCII → freeze engine |
| **ERROR** | Tag `%{i}`, `%{g}`, `%{ri}` tidak ditutup; `%{ri}` bersarang |
| **WARNING** | Ruby tanpa pemisah `\|`; `%{g}` dicampur `%{ri}`; string > 512 byte |
| **INFO** | Tag ruby dihapus saat injeksi; `%{b}` identik dengan `%{i}` |

---

## Struktur File

```
deepLuna.py               ← entry point
luna_cli.py               ← CLI headless
luna_linter.py            ← linter terjemahan
mrg_io.py                 ← parser & packer binary MZP
pua_encode.py             ← encoding font PUA
tag_validator.py          ← pemeriksa tag sebelum injeksi
text_utils.py             ← registry tag & helper pencarian
scene_map.json            ← pemetaan scene ke offset
luna/
  constants.py            ← path & konfigurasi
  mrg_parser.py           ← parser container MZP
  mzx.py                  ← dekompresor MZX
  ruby_utils.py           ← logika ruby text & line-break
  readable_exporter.py    ← format ekspor yang mudah dibaca
  translation_db.py       ← inti DB (content-addressed by hash)
  ui/
    modern_window.py      ← GUI utama
    information_window.py ← dialog about
tests/
  test_ruby_utils.py
  test_translation_db.py
```

---

## Kredit

Dibuat berdasarkan konsep dari toolchain asli milik [Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation).
