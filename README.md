---

# FINAL PROJECT SISTECH 2026 — Path Machine Learning Operations

---
## Checkpoint 1 Feature Engineering & Pseudo Labeling

#### Fondasi Sistem Prediksi *Risk Score* (Chicago Crimes → Proxy Koordinat Jabodetabek)


Group Number : 6
---

###### Name : 

* ###### Renata Gabetta Ruth Evifanita Simarmata
* ###### Shabrina Nur Izzati



#### 1\. Ringkasan 

Notebook ini adalah deliverable **Checkpoint 1** dari Final Project MLOps SISTECH 2026, yang menjadi fondasi bagi sistem prediksi **Risk Score** end-to-end (skor risiko 0–100 untuk suatu lokasi pada waktu tertentu, berdasarkan pola kejahatan historis). Risk Score ini nantinya dikonsumsi lewat REST API oleh tim Front-End sebagai bagian dari platform **Women Safety \& Smart Protection**, proyek lintas-path bersama tim Product Management, Business Analysis \& Strategy, UI/UX, dan Front-End Engineering.

Karena dataset kejahatan yang tersedia (Chicago Crimes) belum memiliki padanan dataset Indonesia yang setara, sementara path lain di grup mendesain aplikasi untuk wilayah **Jabodetabek**, notebook ini juga melakukan transformasi koordinat proxy dari Chicago ke bounding box Jabodetabek, semata untuk membuktikan metodologi (proof-of-concept) — bukan sebagai representasi geografis riil Indonesia.

**Cakupan CP1 :** *Pseudo-Labeling \& Feature Engineering*.



#### 2\. Alur \& Metodologi

Alur Notebook : **Load → Cleaning → Transformasi Koordinat → Feature Engineering → Pseudo-Labeling (severity → temporal decay → spatial decay → normalisasi) → Export**.



##### 2.1 Load Dataset

* Sumber: Chicago Crimes (2001–sekarang)
* Kolom yang diambil: `ID`, `Date`, `Primary Type`, `Description`, `Location Description`, `Arrest`, `Latitude`, `Longitude`, `Year`, dengan dtype dioptimasi (`category` untuk kolom kategorikal, `boolean`/`Int16`) agar hemat memori.
* **Shape mentah:** 8.534.663 baris.
* **Strategi subset — 3 tahun terakhir** (`N\_YEARS = 3`): mengambil data 2024–2026 saja → **553.919 baris**. Justifikasi: pola kejahatan yang terlalu lama (>3 tahun) relevansinya sudah banyak berkurang (lihat juga temporal decay di bawah) dan kurang mencerminkan kondisi terkini, sekaligus menjaga notebook tetap ringan dijalankan berulang selama development.



##### 2.2 Kualitas \& Persiapan Data

Pemeriksaan dilakukan sebelum data dipakai lebih lanjut:

|Pemeriksaan|Hasil|
|-|-|
|Struktur \& tipe data|553.919 baris x 9 kolom, tipe data sudah sesuai (category/boolean/Int16/float64)|
|Missing values|`Latitude`/`Longitude`: 0,55%; `Location Description`: 0,46%; kolom lain 0%|
|Duplikat (baris penuh \& `ID`)|0 baris duplikat penuh, 0 `ID` duplikat|
|Outlier/anomali koordinat|Difilter dengan bounding box kasar Chicago (`41.60–42.05° LU`, `-87.95– -87.50° BT`) untuk membuang koordinat rusak/typo|
|Parsing tanggal|Format `MM/DD/YYYY HH:MM:SS AM/PM` → datetime, baris gagal parse dibuang|

**Hasil akhir cleaning:** 550.896 baris tersisa dari 553.919 (**99,5%** data valid).



##### 2.3 Transformasi Koordinat: Chicago → Jabodetabek (Proxy)

Karena empat path lain di grup finpro mendesain untuk konteks Jabodetabek, koordinat kejadian ditransformasi dengan **normalisasi min-max linear per-axis**, memetakan rentang `Latitude`/`Longitude` hasil cleaning ke bounding box representatif Jabodetabek:

