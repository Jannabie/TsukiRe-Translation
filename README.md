# TsukiRe-Translator & mrg_tool

Kumpulan tools untuk membantu proses lokalisasi dan terjemahan game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung ekstraksi teks, editing lewat GUI, hingga repack ke format aslinya.

---

## TsukiRe-Translator (GUI Editor)

Tool utama untuk menerjemahkan tanpa perlu mengedit file teks mentah. Semua bisa langsung dilakukan lewat tampilan dua kolom yang sederhana dan jelas.

### Preview Interface
<p align="center">
  <img src="https://i.imgur.com/wxw2gl5.png" width="750" alt="GUI Preview">
</p>

### Fitur
- Visual Divider: Pemisah jelas antara kolom Original dan Translation
- Direct Editing: Double click untuk langsung mengedit terjemahan
- Route Tree: Navigasi berdasarkan route (Arcueid, Ciel, Common) dari `scene_map.json`
- Live Search: Pencarian dialog cepat dengan kata kunci

---

## mrg_tool (CLI & GUI Extractor)

Tool teknis untuk ekstrak dan injeksi file `script_text.mrg`

Repository:  
https://github.com/Jannabie/TsukiRe-mrg-txt

### Perbandingan Hasil Patch
<p align="center">
  <img src="https://i.imgur.com/Fl6iTqW.png" width="45%" />
  <img src="https://i.imgur.com/eEtdYFB.jpeg" width="45%" />
</p>

---

## Panduan Pasang Patch (LayeredFS)

LayeredFS memungkinkan modifikasi file game tanpa mengubah ROM asli. Cocok untuk testing di emulator maupun console.

### 1. Siapkan Folder Mod
- Yuzu / Ryujinx: Klik kanan game → Open Mod Data Location
- Buat folder baru (contoh: `TsukiRe_Indo_Patch`)
- Di dalamnya, buat folder `romfs`

### 2. Struktur File

Teks Script:  
`.../TsukiRe_Indo_Patch/romfs/script/script_text.mrg`

Custom Font (opsional):  
Letakkan di folder `ja`, `ja2`, atau `ja3` di dalam `romfs`

### 3. Path Default (PC)

Yuzu:  
`%AppData%\Roaming\yuzu\load\010064101344A000\[Nama Mod]\romfs`

Ryujinx:  
`%AppData%\Roaming\Ryujinx\mods\contents\010064101344a000\[Nama Mod]\romfs`

---

## Penjelasan Repacker

- Auto-Offset Calculation: Pointer dihitung ulang otomatis saat teks berubah
- 10-Section Management: Rebuild 10 bagian utama arsip MZP secara presisi
- Sector Precision: Mengikuti standar sektor `0x800` agar kompatibel dengan emulator dan Switch asli

---

## Cara Pakai

1. Jalankan `tsuki_trans.py`
2. Buka file `script_text.mrg`
3. Pilih route/scene di panel kiri
4. Terjemahkan di kolom kanan
5. Simpan project melalui File → Save Project (.tsproj)
6. Patch lewat File → Patch MRG untuk menghasilkan file baru
