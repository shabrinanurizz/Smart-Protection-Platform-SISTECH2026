# Risk Score API -- CP2 (Model Training & Baseline Comparison + REST API Serving)

SISTECH 2026 MLOps Final Project -- Group 6.

## 1. Cara menjalankan

```bash
pip install -r requirements.txt

# 1) Copy hasil export dari Bab 8 notebook CP2 ke sini:
#    model_registry/v1/model.pkl
#    model_registry/v1/metadata.json   (sudah ada contohnya)

# 2) Jalankan
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Buka `http://localhost:8000/docs` untuk Swagger UI (try it out langsung dari browser).

## 2. Struktur folder

```
api/
├── main.py                    # entrypoint FastAPI, load registry saat startup
├── app/
│   ├── schemas.py              # Pydantic response schema
│   ├── controller.py           # feature engineering + prediksi + registry loader
│   └── router.py                # endpoint GET /risk-score
├── model_registry/
│   └── v1/
│       ├── model.pkl            # <- taruh hasil joblib.dump dari notebook Bab 8 di sini
│       └── metadata.json        # sudah terisi dari hasil kamu
├── requirements.txt
└── README.md
```

## 3. API Contract (ringkas -- lengkapi ke tim FE)

**Base URL:** `http://localhost:8000`
**Interactive docs:** `http://localhost:8000/docs`

### GET /risk-score

| Query Param | Type | Required | Description |
|---|---|---|---|
| `lat` | float | Yes | Latitude, dalam bounding box Jabodetabek proxy (-6.55 s.d. -6.10) |
| `lon` | float | Yes | Longitude, dalam bounding box Jabodetabek proxy (106.55 s.d. 107.05) |
| `datetime` | string | Yes | ISO 8601, contoh: `2026-08-02T14:00:00` |

**Contoh request:**
```
GET /risk-score?lat=-6.30&lon=106.80&datetime=2026-08-02T22:00:00
```

**Contoh response (200):**
```json
{
  "risk_score": 47.58,
  "level": "Low",
  "model_version": "v1",
  "last_updated": "2026-08-01T04:33:56"
}
```

**Level thresholds** (dari `metadata.json`, dihitung dari kuantil 33%/67% risk_score
training set -- lihat Bab 7 notebook CP2): `Low` jika risk_score < 55.8, `Medium`
55.8-67.2, `High` jika > 67.2. *Angka ini akan berubah kalau model di-retrain --
selalu baca dari `metadata.json`, jangan hardcode di FE.*

**Errors:**
| Status | Kapan terjadi |
|---|---|
| 400 | `lat`/`lon` di luar bounding box Jabodetabek, atau `datetime` bukan ISO 8601 valid |
| 422 | Parameter wajib hilang atau tipe salah (ditangani otomatis oleh FastAPI/Pydantic) |

### GET /health, GET /

Health check sederhana, `{"status": 200, "message": "OK"}`.

## 4. Yang PERLU didiskusikan dengan tim FE (belum final, sengaja belum diputuskan sepihak)

1. **Perilaku out-of-bounds** -- saat ini API menolak (400) request di luar bounding
   box Jabodetabek. Apakah FE mengharapkan perilaku lain (misal fallback ke skor 0)?
2. **Format `last_updated`** -- saat ini dikirim penuh dengan jam (`2026-08-01T04:33:56`),
   bukan cuma tanggal (`2024-11-18`) seperti contoh ilustratif di dokumen tugas.
   Konfirmasi ke FE apakah format ini oke atau perlu disederhanakan.
3. **Endpoint batch untuk heatmap** -- endpoint ini cuma menjawab satu titik per
   request. Kalau FE butuh heatmap seluruh Jabodetabek per perubahan filter jam/hari,
   perlu didiskusikan apakah perlu endpoint batch tambahan (belum dibangun di CP2 ini).

## 5. Catatan implementasi

- `dow` (hari dalam seminggu) memakai konvensi Python `datetime.weekday()`:
  Senin=0 ... Minggu=6. **Wajib dicek konsisten** dengan konvensi `dow` yang dipakai
  saat membangun `features_labels.csv` di notebook CP1 -- kalau beda konvensi, model
  akan menerima sinyal hari yang salah walau secara numerik tetap "valid".
- `ROUND_DECIMALS = 2` di `app/controller.py` harus selalu sama dengan resolusi grid
  yang dipakai di notebook CP1. Kalau CP1/CP3 mengubah resolusi grid, ubah juga
  konstanta ini.
- Registry dan model di-load **sekali saat startup** (bukan tiap request) lewat
  FastAPI `lifespan`, supaya latency rendah dan tidak ada race condition baca file.
