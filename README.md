# TsukiRe-Translation

Kumpulan tool untuk membantu proses lokalisasi game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mencakup editor terjemahan berbasis GUI hingga repack file script ke format aslinya.

---

## Apa Ini?

Repo ini terdiri dari dua komponen utama yang bekerja bersama. **TsukiRe-Translator** (`tsuki_trans.py`) adalah editor GUI bergaya Translator++ untuk menerjemahkan isi file `script_text.mrg` secara langsung, tanpa perlu menyentuh file teks mentah. **mrg_tool** adalah tool terpisah yang menangani ekstraksi dan injeksi file MRG di level biner, tersedia di repo tersendiri.

Game ini menyimpan seluruh teks scriptnya dalam satu file bernama `script_text.mrg` dengan format MZP — sebuah arsip multi-section yang berisi string berindeks offset dalam encoding UTF-8. Editor ini membaca file tersebut, menampilkan setiap string bersama ruang untuk terjemahan, lalu bisa menulis ulang MRG yang sudah dipatch siap digunakan.

---

## TsukiRe-Translator — Editor GUI

### Tampilan Antarmuka

[![Tampilan Editor](https://i.imgur.com/wxw2gl5.png)](https://i.imgur.com/wxw2gl5.png)

Tampilan editor terbagi dua: panel kiri berisi pohon navigasi berdasarkan route (Arcueid, Ciel, Common) dan hari yang diambil dari `scene_map.json`, sementara panel kanan menampilkan grid dua kolom — teks asli Jepang di kiri, kolom terjemahan di kanan. Di bagian bawah ada panel detail yang menampilkan teks penuh dari baris yang dipilih sekaligus menjadi area pengetikan utama.

### Cara Pakai

Jalankan editor dengan perintah berikut, lalu ikuti alur kerjanya:

```bash
python tsuki_trans.py
```

Setelah terbuka, buka file `script_text.mrg` lewat **File → Open MRG** atau shortcut `Ctrl+O`. Pilih scene yang ingin dikerjakan dari panel kiri. Klik dua kali pada sel terjemahan di kolom kanan untuk mengedit langsung di baris tersebut, atau gunakan panel detail di bawah untuk mengedit dengan lebih leluasa. Tekan `Tab` untuk berpindah ke baris berikutnya secara otomatis.

Simpan progres kerja lewat **File → Save Project** (`Ctrl+S`) yang akan menghasilkan file `.tsproj`. File ini menyimpan seluruh terjemahan yang sudah dibuat beserta path ke MRG aslinya, sehingga sesi kerja bisa dilanjutkan kapan saja tanpa harus mengulang dari awal. Setelah terjemahan selesai, hasilkan file MRG baru lewat **File → Patch MRG** (`Ctrl+P`).

### Fitur Editor

Pencarian teks bisa dilakukan langsung dari kotak search di bagian atas grid — pencarian berjalan secara realtime saat mengetik. Filter "Untranslated / Translated / All" membantu fokus ke bagian yang belum selesai. Find & Replace global tersedia lewat `Ctrl+H` untuk mengganti satu istilah di seluruh file sekaligus. Navigasi ke offset tertentu bisa dilakukan lewat `Ctrl+G`.

Progress terjemahan per route ditampilkan secara langsung di panel kiri, sehingga bisa dilihat seberapa jauh tiap route sudah selesai tanpa perlu menghitung manual.

### Pintasan Keyboard

| Tombol | Aksi |
|---|---|
| `Ctrl+O` | Buka file MRG |
| `Ctrl+S` | Simpan project |
| `Ctrl+P` | Patch dan hasilkan MRG baru |
| `Ctrl+F` | Fokus ke kotak pencarian |
| `Ctrl+G` | Lompat ke nomor offset tertentu |
| `Ctrl+H` | Buka dialog Find & Replace |
| `Tab` | Simpan dan pindah ke baris berikutnya |
| `Enter` | Masuk ke mode edit sel |
| `Ctrl+Enter` | Simpan terjemahan dari panel detail |

### Tentang `scene_map.json`

File `scene_map.json` harus berada di folder yang sama dengan `tsuki_trans.py`. File ini memetakan setiap offset string ke route, hari, dan nama scene yang sesuai — inilah yang membuat pohon navigasi di panel kiri bisa menampilkan struktur route Arcueid, Ciel, dan Common secara terorganisir. Tanpa file ini editor tetap bisa berjalan, tapi semua string hanya akan muncul sebagai satu daftar flat tanpa navigasi scene.

---

## mrg_tool — Ekstrak & Injeksi MRG

Tool teknis untuk mengekstrak dan menyuntikkan file `script_text.mrg` di level biner tersedia di repo terpisah:

**[github.com/Jannabie/TsukiRe-mrg-txt](https://github.com/Jannabie/TsukiRe-mrg-txt)**


---

## Panduan Pasang Patch (LayeredFS)

LayeredFS memungkinkan modifikasi file game tanpa mengubah ROM asli — cocok untuk testing di emulator maupun di console asli.

### Tahap 1 — Siapkan Folder Mod

Di Yuzu atau Ryujinx, klik kanan game di library lalu pilih **Open Mod Data Location**. Buat folder baru di sana (contoh: `TsukiRe_Indo_Patch`), lalu di dalamnya buat subfolder bernama `romfs`.

### Tahap 2 — Letakkan File

File script yang sudah dipatch diletakkan di path berikut di dalam folder mod:

```
romfs/script/script_text.mrg
```

Jika ingin menggunakan custom font, letakkan file font di dalam folder `ja`, `ja2`, atau `ja3` yang berada di dalam `romfs`.

### Tahap 3 — Path Default per Emulator

Untuk **Yuzu**:
```
%AppData%\Roaming\yuzu\load\010064101344A000\[Nama Mod]\romfs
```

Untuk **Ryujinx**:
```
%AppData%\Roaming\Ryujinx\mods\contents\010064101344a000\[Nama Mod]\romfs
```

---

## Catatan Teknis Repacker

Saat melakukan patch MRG, offset pointer untuk setiap string dihitung ulang secara otomatis mengikuti perubahan panjang teks terjemahan — tidak perlu dilakukan manual. Arsip MZP yang dihasilkan dibangun ulang dengan presisi sektor `0x800` agar kompatibel baik dengan emulator maupun Switch asli.

---

## Requirements

Tool ini membutuhkan **Python 3.8 atau lebih baru** dan `tkinter` (sudah terinstall otomatis bersama Python di Windows). Tidak ada dependensi eksternal lain yang perlu diinstall.

---

## Disclaimer

Tool ini dibuat untuk keperluan edukasi dan lokalisasi personal. Pengguna bertanggung jawab penuh untuk memastikan penggunaannya sesuai dengan aturan copyright dan Terms of Service dari game original.
