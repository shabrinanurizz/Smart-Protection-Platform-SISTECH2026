"""
Manual endpoint test script — untuk menguji /predict-risk dan /safe-commute
secara langsung via HTTP (bukan TestClient).
"""

import json
import requests

BASE = "http://localhost:8000"


def test_health():
    print("=" * 60)
    print("TEST 1: GET /health")
    print("=" * 60)
    resp = requests.get(f"{BASE}/health", timeout=15)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2))
    assert resp.status_code == 200
    assert data["status"] == "healthy"
    print("PASS: /health\n")


def test_predict_risk():
    print("=" * 60)
    print("TEST 2: POST /predict-risk (valid)")
    print("=" * 60)
    payload = {"lat": -6.2, "lon": 106.8, "hour": 22, "day": "Saturday"}
    print(f"Request: {json.dumps(payload)}")
    resp = requests.post(f"{BASE}/predict-risk/", json=payload, timeout=30)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert resp.status_code == 200
    assert "risk_score" in data
    assert "risk_level" in data
    assert 0.0 <= data["risk_score"] <= 100.0
    assert data["risk_level"] in ("Low", "Medium", "High")
    print(f"PASS: risk_score={data['risk_score']}, risk_level={data['risk_level']}\n")


def test_predict_risk_invalid():
    print("=" * 60)
    print("TEST 3: POST /predict-risk (invalid hour=25)")
    print("=" * 60)
    payload = {"lat": -6.2, "lon": 106.8, "hour": 25, "day": "Saturday"}
    resp = requests.post(f"{BASE}/predict-risk/", json=payload, timeout=30)
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 422
    print("PASS: Dikembalikan 422 untuk hour=25\n")


def test_safe_commute():
    print("=" * 60)
    print("TEST 4: POST /safe-commute (valid)")
    print("=" * 60)
    payload = {
        "start": {"lat": -6.2, "lon": 106.8},
        "destination": {"lat": -6.21, "lon": 106.82},
        "hour": 22,
        "day": "Saturday",
    }
    print(f"Request: {json.dumps(payload, indent=2)}")
    resp = requests.post(f"{BASE}/safe-commute/", json=payload, timeout=60)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error response: {resp.text}")
        raise AssertionError(
            f"/safe-commute/ expected 200, got {resp.status_code}"
        )
    data = resp.json()
    print(f"\nResponse:")
    print(json.dumps(data, indent=2))
    assert resp.status_code == 200
    assert "route" in data
    assert "distance_meters" in data
    assert "duration_seconds" in data
    assert "route_risk_score" in data
    assert "risk_level" in data
    assert 0.0 <= data["route_risk_score"] <= 100.0
    assert data["risk_level"] in ("Low", "Medium", "High")
    print(f"\nPASS: route_risk_score={data['route_risk_score']}, "
          f"risk_level={data['risk_level']}, "
          f"provider={data['routing_provider']}")
    print(f"  distance: {data['distance_meters']}m, duration: {data['duration_seconds']}s")
    print(f"  segment_risks: {len(data.get('segment_risks', []))} points")
    print(f"  recommendation: {data['recommendation']}\n")


def test_registry():
    print("=" * 60)
    print("TEST 5: GET /registry")
    print("=" * 60)
    resp = requests.get(f"{BASE}/registry/", timeout=15)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2))
    assert resp.status_code == 200
    print("PASS: /registry\n")


def test_metrics():
    print("=" * 60)
    print("TEST 6: GET /metrics")
    print("=" * 60)
    resp = requests.get(f"{BASE}/metrics", timeout=15)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2))
    assert resp.status_code == 200
    print("PASS: /metrics\n")


if __name__ == "__main__":
    tests = [
        ("GET /health", test_health),
        ("POST /predict-risk (valid)", test_predict_risk),
        ("POST /predict-risk (invalid)", test_predict_risk_invalid),
        ("POST /safe-commute (valid)", test_safe_commute),
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
            print(f"FAIL: {name} — {e}\n")
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)
