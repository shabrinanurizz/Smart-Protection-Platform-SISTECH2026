"""
Unit test untuk Risk Score API.

Dipinduksi dengan Python unittest + FastAPI TestClient (httpx).
Untuk menjalankan:
    cd api_serving2
    python -m pytest tests/ -v
atau
    python -m unittest discover tests/ -v
"""

import os
import sys
import unittest

# Pastikan api_serving2/ ada di sys.path agar `import main` dan `from app.*` berhasil
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from main import app


class TestHealthCheck(unittest.TestCase):
    """Test endpoint health check."""

    def setUp(self):
        # Context manager diperlukan agar FastAPI lifespan (model load) berjalan
        self._cm = TestClient(app)
        self.client = self._cm.__enter__()

    def tearDown(self):
        self._cm.__exit__(None, None, None)

    def test_root(self):
        """GET / → 200 {status: 200, message: OK}"""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], 200)
        self.assertEqual(data["message"], "OK")

    def test_health(self):
        """GET /health → 200 {status: 200, message: OK}"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], 200)
        self.assertEqual(data["message"], "OK")


class TestRiskScore(unittest.TestCase):
    """Test endpoint GET /risk-score."""

    def setUp(self):
        self._cm = TestClient(app)
        self.client = self._cm.__enter__()

    def tearDown(self):
        self._cm.__exit__(None, None, None)

    def test_risk_score_valid(self):
        """Valid request → 200 dengan flat JSON response yang lengkap."""
        resp = self.client.get(
            "/risk-score?lat=-6.30&lon=106.80&datetime=2026-08-02T14:00:00"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("risk_score", data)
        self.assertIn("level", data)
        self.assertIn("model_version", data)
        self.assertIn("last_updated", data)
        # risk_score harus di rentang 0-100
        self.assertGreaterEqual(data["risk_score"], 0)
        self.assertLessEqual(data["risk_score"], 100)
        # level harus salah satu dari Low/Medium/High
        self.assertIn(data["level"], ["Low", "Medium", "High"])
        # model_version harus v1
        self.assertEqual(data["model_version"], "v1")

    def test_risk_score_out_of_bounds_lat(self):
        """Lat di luar bounding box → 400."""
        resp = self.client.get(
            "/risk-score?lat=-7.00&lon=106.80&datetime=2026-08-02T14:00:00"
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("detail", data)

    def test_risk_score_out_of_bounds_lon(self):
        """Lon di luar bounding box → 400."""
        resp = self.client.get(
            "/risk-score?lat=-6.30&lon=108.00&datetime=2026-08-02T14:00:00"
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("detail", data)

    def test_risk_score_invalid_datetime(self):
        """Datetime tidak valid → 400."""
        resp = self.client.get(
            "/risk-score?lat=-6.30&lon=106.80&datetime=not-a-date"
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("detail", data)

    def test_risk_score_missing_params(self):
        """Query param wajib hilang → 422."""
        resp = self.client.get("/risk-score?lat=-6.30&lon=106.80")
        self.assertEqual(resp.status_code, 422)

    def test_risk_score_boundary(self):
        """Koordinat di tepi bounding box → 200 (inclusive)."""
        resp = self.client.get(
            "/risk-score?lat=-6.55&lon=106.55&datetime=2026-08-02T00:00:00"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("risk_score", data)

    def test_risk_score_weekday_consistency(self):
        """Test bahwa dow encoding konsisten: Senin vs Minggu memberi perilaku berbeda."""
        resp_mon = self.client.get(
            "/risk-score?lat=-6.30&lon=106.80&datetime=2026-08-03T14:00:00"
        )
        resp_sun = self.client.get(
            "/risk-score?lat=-6.30&lon=106.80&datetime=2026-08-02T14:00:00"
        )
        self.assertEqual(resp_mon.status_code, 200)
        self.assertEqual(resp_sun.status_code, 200)
        # Skor seharusnya berbeda karena dow berbeda
        mon_score = resp_mon.json()["risk_score"]
        sun_score = resp_sun.json()["risk_score"]
        self.assertNotEqual(mon_score, sun_score,
                            "Risk score harus berbeda untuk dow yang berbeda")


class TestResponseSchema(unittest.TestCase):
    """Test bahwa response schema sesuai kontrak README."""

    def setUp(self):
        self._cm = TestClient(app)
        self.client = self._cm.__enter__()

    def tearDown(self):
        self._cm.__exit__(None, None, None)

    def test_response_no_envelope(self):
        """Response harus flat JSON (tidak ada envelope {status, message, data})."""
        resp = self.client.get(
            "/risk-score?lat=-6.30&lon=106.80&datetime=2026-08-02T14:00:00"
        )
        data = resp.json()
        # Pastikan tidak ada envelope
        self.assertNotIn("data", data)
        self.assertNotIn("status", data)
        self.assertNotIn("message", data)


if __name__ == "__main__":
    unittest.main()
