"""Quick validation: imports + model load + prediction (non-pytest)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.controller import (
    RiskModelRegistry, OutOfBoundsError, InvalidDatetimeError,
    build_feature_vector, validate_bounds, parse_datetime,
)
print("OK: app.controller imports")

from app.schemas import RiskScoreResponse, ErrorResponse
print("OK: app.schemas imports")

from app.router import router
print("OK: app.router imports")

from main import app
print("OK: main.app imports")

# RiskModelRegistry
BASE = Path(__file__).resolve().parent.parent
registry = RiskModelRegistry(BASE / "model_registry", version="v1")
print("OK: RiskModelRegistry loaded")
print(f"  feature_cols : {registry.feature_cols}")
print(f"  low_max      : {registry.low_max}")
print(f"  high_min     : {registry.high_min}")
print(f"  mae_test     : {registry.metadata['metrics']['mae_test']}")
print(f"  rmse_test    : {registry.metadata['metrics']['rmse_test']}")
print(f"  version      : {registry.metadata['version']}")

# Prediction — valid
result = registry.predict(lat=-6.30, lon=106.80, dt_str="2026-08-02T14:00:00")
print(f"OK: Predict (valid): {result}")

# Prediction — weekday consistency (Senin vs Minggu, jam sama)
mon = registry.predict(lat=-6.30, lon=106.80, dt_str="2026-08-03T14:00:00")
sun = registry.predict(lat=-6.30, lon=106.80, dt_str="2026-08-02T14:00:00")
print(f"OK: Senin score  : {mon['risk_score']} ({mon['level']})")
print(f"OK: Minggu score : {sun['risk_score']} ({sun['level']})")
assert mon["risk_score"] != sun["risk_score"], "dow encoding should differ"

# Boundary
b = registry.predict(lat=-6.55, lon=106.55, dt_str="2026-08-02T00:00:00")
print(f"OK: Boundary (lat=-6.55, lon=106.55): {b['risk_score']}")

# Error handling
try:
    registry.predict(lat=-7.00, lon=106.80, dt_str="2026-08-02T14:00:00")
    print("FAIL: out-of-bounds should have raised")
except OutOfBoundsError as e:
    print(f"OK: OutOfBoundsError raised: {e}")

try:
    registry.predict(lat=-6.30, lon=106.80, dt_str="not-a-date")
    print("FAIL: invalid datetime should have raised")
except InvalidDatetimeError as e:
    print(f"OK: InvalidDatetimeError raised: {e}")

print("\n=== ALL IMPORT + PREDICTION CHECKS PASSED ===")