|Batas|Nilai|Keterangan|
|-|-|-|
|`lat\_new\_min`|-6.55|batas selatan (Jakarta, Depok, sebagian Bogor)|
|`lat\_new\_max`|-6.10|batas utara (pesisir Jakarta Utara)|
|`lon\_new\_min`|106.55|batas barat (sebagian besar Tangerang)|
|`lon\_new\_max`|107.05|batas timur (Kota Bekasi \& sebagian Kab. Bekasi)|

Arah relatif dipertahankan (titik paling utara/timur di Chicago tetap paling utara/timur di Jabodetabek), sehingga pola spasial (hotspot, klaster) tetap konsisten posisi relatifnya, hanya "berpindah label" geografis. Koordinat asli disimpan di `Latitude\_Chicago\_orig`/`Longitude\_Chicago\_orig` dan hasil transformasi divalidasi dengan assertion (`between(lat\_new\_min, lat\_new\_max)`) serta visual scatter before/after.

Catatan (sesuai arahan FAQ Final Project): dataset Chicago Crimes untuk saat ini hanya dipakai untuk membuktikan model secara metodologis, bukan representasi akurat kondisi Jabodetabek. 


##### 2.4 Feature Engineering

**Temporal — Cyclical Encoding.** Jam (`hour`), hari (`dow`), dan bulan (`month`) dienkode sebagai pasangan `(sin, cos)` dengan periode masing-masing 24, 7, dan 12, supaya kedekatan siklikal (jam 23 dekat dengan jam 0) terepresentasi dengan benar secara numerik — dibuktikan lewat perhitungan jarak Euclidean: jarak `23→0` jauh lebih kecil dibanding `0→12`.

**Spasial — Grid Aggregation.** Koordinat kontinu dibulatkan ke grid diskrit (`lat\_r`, `lon\_r`) agar bisa diagregasi per lokasi:

* `ROUND\_DECIMALS = 2` (\~1 km per sel) → **1.001 sel unik grid**.
* Resolusi ini dipilih (setelah proses debugging) karena resolusi lebih halus (3 desimal, \~110 m) menghasilkan kepadatan sel yang berlebihan relatif terhadap radius pencarian tetangga (rata-rata tetangga meledak ke ribuan), sehingga smoothing spasial menyebar ke area yang sebenarnya tidak relevan.


##### 2.5 Pseudo-Labeling → Risk Score

Karena dataset tidak menyediakan Risk Score secara langsung, target dibentuk lewat 5 tahap:

**a) Severity Scoring (fallback 3-tier).** Setiap kejadian diberi skor keparahan 0–100 berdasarkan kombinasi `(Primary Type, Description)`, dengan urutan mengikuti *Hierarchy Rule* FBI UCR (nyawa > kekerasan fisik > kerugian materi):

|Tier|Kondisi|Persentase data|
|-|-|-|
|1 — Exact match|Kombinasi spesifik ada di tabel manual|89,9%|
|2 — Fallback per Primary Type|Kombinasi tidak ada, tapi kategori besarnya dikenal|9,7%|
|3 — Fallback global|Kategori besar pun tidak dikenal|0,4%|

Tier 3 yang kecil (0,4%) mengonfirmasi tabel severity manual sudah cukup representatif untuk sebagian besar data.

**b) Temporal Decay (Recency).** `w\_time = exp(-λ · usia\_hari)`, exponential decay dengan **half-life 180 hari** — kejadian setahun lalu masih menyumbang \~25% bobot penuhnya (cukup untuk menangkap pola musiman tahunan), tapi kejadian yang jauh lebih lama meluruh signifikan. Rata-rata `w\_time` di seluruh data: 0,285 (usia rata-rata kejadian: 428 hari).

`event\_value = severity × w\_time` menjadi kontribusi tiap kejadian individual.

**c) Unit Analisis.** Kejadian diagregasi ke level **(sel grid × hari × jam)** — unit ini yang menjawab langsung definisi "risiko suatu lokasi pada waktu tertentu". `base\_value` = jumlah `event\_value` per unit, `crime\_count` = frekuensi kejadian, `arrest\_rate` = rata-rata status penangkapan. **Total 119.454 baris unit** dari 550.896 kejadian individual.

