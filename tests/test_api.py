"""
Test suite untuk Smart Protection Platform API.

Tests:
  1. GET  /health        — health check
  2. POST /predict-risk  — risk prediction
  3. POST /safe-commute  — safe commute planning

Cara jalankan:
  python -m pytest tests/test_api.py -v
  # atau
  python tests/test_api.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Pastikan project root ada di sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# =====================================================================
# Helper
# =====================================================================
def print_separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# =====================================================================
# TEST 1: GET /health
# =====================================================================
def test_health_check() -> None:
    """GET /health — memastikan semua komponen (model, routing) siap."""
    print_separator("TEST: GET /health")

    response = client.get("/health")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"  Status: {data['status']}")
    print(f"  Model:  {data['components']['model']['status']}")
    print(f"  Routing: {data['components']['routing']['status']}")

    assert data["status"] == "healthy", f"Expected 'healthy', got '{data['status']}'"
    assert data["components"]["model"]["status"] == "ok"
    assert data["components"]["routing"]["status"] == "ok"

    print("  ✅ PASS: /health mengembalikan status 'healthy'")
    return data


# =====================================================================
# TEST 2: POST /predict-risk
# =====================================================================
def test_predict_risk_valid() -> None:
    """POST /predict-risk — request valid."""
    print_separator("TEST: POST /predict-risk (valid)")

    payload = {
        "lat": -6.2,
        "lon": 106.8,
        "hour": 22,
        "day": "Saturday",
    }
    print(f"  Request: {payload}")

    response = client.post("/predict-risk/", json=payload)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. "
        f"Response: {response.text}"
    )

    data = response.json()
    print(f"  Response: {data}")

    assert "risk_score" in data, "Response harus mengandung 'risk_score'"
    assert "risk_level" in data, "Response harus mengandung 'risk_level'"
    assert 0.0 <= data["risk_score"] <= 100.0, f"risk_score harus 0-100, got {data['risk_score']}"
    assert data["risk_level"] in ("Low", "Medium", "High"), (
        f"risk_level harus Low/Medium/High, got '{data['risk_level']}'"
    )

    print(f"  ✅ PASS: risk_score={data['risk_score']}, risk_level={data['risk_level']}")
    return data


def test_predict_risk_invalid_lat() -> None:
    """POST /predict-risk — latitude di luar range."""
    print_separator("TEST: POST /predict-risk (invalid lat)")

    payload = {"lat": 999, "lon": 106.8, "hour": 22, "day": "Saturday"}
    response = client.post("/predict-risk/", json=payload)

    assert response.status_code in (400, 422), (
        f"Expected 400/422, got {response.status_code}"
    )
    print(f"  ✅ PASS: Dikembalikan status {response.status_code} untuk lat tidak valid")


def test_predict_risk_invalid_hour() -> None:
    """POST /predict-risk — hour di luar range 0-23."""
    print_separator("TEST: POST /predict-risk (invalid hour)")

    payload = {"lat": -6.2, "lon": 106.8, "hour": 25, "day": "Saturday"}
    response = client.post("/predict-risk/", json=payload)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    print(f"  ✅ PASS: Dikembalikan status 422 untuk hour=25")


def test_predict_risk_invalid_day() -> None:
    """POST /predict-risk — day tidak valid."""
    print_separator("TEST: POST /predict-risk (invalid day)")

    payload = {"lat": -6.2, "lon": 106.8, "hour": 22, "day": "Minggu"}  # bukan English
    response = client.post("/predict-risk/", json=payload)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    print(f"  ✅ PASS: Dikembalikan status 422 untuk day='Minggu'")


def test_predict_risk_missing_field() -> None:
    """POST /predict-risk — field yang missing."""
    print_separator("TEST: POST /predict-risk (missing field)")

    payload = {"lat": -6.2, "hour": 22, "day": "Saturday"}  # lon missing
    response = client.post("/predict-risk/", json=payload)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    print(f"  ✅ PASS: Dikembalikan status 422 untuk field yang missing")


# =====================================================================
# TEST 3: POST /safe-commute
# =====================================================================
def test_safe_commute_valid() -> None:
    """POST /safe-commute — request valid."""
    print_separator("TEST: POST /safe-commute (valid)")

    payload = {
        "start": {"lat": -6.2, "lon": 106.8},
        "destination": {"lat": -6.21, "lon": 106.82},
        "hour": 22,
        "day": "Saturday",
    }
    print(f"  Request: {payload}")

    response = client.post("/safe-commute/", json=payload)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. "
        f"Response: {response.text}"
    )

    data = response.json()
    print(f"  Response keys: {list(data.keys())}")
    print(f"  route_risk_score: {data['route_risk_score']}")
    print(f"  risk_level: {data['risk_level']}")
    print(f"  distance_meters: {data['distance_meters']}")
    print(f"  duration_seconds: {data['duration_seconds']}")
    print(f"  routing_provider: {data['routing_provider']}")
    print(f"  segment_risks count: {len(data.get('segment_risks', []))}")

    assert "route" in data, "Response harus mengandung 'route'"
    assert "distance_meters" in data
    assert "duration_seconds" in data
    assert "route_risk_score" in data
    assert "risk_level" in data
    assert 0.0 <= data["route_risk_score"] <= 100.0
    assert data["risk_level"] in ("Low", "Medium", "High")
    assert data["distance_meters"] > 0

    print(f"  ✅ PASS: Safe commute berhasil direncanakan")
    return data


def test_safe_commute_close_points() -> None:
    """POST /safe-commute — titik awal dan tujuan sangat dekat."""
    print_separator("TEST: POST /safe-commute (close points)")

    payload = {
        "start": {"lat": -6.2, "lon": 106.8},
        "destination": {"lat": -6.2001, "lon": 106.8001},
        "hour": 14,
        "day": "Monday",
    }

    response = client.post("/safe-commute/", json=payload)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert "route" in data
    assert data["distance_meters"] > 0 or data["distance_meters"] == 0  # bisa 0 untuk titik dekat
    print(f"  ✅ PASS: Close points - risk_level={data['risk_level']}")
    return data


def test_safe_commute_invalid() -> None:
    """POST /safe-commute — request dengan lat/lon tidak valid."""
    print_separator("TEST: POST /safe-commute (invalid)")

    payload = {
        "start": {"lat": -6.2, "lon": 106.8},
        "destination": {"lat": 999, "lon": 106.82},  # invalid lat
        "hour": 22,
        "day": "Saturday",
    }
    response = client.post("/safe-commute/", json=payload)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    print(f"  ✅ PASS: Dikembalikan 422 untuk lat tidak valid")


# =====================================================================
# TEST 4: GET /registry
# =====================================================================
def test_registry() -> None:
    """GET /registry — list registered models."""
    print_separator("TEST: GET /registry")

    response = client.get("/registry/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"  Registered models: {len(data)}")
    for model in data:
        print(f"    - version: {model['version']}")
    print("  ✅ PASS: /registry berhasil")
    return data


# =====================================================================
# TEST 5: GET /metrics
# =====================================================================
def test_metrics() -> None:
    """GET /metrics — application metrics."""
    print_separator("TEST: GET /metrics")

    response = client.get("/metrics")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"  Status: {data.get('status')}")
    print(f"  Model version: {data.get('model_version')}")
    print(f"  Uptime: {data.get('uptime_seconds')}s")
    print("  ✅ PASS: /metrics berhasil")
    return data


# =====================================================================
# Main runner
# =====================================================================
if __name__ == "__main__":
    tests = [
        ("GET /health", test_health_check),
        ("POST /predict-risk (valid)", test_predict_risk_valid),
        ("POST /predict-risk (invalid lat)", test_predict_risk_invalid_lat),
        ("POST /predict-risk (invalid hour)", test_predict_risk_invalid_hour),
        ("POST /predict-risk (invalid day)", test_predict_risk_invalid_day),
        ("POST /predict-risk (missing field)", test_predict_risk_missing_field),
        ("POST /safe-commute (valid)", test_safe_commute_valid),
        ("POST /safe-commute (close points)", test_safe_commute_close_points),
        ("POST /safe-commute (invalid)", test_safe_commute_invalid),
        ("GET /registry", test_registry),
        ("GET /metrics", test_metrics),
    ]

    passed = 0
    failed = 0

    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)
