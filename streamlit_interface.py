"""
Smart Protection Platform — Streamlit Interface.

Struktur, alur, dan gaya penulisan diadopsi dari `interface.py` (referensi),
tetapi dihubungkan ke endpoint sesungguhnya yang tersedia di proyek ini:

    GET  /health              → status API, komponen model & routing
    POST /predict-risk/       → risk score (0-100) + risk level untuk 1 titik
    POST /safe-commute/       → rencana rute aman + risk per segmen
    GET  /registry/           → daftar model terdaftar
    GET  /registry/{version}  → detail metadata satu versi
    GET  /metrics             → metrik runtime (uptime, request/prediction counts)

Catatan penting
---------------
Bedanya dengan interface.py referensi:
  * interface.py referensi memakai domain "Taxi Trip Pricing" dan endpoint
    `/predict_live`, `/predict_batch`, `/get_available_versions`,
    `/get_model_info`, `/generate_full_report`, `/check_freshness` yang
    **tidak ada** pada proyek ini.
  * interface.py memakai `CONFIG.get_str("api.host")` — pada proyek ini
    `CONFIG` adalah sebuah `dict` biasa (bukan objek dengan method
    `get_str`), dan `config.yaml` tidak memiliki section `api`.

Oleh karena itu pemetaan berikut ini disesuaikan ke kontrak riil proyek:

  | Tab interface.py | Endpoint referensi       | Endpoint proyek ini      |
  |------------------|--------------------------|--------------------------|
  | Live Prediction  | POST /predict_live       | POST /predict-risk/      |
  | Batch Prediction | POST /predict_batch      | POST /safe-commute/ (*)  |
  | Model Registry   | GET /get_available_... + | GET /registry/ +        |
  |                  |   /get_model_info        |   /registry/{version}    |
  | Monitoring       | GET /generate_full_report| GET /metrics + GET /health|
  |                  | + GET /check_freshness   |                          |

  (*) `/predict_batch` tidak ada di proyek ini, sehingga tab "Batch
  Prediction" diganti menjadi "Safe Commute" — endpoint multi-titik
  sebenarnya yang tersedia.

Kontrak respons proyek ini **tidak** memakai envelope `{status, data}`;
respons dikembalikan langsung (Pydantic model / dict) dengan kode HTTP
standar. Maka pola penanganan diadaptasi: pakai `resp.raise_for_status()`
lalu `resp.json()` langsung, sambil tetap mempertahankan try/except
`ConnectionError` + `HTTPError` seperti di interface.py.

Cara jalankan:
  1. Pastikan API sudah berjalan:  uvicorn main:app --reload --port 8000
  2. streamlit run streamlit_interface.py
     (butuh: pip install streamlit plotly  — pandas & requests sudah ada)
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from apps.bootstrap.config import CONFIG

# ---------------------------------------------------------------------------
# Konfigurasi API base URL
# ---------------------------------------------------------------------------
# config.yaml proyek ini tidak memiliki section `api` (beda dengan interface.py
# referensi yang memakai CONFIG.get_str("api.host")). Pakai environment
# variable dengan default yang konsisten dengan main.py / Dockerfile / .env.
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

# Hari yang diterima domain model (validator normalisasi ke lowercase).
DAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


# ---------------------------------------------------------------------------
# Halaman
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Smart Protection Platform", layout="wide")
st.title("🛡️ Smart Protection Platform — Risk Prediction & Safe Commute")

# Konfigurasi yang tersedia di config.yaml (dipakai untuk referensi / fallback
# versi aktif pada tab Model Registry).
_CONFIGURED_VERSION = CONFIG.get("model", {}).get("version", "unknown")
_RISK_THRESHOLDS = CONFIG.get("risk_thresholds", {})


tab_live, tab_commute, tab_registry, tab_monitor = st.tabs(
    [
        "Live Prediction",
        "Safe Commute",
        "Model Registry",
        "Monitoring Dashboard",
    ]
)


# ---------------------------------------------------------------------------
# Tab 1: Live Prediction — calls POST /predict-risk/
# ---------------------------------------------------------------------------
with tab_live:
    st.subheader("Real-time risk prediction")
    st.caption(
        "Calls POST /predict-risk/ — the model predicts a crime/safety risk "
        "score (0-100) and level (Low/Medium/High) for the exact location and "
        "time given. Every field here maps 1:1 to the API contract."
    )
    if _RISK_THRESHOLDS:
        st.caption(
            f"Thresholds (config.yaml): Low <= "
            f"{_RISK_THRESHOLDS.get('low_max', 33)}, Medium <= "
            f"{_RISK_THRESHOLDS.get('medium_max', 66)}, else High."
        )

    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input(
            "Latitude", min_value=-90.0, max_value=90.0, value=-6.2, key="live_lat"
        )
        lon = st.number_input(
            "Longitude", min_value=-180.0, max_value=180.0, value=106.8, key="live_lon"
        )
        hour = st.number_input(
            "Hour of day (0-23)", min_value=0, max_value=23, value=22, key="live_hour"
        )
    with col2:
        day = st.selectbox("Day of week", DAYS, index=5, key="live_day")
        # Isi kolom kanan agar seimbang dengan kolom kiri.
        st.empty()

    if st.button("Predict risk", type="primary"):
        payload = {"lat": lat, "lon": lon, "hour": hour, "day": day}
        try:
            resp = requests.post(
                f"{API_BASE}/predict-risk/", json=payload, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()  # {risk_score, risk_level} — no envelope
            risk_score = data["risk_score"]
            risk_level = data["risk_level"]
            st.success(f"Risk score: **{risk_score}**")
            color = {"Low": "green", "Medium": "orange", "High": "red"}.get(risk_level)
            st.markdown(
                f"<span style='color:{color};font-weight:bold'>risk level: "
                f"{risk_level}</span>",
                unsafe_allow_html=True,
            )
            st.caption("Score range 0.0 - 100.0, level from config thresholds.")
        except requests.exceptions.ConnectionError:
            st.error("Can't reach the API. Is `uvicorn main:app --reload` running on port 8000?")
        except requests.exceptions.HTTPError as e:
            st.error(f"API error: {e.response.text}")


# ---------------------------------------------------------------------------
# Tab 2: Safe Commute — calls POST /safe-commute/
# ---------------------------------------------------------------------------
with tab_commute:
    st.subheader("Safe commute — route risk planning")
    st.caption(
        "Calls POST /safe-commute/ — given start, destination, time and day, "
        "returns a route, its aggregated risk score, per-point segment risks, "
        "and a human-readable recommendation. This is the project's real "
        "multi-point endpoint (the reference's /predict_batch does not exist here)."
    )
    st.info(
        "Required fields: start{lat,lon}, destination{lat,lon}, "
        "hour(0-23), day(Monday..Sunday)."
    )

    col1, col2 = st.columns(2)
    with col1:
        start_lat = st.number_input(
            "Start latitude", -90.0, 90.0, -6.2, key="comm_start_lat"
        )
        start_lon = st.number_input(
            "Start longitude", -180.0, 180.0, 106.8, key="comm_start_lon"
        )
        dep_hour = st.number_input(
            "Departure hour (0-23)", 0, 23, 22, key="comm_hour"
        )
        dep_day = st.selectbox("Day of week", DAYS, 5, key="comm_day")
    with col2:
        end_lat = st.number_input(
            "Destination latitude", -90.0, 90.0, -6.21, key="comm_end_lat"
        )
        end_lon = st.number_input(
            "Destination longitude", -180.0, 180.0, 106.82, key="comm_end_lon"
        )
        st.empty()

    if st.button("Plan safe commute", type="primary"):
        payload = {
            "start": {"lat": start_lat, "lon": start_lon},
            "destination": {"lat": end_lat, "lon": end_lon},
            "hour": dep_hour,
            "day": dep_day,
        }
        try:
            resp = requests.post(
                f"{API_BASE}/safe-commute/", json=payload, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()  # SafeCommuteResponse — no envelope
        except requests.exceptions.ConnectionError:
            st.error("Can't reach the API. Is `uvicorn main:app --reload` running on port 8000?")
            st.stop()
        except requests.exceptions.HTTPError as e:
            st.error(f"API error: {e.response.text}")
            st.stop()

        # --------------------------------------------------------
        # KPI Cards
        # --------------------------------------------------------
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Distance", f"{data.get('distance_meters', 0) / 1000:.2f} km")
        m2.metric("Duration", f"{data.get('duration_seconds', 0) / 60:.1f} min")
        m3.metric("Route risk score", f"{data.get('route_risk_score', '?')}")
        m4.metric("Risk level", data.get("risk_level", "—"))
        st.caption(
            f"routing provider: `{data.get('routing_provider', '?')}`"
        )
        st.divider()

        # --------------------------------------------------------
        # Route map (plotly) — uses real `route` + `segment_risks`
        # --------------------------------------------------------
        route = data.get("route", [])
        seg = data.get("segment_risks", [])
        if route:
            st.markdown("### Route & segment risk")
            fig = go.Figure()

            # Route geometry: list of [lon, lat] (GeoJSON LineString)
            lons = [pt[0] for pt in route]
            lats = [pt[1] for pt in route]
            fig.add_trace(
                go.Scattergeo(
                    lat=lats,
                    lon=lons,
                    mode="lines",
                    line=dict(width=4, color="#1f77b4"),
                    name="Route",
                )
            )

            # Segment risk points
            if seg:
                s_lats = [p.get("lat") for p in seg]
                s_lons = [p.get("lon") for p in seg]
                s_scores = [p.get("risk_score", 0) for p in seg]
                fig.add_trace(
                    go.Scattergeo(
                        lat=s_lats,
                        lon=s_lons,
                        mode="markers",
                        marker=dict(
                            size=8,
                            color=s_scores,
                            colorscale="RdYlGn_r",
                            cmin=0,
                            cmax=100,
                            showscale=True,
                            colorbar=dict(title="Risk"),
                        ),
                        name="Segment risk",
                        text=[f"{s:.1f}" for s in s_scores],
                        hoverinfo="text",
                    )
                )

            fig.update_geos(fitbounds=True, visible=False)
            fig.update_layout(height=420, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No route geometry returned.")

        # --------------------------------------------------------
        # Segment risk table
        # --------------------------------------------------------
        if seg:
            st.markdown("### Segment risk details")
            seg_df = pd.DataFrame(seg)
            st.dataframe(seg_df, hide_index=True, use_container_width=True)

        # --------------------------------------------------------
        # Recommendation
        # --------------------------------------------------------
        st.markdown("### Recommendation")
        st.info(data.get("recommendation", "—"))


# ---------------------------------------------------------------------------
# Tab 3: Model Registry — GET /registry/ + GET /registry/{version}
# ---------------------------------------------------------------------------
with tab_registry:
    st.subheader("Model registry")
    st.caption(
        "Calls GET /registry/ and GET /registry/{version} — the same registry "
        "your controllers read from on every prediction."
    )

    try:
        versions_resp = requests.get(f"{API_BASE}/registry/", timeout=5)
        versions_resp.raise_for_status()
        models = versions_resp.json()  # list of model info dicts
        available_versions = [m["version"] for m in models if m.get("version")]
    except requests.exceptions.ConnectionError:
        st.error("Can't reach the API. Is `uvicorn main:app --reload` running on port 8000?")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.text}")
        st.stop()

    st.markdown(
        f"**Available versions:** "
        f"{', '.join(available_versions) if available_versions else 'none found'} "
        f"· active (config.yaml): `{_CONFIGURED_VERSION}`"
    )

    selected_version = st.selectbox(
        "Inspect version",
        options=["(active)"] + available_versions,
        key="inspect_version",
    )

    # (active) → versi yang sedang diserve (dari config.yaml)
    if selected_version == "(active)":
        lookup_version = _CONFIGURED_VERSION
    else:
        lookup_version = selected_version

    try:
        info_resp = requests.get(
            f"{API_BASE}/registry/{lookup_version}", timeout=5
        )
        info_resp.raise_for_status()
        model_info = info_resp.json()  # {version, model_file_exists, metadata_file_exists, metadata}
    except requests.exceptions.ConnectionError:
        st.error("Can't reach the API. Is `uvicorn main:app --reload` running on port 8000?")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.text}")
        st.stop()

    metadata = model_info.get("metadata", {}) if isinstance(model_info, dict) else {}

    st.markdown(
        f"**Version:** `{model_info.get('version', '?')}` "
        f"· **Model:** `{metadata.get('model_name', '?')}`"
    )
    st.caption(
        f"Algorithm: `{metadata.get('model_type', '?')}` "
        f"· sklearn: `{metadata.get('sklearn_version', '?')}` "
        f"· model file exists: `{model_info.get('model_file_exists')}`"
    )
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Training params**")
        st.json(metadata.get("training", {}))
    with col2:
        st.markdown("**Metrics & ranges**")
        st.json(
            {
                "target": metadata.get("target"),
                "target_range": metadata.get("target_range"),
                "prediction_range": metadata.get("prediction_range"),
                "n_features": len(metadata.get("features", [])),
                "encoding_maps_source": metadata.get("encoding_maps_source"),
            }
        )

    features = metadata.get("features", [])
    if features:
        st.markdown("**Features**")
        st.dataframe(
            pd.DataFrame({"feature": features}), hide_index=True, use_container_width=True
        )

    st.markdown("**Preprocessing**")
    st.json(metadata.get("preprocessing", {}))

    if metadata.get("created_at") or metadata.get("description"):
        st.markdown("**Meta**")
        st.json(
            {
                "created_at": metadata.get("created_at"),
                "description": metadata.get("description"),
            }
        )


# ---------------------------------------------------------------------------
# Tab 4: Monitoring Dashboard — GET /metrics + GET /health
# ---------------------------------------------------------------------------
with tab_monitor:
    st.subheader("Production Monitoring")
    st.caption(
        "Reads service metrics from GET /metrics and health status from "
        "GET /health. (This project exposes aggregate metrics only; "
        "per-prediction distribution / latency analytics are not available as "
        "API endpoints, so detailed charts are shown only where the API returns "
        "the underlying data.)"
    )

    if st.button("Refresh"):
        st.rerun()

    try:
        metrics = requests.get(f"{API_BASE}/metrics", timeout=5).json()
        health = requests.get(f"{API_BASE}/health", timeout=5).json()
    except requests.exceptions.ConnectionError:
        st.error("Can't reach the API. Is `uvicorn main:app --reload` running on port 8000?")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.text}")
        st.stop()

    # --------------------------------------------------------
    # Health banner (mirrors the freshness banner pattern)
    # --------------------------------------------------------
    health_status = health.get("status", "unknown")
    components = health.get("components", {})
    model_comp = components.get("model", {})
    routing_comp = components.get("routing", {})

    if health_status == "healthy":
        st.success("Service is healthy -- model and routing ready.")
    else:
        detail = model_comp.get("error") or routing_comp.get("error") or "see components below"
        st.warning(f"Service is degraded: {detail}")

    # --------------------------------------------------------
    # KPI Cards (from GET /metrics)
    # --------------------------------------------------------
    uptime = metrics.get("uptime_seconds")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Status", metrics.get("status", "—"))
    c2.metric("Model version", metrics.get("model_version", "—"))
    c3.metric("Uptime (s)", f"{uptime:.1f}" if uptime is not None else "—")
    c4.metric("Requests total", metrics.get("requests_total", 0))
    c5.metric("Predictions total", metrics.get("predictions_total", 0))
    st.divider()

    # --------------------------------------------------------
    # Main Charts (real data only — no fabrication)
    # --------------------------------------------------------
    left, right = st.columns(2)
    with left:
        st.markdown("### Traffic overview")
        totals = {
            "Requests": metrics.get("requests_total", 0),
            "Predictions": metrics.get("predictions_total", 0),
        }
        if sum(totals.values()) > 0:
            fig = px.bar(
                x=list(totals.keys()),
                y=list(totals.values()),
                labels={"x": "Event type", "y": "Cumulative count"},
                color=list(totals.keys()),
                color_discrete_sequence=["#1f77b4", "#ff7f0e"],
            )
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No predictions logged yet.")

    with right:
        st.markdown("### Health components")
        rows = []
        for name, comp in [("Model", model_comp), ("Routing", routing_comp)]:
            status = comp.get("status", "—")
            if status == "ok":
                if name == "Model":
                    detail = (
                        f"v{comp.get('version', '?')} - "
                        f"{comp.get('model_name', '?')} - "
                        f"{len(comp.get('features', []))} features"
                    )
                else:
                    detail = comp.get("provider", "?")
            else:
                detail = comp.get("error", "unknown error")
            rows.append({"Component": name, "Status": status, "Details": detail})
        st.dataframe(
            pd.DataFrame(rows), hide_index=True, use_container_width=True
        )

    # --------------------------------------------------------
    # Secondary info
    # --------------------------------------------------------
    left, right = st.columns(2)
    with left:
        st.markdown("### Model info")
        st.json(
            {
                "model_name": metrics.get("model_name"),
                "model_version": metrics.get("model_version"),
                "configured_version": _CONFIGURED_VERSION,
            }
        )
    with right:
        st.markdown("### Configured risk thresholds")
        st.json(_RISK_THRESHOLDS if _RISK_THRESHOLDS else {"(none)": None})

    # --------------------------------------------------------
    # Raw API responses (mirrors the "Latency Details" expander)
    # --------------------------------------------------------
    with st.expander("Raw API responses"):
        st.json({"metrics": metrics, "health": health})
