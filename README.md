# Smart Protection Platform — Crime Risk Prediction API

A FastAPI-based machine learning serving project built for SISTECH 2026.  
It serves a crime risk prediction model through a REST API and provides a Safe Commute feature for evaluating route risk based on location and time.

## Project Structure

```text
Smart-Protection-Platform-SISTECH2026/
├── apps/
│   ├── bootstrap/          # configuration and logger setup
│   ├── controllers/        # application business logic
│   ├── middleware/         # request tracing middleware
│   ├── routers/            # API endpoint routers
│   ├── schemas/            # Pydantic request/response schemas
│   └── services/           # model, routing, and commute services
├── data/
│   └── sample/              # sample API requests
├── model_registry/
│   └── v1/                  # versioned model metadata
├── notebooks/
│   ├── FeatureEngineering-PseudoLabeling.ipynb
│   └── Modelling-Train.ipynb
├── tests/
│   ├── test_api.py
│   └── test_endpoints_manual.py
├── main.py                  # FastAPI application entrypoint
├── config.yaml              # central application configuration
├── Dockerfile
├── requirements.txt
└── .gitignore
````

## Prerequisites

* Python 3.11+
* pip
* Git

## Getting Started

### 1. Create and activate a virtual environment

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Prepare the model

The API uses a versioned local model registry:

```text
model_registry/
└── v1/
    ├── model.pkl
    └── metadata.json
```

The model artifact is not included in the repository because of its large file size.

Make sure the model is available at:

```text
model_registry/v1/model.pkl
```

### 4. Run the API

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

## Configuration

Runtime settings are managed through `config.yaml`.

### Model

```yaml
model:
  version: "v1"
  registry_path: "model_registry/v1"
  model_file: "model.pkl"
  metadata_file: "metadata.json"
```

### Risk Thresholds

```yaml
risk_thresholds:
  low_max: 33.0
  medium_max: 66.0
  min_score: 0.0
  max_score: 100.0
```

Risk levels:

| Risk Score | Level  |
| ---------- | ------ |
| 0 – 33     | Low    |
| 33.1 – 66  | Medium |
| > 66       | High   |

### Routing

The Safe Commute feature currently uses OSRM as its routing provider.

```yaml
routing:
  provider: "osrm"
```

## Model Features

The model uses the following features:

```text
lat_r
lon_r
hour_sin
hour_cos
dow_sin
dow_cos
crime_count
cell_freq_enc
cell_target_enc
```

Temporal variables are represented using cyclical encoding for hour and day of week.

## API Overview

The API provides the following endpoint groups:

* **Health** — check API, model, and routing service status
* **Prediction** — predict crime risk for a location and time
* **Safe Commute** — calculate route and aggregate risk along the route
* **Registry** — inspect model registry information
* **Monitoring** — retrieve API/prediction metrics, drift monitoring history, and active model performance

### Health Check

```http
GET /health
```

### Risk Prediction

```http
POST /predict-risk/
```

Example request:

```json
{
  "lat": -6.2,
  "lon": 106.8,
  "hour": 22,
  "day": "Saturday"
}
```

Example response:

```json
{
  "risk_score": 62.58,
  "risk_level": "Medium"
}
```

### Safe Commute

```http
POST /safe-commute/
```

Example request:

```json
{
  "start": {
    "lat": -6.2,
    "lon": 106.8
  },
  "destination": {
    "lat": -6.21,
    "lon": 106.82
  },
  "hour": 22,
  "day": "Saturday"
}
```

The endpoint returns route information, distance, duration, route risk score, risk level, segment risks, and recommendation.

### Model Registry

```http
GET /registry/
```

### Monitoring

The Monitoring group provides observability into both the application and the model serving pipeline.

#### Application Metrics

```http
GET /metrics
```

Returns information such as:

* API uptime
* model version
* total requests
* total predictions
* application status

#### Drift Monitoring History

```http
GET /monitoring/drift
```

Reads the drift monitoring history from `model_registry/drift_log.json`. If the file does not exist yet, returns an empty list with an appropriate message. Each entry includes the before/after active versions, batch number, performance metrics, distribution drift results, and the promotion status.

Example response:

```json
{
  "data": [
    {
      "batch": 1,
      "active_version_before": "v2",
      "active_version_after": "v2",
      "performance": {
        "mae": 2.75776594541133,
        "performance_drift": false
      },
      "distribution": {
        "distribution_drift": false,
        "ks_results": null
      },
      "drift_detected": false,
      "candidate_version": null,
      "promoted": false
    }
  ],
  "message": "Berhasil memuat 4 entri monitoring drift."
}
```

#### Active Model Performance

```http
GET /monitoring/model-performance
```

Reads `model_registry/active_version.json` to resolve the active version, then reads **only** the `metadata.json` of that version (the model artifact `model.pkl` and `encoding_maps.pkl` are never loaded). Returns training metadata and metrics for the active model.

Example response:

```json
{
  "active_version": "v2",
  "trained_at": "2026-08-05T09:03:10.997007+00:00",
  "metrics": {
    "mae_test": 2.7169557958305735,
    "rmse_test": 3.7333234557464373,
    "n_test_rows": 23891
  },
  "n_train_rows": 95563,
  "trigger": "initial_training",
  "parent_version": null,
  "feature_cols": [
    "lat_r",
    "lon_r",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "crime_count",
    "cell_freq_enc",
    "cell_target_enc"
  ]
}
```

## Testing

### Automated API Tests

Run:

```bash
pytest tests/test_api.py -v
```

Current result:

```text
11 passed
```

### Manual HTTP Endpoint Tests

The project also includes direct HTTP testing using `requests`:

```bash
python tests/test_endpoints_manual.py
```

This tests the running API rather than FastAPI's `TestClient`.

Tested endpoints:

```text
GET  /health
POST /predict-risk/
POST /predict-risk/ (invalid input)
POST /safe-commute/
GET  /registry/
GET  /metrics
GET  /monitoring/drift
GET  /monitoring/model-performance
```

## Docker

Build the image:

```bash
docker build -t smart-protection-platform .
```

Run the API:

```bash
docker run -p 8000:8000 smart-protection-platform
```

The API will then be available at:

```text
http://localhost:8000
```

## Model Registry

Models are versioned using a local model registry:

```text
model_registry/
└── v1/
    ├── model.pkl
    └── metadata.json
```

To change the served model version, update the model configuration in `config.yaml` and provide the corresponding model artifact.

## Logging

Runtime logs are generated by the application and are not committed to the repository.

The application maintains logs for:

* HTTP requests
* predictions
* errors

Log files are excluded through `.gitignore`.

## Project Status

* FastAPI serving: Ready
* Model registry: v1
* Risk prediction: Ready
* Safe Commute: Ready
* Automated API tests: 11/11 passed
* Manual HTTP endpoint testing: Implemented
* Docker configuration: Included