**d) Spatial Decay (Proximity).** `w\_dist = exp(-d²/2σ²)` dengan `σ (SIGMA\_METERS) = 1.500 m`, dihitung dari jarak geografis sesungguhnya (haversine, via `BallTree`) — bukan sekadar "grid tetangga 3×3". Setiap sel menyerap pengaruh sel-sel tetangganya dalam radius pencarian `3σ = 4.500 m`, berbobot jarak. **Rata-rata jumlah tetangga per sel: 40,4** (angka yang sudah divalidasi wajar setelah proses debugging bersama, dibandingkan dengan percobaan awal `SIGMA\_METERS=500` yang hanya menghasilkan \~8 tetangga, dan grid 3-desimal yang sempat menghasilkan ribuan tetangga tidak wajar).

**e) Normalisasi 0–100.** `risk\_raw` (hasil smoothing) di-transform dengan `log1p` sebelum di-min-max scale ke 0–100 — lebih tahan terhadap outlier dibanding min-max langsung, karena beberapa sel dengan nilai ekstrem tidak lagi menekan seluruh sel lain ke rentang sempit.

**Hasil akhir `risk\_score`:** mean 60,08, std 13,40, rentang 0–100 — distribusi cukup lebar (bukan menumpuk di satu titik), yang berarti target ini punya variansi yang cukup informatif untuk dipelajari model prediksi di CP2.

##### 2.6 Menyusun Dataset Akhir

Dataset final (`final`) berisi 119.454 baris x 12 kolom:

|Kolom|Keterangan|
|-|-|
|`cell\_id`, `lat\_r`, `lon\_r`|Identitas \& koordinat sel grid|
|`dow`, `hour`|Waktu mentah|
|`dow\_sin`, `dow\_cos`, `hour\_sin`, `hour\_cos`|Encoding siklikal waktu|
|`crime\_count`|Frekuensi kejadian di unit tsb|
|`arrest\_rate`|Proporsi kejadian yang berujung penangkapan|
|`risk\_score`|**Label target** (0–100)|

Disimpan sebagai `features\_labels.csv` sebagai input untuk tahap modeling (CP2).

#### 3\. Parameter Kunci \& Justifikasi

|Parameter|Nilai|Alasan|
|-|-|-|
|`N\_YEARS`|3|Menjaga relevansi data terkini \& notebook tetap ringan dijalankan ulang|
|`ROUND\_DECIMALS` (grid)|2 (\~1 km/sel)|Resolusi lebih halus (3 desimal) membuat kepadatan sel berlebihan relatif terhadap radius pencarian tetangga|
|`HALF\_LIFE\_DAYS`|180|Kejadian setahun lalu masih relevan \~25%, menyeimbangkan pola musiman vs kebaruan|
|`SIGMA\_METERS`|1.500|Menghasilkan rata-rata \~40 tetangga/sel — cukup untuk smoothing bermakna tanpa menyebar ke area tak relevan|
|Metode normalisasi|`log1p` + min-max|Tahan outlier, mempertahankan urutan magnitude, distribusi akhir tidak menumpuk di satu ujung|

#### 4\. Keterbatasan \& Rencana Lanjutan

* **Dataset proxy, bukan data riil Jabodetabek.** 
* **Performa `spatial\_smooth`:** implementasi saat ini melakukan pencarian posisi sel per baris (`cells.index\[...]`) di dalam fungsi yang dipanggil berulang lewat `.apply(axis=1)` — berjalan baik untuk 1.001 sel unik saat ini, tapi berpotensi melambat signifikan jika subset data/​jumlah sel diperbesar di iterasi berikutnya. Direkomendasikan untuk di-precompute (`cell\_id → posisi`) bila skala data bertambah.
* **Bagian EDA (pola waktu/lokasi, hotspot) tidak disertakan** dalam notebook CP1 ini secara eksplisit. Sesuai penugasan check point 1, kami lebih fokus pada pseudo labeling, feature engineering, dan untuk kasus ini, koordinat proxy untuk wilayah Jabodetabek.
* Justifikasi metode normalisasi \& temporal decay saat ini disampaikan secara naratif; menambahkan perbandingan eksplisit dengan alternatif (mis. percentile-rank, clipping, atau linear decay) dapat memperkuat argumen di laporan akhir.

---

## Checkpoint 2 Model Training and Baseline Comparison + REST API Serving
