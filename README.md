# TsukiRe-Translator

Editor GUI untuk menerjemahkan script game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch) langsung dari file `script_text.mrg`.

---

## Apa Ini?

`tsuki_trans.py` adalah editor bergaya Translator++ yang membaca file `script_text.mrg`, menampilkan setiap string dialog bersama kolom terjemahannya, lalu bisa menulis ulang file MRG yang sudah dipatch dan siap digunakan.

Navigasi scene dibantu oleh `scene_map.json` yang memetakan setiap offset string ke route (Arcueid, Ciel, Common) dan nama scene-nya masing-masing. Kedua file ini harus berada di folder yang sama saat dijalankan.

---

## Tampilan Editor

[![Tampilan Editor](https://i.imgur.com/wxw2gl5.png)](https://i.imgur.com/wxw2gl5.png)

Panel kiri menampilkan pohon navigasi berdasarkan route dan hari, panel kanan menampilkan grid dua kolom teks asli dan terjemahan, serta panel detail di bagian bawah untuk mengedit teks panjang dengan lebih leluasa.

---

## Cara Pakai

Jalankan editor dengan:

```bash
python tsuki_trans.py
```

Buka `script_text.mrg` lewat **File → Open MRG** atau `Ctrl+O`. Pilih scene dari panel kiri, klik dua kali sel terjemahan untuk mengedit, lalu tekan `Tab` untuk pindah ke baris berikutnya. Simpan progres lewat **File → Save Project** (`Ctrl+S`) yang menghasilkan file `.tsproj` — file ini bisa dibuka kembali kapan saja untuk melanjutkan kerja. Setelah selesai, hasilkan file MRG baru lewat **File → Patch MRG** (`Ctrl+P`).

### Pintasan Keyboard

| Tombol | Aksi |
|---|---|
| `Ctrl+O` | Buka file MRG |
| `Ctrl+S` | Simpan project |
| `Ctrl+P` | Patch dan hasilkan MRG baru |
| `Ctrl+F` | Fokus ke kotak pencarian |
| `Ctrl+G` | Lompat ke nomor offset tertentu |
| `Ctrl+H` | Find & Replace global |
| `Tab` | Simpan dan pindah ke baris berikutnya |
| `Ctrl+Enter` | Simpan terjemahan dari panel detail |

---

## Tools Pendukung

Untuk ekstraksi dan injeksi `script_text.mrg` di level biner, gunakan tool terpisah di repo berikut:

**[TsukiRe-mrg-txt](https://github.com/Jannabie/TsukiRe-mrg-txt)** — unpack dan repack file MRG.

Untuk memasang patch ke game (emulator maupun Switch asli), gunakan sistem **LayeredFS** dengan meletakkan `script_text.mrg` hasil patch di path berikut sesuai emulatornya:

Yuzu: `%AppData%\Roaming\yuzu\load\010064101344A000\[Nama Mod]\romfs\script\`

Ryujinx: `%AppData%\Roaming\Ryujinx\mods\contents\010064101344a000\[Nama Mod]\romfs\script\`

---

## Requirements

Python 3.8 atau lebih baru, dengan `tkinter` yang sudah terinstall otomatis bersama Python di Windows. Tidak ada dependensi eksternal lain.

---

## Disclaimer

Tool ini dibuat untuk keperluan edukasi dan lokalisasi personal. Gunakan sesuai aturan copyright dan Terms of Service dari game original.
