# TsukiRe-Translator & mrg_tool

Kumpulan alat (tools) untuk proses lokalisasi game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung ekstraksi, pengeditan teks secara langsung dengan GUI, hingga pengemasan ulang (*repacking*) ke format aslinya.

---

## 1. TsukiRe-Translator (GUI Editor)
Alat utama untuk menerjemahkan tanpa perlu berurusan dengan file teks mentah. Memungkinkan pengeditan langsung dengan tampilan dua kolom yang rapi dan terorganisir.

### Preview Interface
<p align="center">
  <kbd>
    <img src="https://i.imgur.com/wxw2gl5.png" width="750" alt="GUI Preview">
  </kbd>
</p>

**Fitur Unggulan:**
- **Visual Divider:** Garis pemisah vertikal antar kolom (Original | Translation) untuk keterbacaan yang maksimal.
- **Direct Editing:** Klik dua kali pada kolom terjemahan untuk mengedit secara instan.
- **Route Tree:** Navigasi berdasarkan rute (Arcueid, Ciel, Common) yang sudah disortir secara otomatis.
- **Live Search:** Mencari baris dialog tertentu dengan cepat berdasarkan keyword.

---

## 2. mrg_tool (CLI & GUI Extractor)
Tool teknis untuk menangani ekstraksi dan injeksi file `script_text.mrg`. 
**Repository:** [Jannabie/TsukiRe-mrg-txt](https://github.com/Jannabie/TsukiRe-mrg-txt)

### Perbandingan Hasil Patch
<p align="center">
  <table>
    <tr>
      <td align="center"><b>Sebelum (Original)</b></td>
      <td align="center"><b>Sesudah (Indonesian Patch)</b></td>
    </tr>
    <tr>
      <td><kbd><img src="https://i.imgur.com/Fl6iTqW.png" width="350"></kbd></td>
      <td><kbd><img src="https://i.imgur.com/eEtdYFB.jpeg" width="350"></kbd></td>
    </tr>
  </table>
</p>

### Preview Format Teks (.txt)
Jika Anda lebih suka pengeditan manual via teks editor, hasil ekstraksinya berbentuk seperti ini:
<p align="center">
  <kbd>
    <img src="https://i.imgur.com/yALew5y.png" width="450" alt="Preview TXT">
  </kbd>
  <br>
  <i>Hasil ekstraksi mempertahankan ID Offset agar bisa di-repack dengan tepat.</i>
</p>

---

## Penjelasan Teknis Kompresor (Repacker)
Sistem pengemasan ulang pada tool ini memastikan stabilitas game dengan:
- **Auto-Offset Calculation:** Menghitung ulang seluruh tabel pointer secara otomatis saat panjang teks berubah agar tidak terjadi *crash*.
- **10-Section Management:** Rekonstruksi 10 bagian utama arsip MZP termasuk penyelarasan byte (*alignment*) yang presisi.
- **Sector Precision:** Mengikuti standar sektor `0x800` untuk kompatibilitas penuh pada emulator maupun hardware Switch asli.

---

## Cara Penggunaan

### Menggunakan Translator GUI (Rekomendasi)
1. Jalankan `tsuki_trans.py`.
2. Buka file `script_text.mrg`.
3. Pilih rute/scene pada panel kiri, lalu mulai menerjemahkan di kolom kanan.

### Menggunakan mrg_tool (Manual)
**Ekstrak ke TXT:**
```bash
python mrg_tool.py extract script_text.mrg output.txt
