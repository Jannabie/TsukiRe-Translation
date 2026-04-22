# TsukiRe-Translator

Editor GUI untuk menerjemahkan script game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch) langsung dari file `script_text.mrg`.

---

## ⚠️ Catatan Penting

| | |
|---|---|
| 🎮 **Game Dump** | Game harus di-dump secara mandiri terlebih dahulu untuk mendapatkan file yang diperlukan. |
| 🇯🇵 **Versi Game** | Tool ini **hanya berfungsi pada versi Jepang** (`010064101344A000`). |
| 📄 **File Wajib** | `script_text.mrg` dari ROM dump + `scene_map.json` yang disertakan di repo ini. |

---

## Apa Ini?

`tsuki_trans.py` adalah editor bergaya Translator++ yang membaca `script_text.mrg` (format MRG biner milik engine HuneX/KiriKiriX), menampilkan **43.961 string** dialog dalam grid dua kolom (*Original* | *Translation*), lalu bisa menulis ulang MRG yang sudah dipatch dan siap dipakai di emulator.

Navigasi scene dibantu oleh `scene_map.json` — file JSON yang memetakan setiap offset string ke route (*Arcueid, Ciel, Common, QA*) beserta nama scene-nya. Kedua file ini harus berada di folder yang **sama** saat dijalankan.

---

## Tampilan Editor

