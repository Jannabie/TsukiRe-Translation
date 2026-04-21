# TsukiRe-Translator

Editor GUI untuk menerjemahkan script game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch) langsung dari file `script_text.mrg`.

---

## ⚠️ Catatan Penting
* **Game Dump:** Game harus di-dump terlebih dahulu secara mandiri untuk mendapatkan file yang diperlukan.
* **Versi Game:** Tool ini hanya bisa dilakukan dan berfungsi pada **Versi Jepang**.

---

## Apa Ini?

`tsuki_trans.py` adalah editor bergaya Translator++ yang membaca file `script_text.mrg`, menampilkan setiap string dialog bersama kolom terjemahannya, lalu bisa menulis ulang file MRG yang sudah dipatch dan siap digunakan.

Navigasi scene dibantu oleh `scene_map.json` yang memetakan setiap offset string ke route (Arcueid, Ciel, Common) dan nama scene-nya masing-masing. Kedua file ini harus berada di folder yang sama saat dijalankan.

---

## Tampilan Editor

[![Tampilan Editor](https://i.imgur.com/wxw2gl5.png)](https://i.imgur.com/wxw2gl5.png)

Panel kiri menampilkan pohon navigasi berdasarkan route dan hari, panel kanan menampilkan grid dua kolom teks asli dan terjemahan, serta panel detail di bagian bawah untuk mengedit teks panjang dengan lebih leluasa.

---

## Memasang Patch ke Game (LayeredFS)

Letakkan `script_text.mrg` hasil repack di path berikut sesuai emulatornya, tanpa mengubah file ROM asli:

**Yuzu:** `%AppData%\Roaming\yuzu\load\010064101344A000\[Nama Mod]\romfs\script\`

**Ryujinx:** `%AppData%\Roaming\Ryujinx\mods\contents\010064101344a000\[Nama Mod]\romfs\script\`


