# TsukiRe-Translator & mrg_tool

Kumpulan alat (tools) untuk proses lokalisasi game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung ekstraksi, pengeditan teks secara langsung dengan GUI, hingga pengemasan ulang (*repacking*) ke format aslinya.

---

## TsukiRe-Translator (GUI Editor)
Alat utama untuk menerjemahkan tanpa perlu berurusan dengan file teks mentah. Memungkinkan pengeditan langsung dengan tampilan dua kolom yang rapi dan terorganisir.

### Preview Interface
<div align="center">
  <table style="margin-left: auto; margin-right: auto;">
    <tr>
      <td align="center"><b>Tampilan Editor GUI</b></td>
    </tr>
    <tr>
      <td><img src="https://i.imgur.com/wxw2gl5.png" width="750" alt="GUI Preview"></td>
    </tr>
  </table>
</div>

**Fitur:**
- **Visual Divider:** Garis pemisah vertikal antar kolom (Original | Translation) untuk keterbacaan yang maksimal.
- **Direct Editing:** Klik dua kali pada kolom terjemahan untuk mengedit secara instan.
- **Route Tree:** Navigasi berdasarkan rute (Arcueid, Ciel, Common) yang sudah disortir secara otomatis menggunakan `scene_map.json`.
- **Live Search:** Mencari baris dialog tertentu dengan cepat berdasarkan kata kunci.

---

## mrg_tool (CLI & GUI Extractor)
Tool teknis untuk menangani ekstraksi dan injeksi file `script_text.mrg`.
**Repository:** [Jannabie/TsukiRe-mrg-txt](https://github.com/Jannabie/TsukiRe-mrg-txt)

### Perbandingan Hasil Patch
<div align="center">
  <table style="margin-left: auto; margin-right: auto;">
    <tr>
      <td align="center"><b>Sebelum (Original)</b></td>
      <td align="center"><b>Sesudah (Indonesian Patch)</b></td>
    </tr>
    <tr>
      <td><img src="https://i.imgur.com/Fl6iTqW.png" width="350"></td>
      <td><img src="https://i.imgur.com/eEtdYFB.jpeg" width="350"></td>
    </tr>
  </table>
</div>

---

## Panduan Pemasangan Patch (LayeredFS)
LayeredFS memungkinkan kita memodifikasi file game secara *on-the-fly* tanpa merubah file ROM asli. Gunakan metode ini untuk mengetes hasil terjemahan Anda di Emulator atau Console.

### 1. Persiapan Folder Mod
Buka folder modifikasi dengan cara:
- **Yuzu/Ryujinx:** Klik kanan pada game di daftar menu emulator, lalu pilih **Open Mod Data Location**.
- Buat folder baru di dalamnya (bebas, contoh: `TsukiRe_Indo_Patch`).
- Di dalam folder tersebut, buat folder lagi bernama `romfs`.

### 2. Struktur File
File hasil *repack* harus diletakkan sesuai dengan jalur aslinya di dalam folder `romfs`. Struktur akhirnya harus terlihat seperti ini:

**Untuk Teks Script:**
`.../TsukiRe_Indo_Patch/romfs/script/script_text.mrg`

**Untuk Custom Font (Jika ada):**
Pastikan diletakkan di dalam folder `ja`, `ja2`, atau `ja3` di bawah romfs.

### 3. Lokasi Path Default (PC)
- **Yuzu:** `%AppData%\Roaming\yuzu\load\010064101344A000\[Nama Mod]\romfs`
- **Ryujinx:** `%AppData%\Roaming\Ryujinx\mods\contents\010064101344a000\[Nama Mod]\romfs`

---

## Penjelasan Teknis Kompresor (Repacker)
Sistem pengemasan ulang pada tool ini memastikan stabilitas game dengan:
- **Auto-Offset Calculation:** Menghitung ulang seluruh tabel pointer secara otomatis saat panjang teks berubah agar tidak terjadi *crash*.
- **10-Section Management:** Rekonstruksi 10 bagian utama arsip MZP termasuk penyelarasan byte (*alignment*) yang presisi.
- **Sector Precision:** Mengikuti standar sektor `0x800` untuk kompatibilitas penuh pada emulator maupun hardware Switch asli.

---

## Cara Penggunaan

1. Jalankan `tsuki_trans.py`.
2. Buka file `script_text.mrg`.
3. Pilih rute/scene pada panel kiri, lalu mulai menerjemahkan di kolom kanan.
4. **Simpan Proyek:** Gunakan menu **File > Save Project (.tsproj)** untuk menyimpan progres.
5. **Patch Game:** Gunakan menu **File > Patch MRG** untuk menghasilkan file `.mrg` baru.