[![Tampilan Editor](https://i.imgur.com/wxw2gl5.png)](https://i.imgur.com/wxw2gl5.png)

| Area | Fungsi |
|---|---|
| **Panel kiri** | Pohon navigasi Route → Hari → Scene, plus progress bar per-route |
| **Panel kanan atas** | Grid dua kolom Original / Translation + kolom status & offset |
| **Panel kanan bawah** | Detail editor untuk teks panjang + toolbar format tag |
| **Search bar** | Pencarian real-time di seluruh string atau scope yang dipilih |

---

## Cara Pakai

### 1 — Buka MRG
```
File → Open MRG…  (Ctrl+O)
```
Arahkan ke `script_text.mrg` hasil dump. Loading ~43k string membutuhkan beberapa detik.

### 2 — Navigasi Scene
Klik route/hari/scene di panel kiri untuk mempersempit tampilan grid.  
Tombol **ALL** di atas pohon mengembalikan ke tampilan semua string.

### 3 — Edit Terjemahan

**Cara cepat (inline):**  
Double-click sel kolom *Translation* di grid → ketik → `Enter` untuk simpan, `Escape` untuk batal, `Tab` untuk lanjut ke baris berikutnya.

**Cara detail (panel bawah):**  
Klik baris mana saja → teks asli dan terjemahan muncul di panel bawah → edit di kotak *Translation* → `Ctrl+Enter` atau tombol **Save**.

### 4 — Simpan Project
```
File → Save Project  (Ctrl+S)
```
Menyimpan progress ke file `.tsproj` (JSON). Bisa dibuka kembali kapan saja tanpa perlu MRG asli terbuka (MRG dimuat ulang otomatis dari path relatif yang tersimpan).

### 5 — Patch MRG
```
File → Patch MRG  (Ctrl+P)
```
Menghasilkan `script_text_patched.mrg` baru. File asli **tidak diubah**.

---

## Format Tag yang Didukung

Tool ini memahami dan menampilkan semua kategori tag yang ada di dalam script game maupun format penulisan terjemahan standar Tsukihimates.

### Tag Engine Game (di teks Original JP)

Tag-tag ini **tidak perlu ditulis ulang** dalam terjemahan — cukup diketahui supaya tidak terkejut saat melihatnya.

| Tag | Fungsi | Tampilan di Editor |
|---|---|---|
| `@g` | Gray / inner-monologue style | Teks setelahnya berwarna abu |
| `@b` | Bold (selalu kombinasi dengan `@g`) | Abu + tebal |
| `@t` | Tab alignment (untuk pilihan ganda) | Dimmed |
| `@k` | Pause / wait marker | Dimmed |
| `[ber00]` | Placeholder suara screech/beep | Highlight biru |
| `[zap00]` | Placeholder suara zap | Highlight biru |
| `^` | Column separator / emphasis | Dihapus dari tampilan |
| `■` | Teks tersensor intentional | Abu gelap — **tetap ditampilkan** |
| `<漢字\|ふりがな>` | Furigana / ruby text | Hanya kanji yang ditampilkan |
| `U+E0xx` | PUA highlight chars (kata berwarna) | Di-decode ke ASCII normal |

### Tag Format Terjemahan (ditulis oleh penerjemah)

| Tag | Fungsi | Contoh |
|---|---|---|
| `%{i}` … `%{/i}` | *Italic* | `%{i}Pitter patter%{/i}` |
| `%{b}` … `%{/b}` | **Bold** | `%{b}SHIKI%{/b}` |
| `%{u}` … `%{/u}` | Underline | `%{u}teks%{/u}` |
| `%{s}` … `%{/s}` | ~~Strikethrough~~ | `%{s}salah%{/s}` |
| `#` | Line-glue marker | `baris pertama#baris kedua` |
| `<teks\|ruby>` | Ruby annotation (EN) | `<Shiki\|シキ>` |

> **Tips toolbar:** Panel bawah menyediakan tombol **𝘐 Italic · 𝐁 Bold · U Under · # Glue · \<ruby|\>** — pilih teks lalu klik tombol untuk wrap otomatis. Jika tidak ada selection, placeholder `text` akan disisipkan.

### Live Validation

Editor secara real-time mendeteksi tag yang tidak seimbang saat mengetik:

```
⚠ %{I}: 1 opening, 0 closing
```

Dialog konfirmasi muncul jika kamu tetap ingin menyimpan meski ada tag mismatch.

---

## Pencarian

```
Search bar  (Ctrl+F)
```

Pencarian bersifat **tag-transparent** — kamu tidak perlu tahu apakah string yang kamu cari mengandung `@g`, furigana, `%{i}`, atau PUA chars. Ketik saja teks yang ingin dicari dalam bentuk biasa.

**Contoh yang sekarang berfungsi:**

| Query | Situasi |
|---|---|
| `aku merusak tempat tidur itu` | String mengandung PUA chars + internal newline |
| `bagaimana` | Kata ini ter-encode sebagai `\ue062\ue061\ue067...` di MRG |
| `畳` | Kanji terbungkus furigana `<畳\|くさ>` |
| `Pitter patter` | Teks di dalam tag `%{i}Pitter patter%{/i}` |

Filter dropdown **Untranslated / Translated** berfungsi bersamaan dengan search.

---

## Find & Replace

```
Edit → Find & Replace  (Ctrl+H)
```

Bekerja di seluruh terjemahan yang sudah diinput. Berguna untuk konsistensi istilah.

---

## Shortcut Keyboard

| Shortcut | Fungsi |
|---|---|
| `Ctrl+O` | Buka MRG |
| `Ctrl+S` | Simpan project |
| `Ctrl+P` | Patch MRG |
| `Ctrl+F` | Fokus ke search bar |
| `Ctrl+H` | Dialog Find & Replace |
| `Ctrl+G` | Jump ke offset tertentu |
| `Double-click` sel | Edit terjemahan inline |
| `Enter` | Konfirmasi edit inline |
| `Tab` | Simpan + pindah ke baris berikutnya |
| `Escape` | Batal edit |
| `Ctrl+Enter` | Simpan dari panel detail bawah |

---

## Memasang Patch ke Game (LayeredFS)

Letakkan `script_text.mrg` hasil Patch MRG di path berikut sesuai emulatornya. File ROM asli **tidak perlu diubah**.

**Yuzu / Suyu:**
```
%AppData%\Roaming\yuzu\load\010064101344A000\[Nama Mod]\romfs\script\
```

**Ryujinx:**
```
%AppData%\Roaming\Ryujinx\mods\contents\010064101344a000\[Nama Mod]\romfs\script\
```

`[Nama Mod]` bisa diisi bebas, misalnya `TsukiRe-ID`.

---

## Requirements

```
Python 3.8+
tkinter  (sudah include di instalasi Python standar)
```

Tidak ada dependency eksternal. Jalankan langsung:

```bash
python tsuki_trans.py
# atau dengan langsung membuka MRG:
python tsuki_trans.py path/ke/script_text.mrg
```

---

## File yang Diperlukan

| File | Sumber | Keterangan |
|---|---|---|
| `tsuki_trans.py` | Repo ini | Script utama editor |
| `scene_map.json` | Repo ini | Peta offset → route/scene |
| `script_text.mrg` | ROM dump sendiri | Script game (±5 MB) |

---

## Struktur Project yang Disimpan (`.tsproj`)

File project adalah JSON biasa yang bisa dibuka dengan teks editor:

```json
{
  "version": 1,
  "mrg_path": "script_text.mrg",
  "saved": "2025-04-22T10:00:00",
  "translations": {
    "201": "\"Bagaimana kamu merusak tempat tidur itu, Shiki-kun?\"",
    "202": "Dia terus bertanya %{i}bagaimana%{/i} aku merusak..."
  }
}
```

Path ke MRG disimpan relatif terhadap lokasi file `.tsproj`.

---

## Lisensi & Kredit

- Tool ini **bukan bagian resmi** dari proyek Tsukihimates.
- Referensi format script: [Tsukihimates/Tsukihime-Translation](https://github.com/Tsukihimates/Tsukihime-Translation)
- Referensi format MRG: [Hakanaou/deepLuna](https://github.com/Hakanaou/deepLuna)
- Tsukihime -A piece of blue glass moon- © TYPE-MOON
