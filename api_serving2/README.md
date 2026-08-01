# Risk Score API — api_serving2 (CP2: Model Training & REST API Serving)

SISTECH 2026 MLOps Final Project — Group 6.

> `api_serving2` adalah versi perbaikan dari `api_serving`. Perbaikan utama:
> - `model.pkl` disediakan (hasil training ulang dengan script `train.py`)
> - Path registry berbasis `Path(__file__)` — tidak bergantung pada CWD
> - Dukungan `.env` via `python-dotenv` (opsional)
> - `Dockerfile` tersedia untuk deployment
> - Unit test tersedia di `tests/`
> - `train.py` untuk mereproduksi model secara reproducible

## 1. Cara menjalankan

### Prasyarat
- Python ≥ 3.10
- Dataset `features_labels.csv` tersedia di `../data/dataset/` (proyek root)

### Instalasi

```bash
cd api_serving2
pip install -r requirements.txt
```

### Opsi A: Langsung jalankan API (model.pkl sudah ada)

```bash
cd api_serving2
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Opsi B: Training ulang model dari awal

```bash
cd api_serving2
# Default data path: ../data/dataset/features_labels.csv
python train.py

# Atau gunakan path kustom:
python train.py --data-path /path/ke/features_labels.csv
```

Output training:
- `model_registry/v1/model.pkl` — model RandomForestRegressor terlatih
- `model_registry/v1/metadata.json` — metadata terupdate (metrics, thresholds, params)

### Opsi C: Jalankan dengan Docker

```bash
cd api_serving2
docker build -t risk-score-api .
docker run -p 8000:8000 risk-score-api
```

### Opsi D: Jalankan unit test

```bash
cd api_serving2
python -m pytest tests/ -v
# atau
python -m unittest discover tests/ -v
```

Buka `http://localhost:8000/docs` untuk Swagger UI (try it out langsung dari browser).

## 2. Struktur folder

```
api_serving2/
├── main.py                    # entrypoint FastAPI, load registry saat startup
├── train.py                   # [BARU] script training ke model.pkl (reproducible)
├── requirements.txt           # dependencies
├── Dockerfile                 # [BARU] container build
├── .env.example               # [BARU] template env vars (MODEL_VERSION)
├── .gitignore                 # [BARU] ignore .env, __pycache__, dll
├── README.md                  # ini file
├── app/
│   ├── __init__.py
│   ├── schemas.py              # Pydantic response schema
│   ├── controller.py           # feature engineering + prediksi + registry loader
│   └── router.py               # endpoint GET /risk-score
├── model_registry/
│   └── v1/
│       ├── model.pkl           # hasil training RandomForestRegressor
│       └── metadata.json       # metadata model (params, metrics, thresholds)
└── tests/
    ├── __init__.py
    └── test_app.py             # [BARU] unit test (health, risk-score, errors)
```

## 3. API Contract

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
  "level": "Medium",
  "model_version": "v1",
  "last_updated": "2026-08-01T14:12:26"
}
```

**Level thresholds** (dari `metadata.json`, dihitung dari kuantil 33%/67% risk_score training set):
- `Low` jika `risk_score < 55.8`
- `Medium` jika `55.8 ≤ risk_score ≤ 67.2`
- `High` jika `risk_score > 67.2`

> Angka ini dihitung otomatis oleh `train.py` dan disimpan di `metadata.json`. API selalu membaca dari sana, tidak hardcode.

**Errors:**

| Status | Kapan terjadi |
|---|---|
| 400 | `lat`/`lon` di luar bounding box Jabodetabek, atau `datetime` bukan ISO 8601 valid |
| 422 | Parameter wajib hilang atau tipe salah (ditangani otomatis oleh FastAPI/Pydantic) |

### GET /health, GET /

Health check sederhana: `{"status": 200, "message": "OK"}`.

## 4. Feature Engineering

Model menerima **6 fitur** yang selalu tersedia saat serving time:

| Feature | Deskripsi |
|---|---|
| `lat_r` | Latitude dibulatkan ke 2 desimal |
| `lon_r` | Longitude dibulatkan ke 2 desimal |
| `dow_sin`, `dow_cos` | Day-of-week cyclical encoding (period=7, Monday=0..Sunday=6) |
| `hour_sin`, `hour_cos` | Hour cyclical encoding (period=24) |

**Fitur yang dikecualikan dari serving:**
- `crime_count` — hanya tersedia setelah kejadian terjadi, tidak untuk prediksi masa depan
- `arrest_rate` — sama, post-hoc

## 5. Environment Configuration

File `.env.example` berisi:
```
MODEL_VERSION=v1
```

Copy ke `.env` dan sesuaikan jika perlu deploy versi berbeda.

## 6. Catatan implementasi & perbaikan dari api_serving

- **Path resilience**: `REGISTRY_DIR` dihitung dari `Path(__file__).resolve().parent`, sehingga tidak bergantung pada current working directory.
- **Model artifact**: `model.pkl` disediakan hasil training ulang via `train.py` (original api_serving tidak memiliki file ini karena notebook CP2 tidak pernah ekspor model).
- **Reproducibility**: `train.py` menggunakan `random_state=42` dan hyperparameter yang sama dengan `metadata.json`.
- **Containerisasi**: `Dockerfile` tersedia untuk deployment Docker.
- **Testing**: Unit test di `tests/` mencakup health check, risk-score endpoint, error handling (400/422), boundary conditions, dan schema validation.
