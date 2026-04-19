# TsukiRe-Translator & mrg_tool

Kumpulan tools buat bantu proses lokalisasi dan terjemahan game Tsukihime -A piece of blue glass moon- (Nintendo Switch). Bisa dipakai buat ekstrak teks, edit langsung lewat GUI, sampai repack ke format aslinya.

---

## TsukiRe-Translator (GUI Editor)

Tool utama buat nerjemahin tanpa harus ribet ngoprek file teks mentah. Semua bisa langsung diedit lewat tampilan dua kolom yang rapi.

### Preview Interface
<div align="center">
  <img src="https://i.imgur.com/wxw2gl5.png" width="750" alt="GUI Preview">
</div>

### Fitur
- Visual Divider: Ada garis pemisah antara kolom Original dan Translation biar lebih gampang dibaca
- Direct Editing: Tinggal double click di kolom terjemahan buat langsung edit
- Route Tree: Navigasi berdasarkan route (Arcueid, Ciel, Common) yang sudah otomatis tersusun dari `scene_map.json`
- Live Search: Cari dialog dengan cepat pakai kata kunci

---

## mrg_tool (CLI & GUI Extractor)

Tool teknis buat ekstrak dan injeksi file `script_text.mrg`

Repository:
https://github.com/Jannabie/TsukiRe-mrg-txt

### Perbandingan Hasil Patch
<div align="center">
  <img src="https://i.imgur.com/Fl6iTqW.png" width="350">
  <img src="https://i.imgur.com/eEtdYFB.jpeg" width="350">
</div>

---

## Panduan Pasang Patch (LayeredFS)

LayeredFS memungkinkan kita modifikasi file game tanpa mengubah ROM asli. Cocok buat testing di emulator atau console.

### 1. Siapkan Folder Mod
- Yuzu / Ryujinx: Klik kanan game → Open Mod Data Location
- Buat folder baru (contoh: `TsukiRe_Indo_Patch`)
- Di dalamnya, buat folder `romfs`

### 2. Struktur File

Teks Script:
.../TsukiRe_Indo_Patch/romfs/script/script_text.mrg

Custom Font (jika ada):
Letakkan di folder `ja`, `ja2`, atau `ja3` di dalam romfs

### 3. Path Default (PC)

Yuzu:
%AppData%\Roaming\yuzu\load\010064101344A000\[Nama Mod]\romfs

Ryujinx:
%AppData%\Roaming\Ryujinx\mods\contents\010064101344a000\[Nama Mod]\romfs

---

## Penjelasan Repacker

- Auto-Offset Calculation: Pointer dihitung ulang otomatis saat teks berubah supaya tidak crash
- 10-Section Management: Rebuild 10 bagian utama arsip MZP dengan alignment yang presisi
- Sector Precision: Mengikuti standar sektor 0x800 biar kompatibel di emulator dan Switch asli

---

## Cara Pakai

1. Jalankan `tsuki_trans.py`
2. Buka file `script_text.mrg`
3. Pilih route/scene di panel kiri
4. Mulai terjemahkan di kolom kanan
5. Save Project lewat File > Save Project (.tsproj)
6. Patch lewat File > Patch MRG untuk generate file baru
