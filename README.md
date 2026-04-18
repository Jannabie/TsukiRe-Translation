# mrg_tool & TsukiRe-Translator

Kumpulan alat (tools) untuk proses lokalisasi game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung ekstraksi, pengeditan teks secara langsung, hingga pengemasan ulang (*repacking*) ke format aslinya.

---

## 1. TsukiRe-Translator (GUI Editor)
Alat utama untuk menerjemahkan tanpa perlu berurusan dengan file teks mentah. Memungkinkan pengeditan langsung dengan tampilan dua kolom yang rapi.

### Preview Interface
<p align="center">
  <img src="https://i.imgur.com/wxw2gl5.png" width="700" alt="GUI Preview">
</p>

**Fitur Unggulan:**
- **Visual Divider:** Garis pemisah vertikal antar kolom (Original | Translation) untuk keterbacaan yang lebih baik.
- **Direct Editing:** Klik dua kali pada kolom terjemahan untuk mengedit secara instan.
- **Route Tree:** Navigasi mudah berdasarkan rute (Arcueid, Ciel, Common) yang sudah disortir.
- **Live Search:** Mencari baris dialog tertentu dengan cepat.

---

## 2. mrg_tool (CLI & GUI Extractor)
Tool teknis untuk menangani file `script_text.mrg` (format arsip MZP/mrgd00).

### Perbandingan Hasil Patch
| Sebelum (Original) | Sesudah (Indonesian Patch) |
| :---: | :---: |
| ![Sebelum](https://i.imgur.com/Fl6iTqW.png) | ![Sesudah](https://i.imgur.com/eEtdYFB.jpeg) |

### Preview Format Teks (.txt)
Jika Anda lebih suka mengedit via teks editor (seperti Notepad++/VS Code), hasil ekstraksinya akan terlihat seperti ini:
<p align="center">
  <img src="https://i.imgur.com/yALew5y.png" width="450" alt="Preview TXT">
</p>

---

## Detail Teknis Repacker
Sistem pengemasan ulang (`repack`) pada tool ini memastikan stabilitas game dengan:
- **Auto-Offset Calculation:** Menghitung ulang tabel pointer secara otomatis saat panjang teks berubah.
- **10-Section Management:** Menyusun ulang 10 bagian utama arsip MZP termasuk penyelarasan byte (*alignment*).
- **Sector Precision:** Memastikan kompatibilitas penuh pada sektor `0x800` untuk emulator dan hardware asli.

---

## Cara Penggunaan

### Meng
