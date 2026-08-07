"""
Smart Protection Platform — Streamlit Interface (Client Application)

Web app ini adalah CONSUMER dari FastAPI service (main.py). Semua business
logic & model inference ada di API; interface ini cuma manggil endpoint via
HTTP request dan menampilkan hasilnya — sesuai prinsip "separate the
backend (model inference) from the frontend through HTTP APIs".

Cara jalankan:
    1. Jalankan API dulu di terminal terpisah:
         uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    2. Jalankan interface ini di terminal lain:
         streamlit run interface.py
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

DEFAULT_API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

st.set_page_config(page_title="Smart Protection Platform", page_icon="🛡️", layout="wide")

st.title("🛡️ Smart Protection Platform")
st.caption(
    "Estimasi risk score berbasis pola kejahatan historis. "
    "**Disclaimer:** skor ini adalah estimasi berbasis pola historis, "
    "bukan prediksi kepastian suatu kejadian. Konteks dataset (Chicago) "
    "berbeda dengan konteks lokal — gunakan sebagai demo, bukan acuan operasional."
)

# ---------------------------------------------------------------------
# Sidebar — API config & health check
# ---------------------------------------------------------------------
with st.sidebar:
    st.subheader("⚙️ Konfigurasi")
    api_base_url = st.text_input("API base URL", value=DEFAULT_API_BASE_URL).rstrip("/")
    st.caption(f"Endpoint aktif: `{api_base_url}`")

    if st.button("🔄 Cek koneksi API (GET /health)"):
        try:
            r = requests.get(f"{api_base_url}/health", timeout=5)
            if r.status_code == 200:
                st.success(f"API OK ({r.status_code})")
            else:
                st.warning(f"API merespon dengan status {r.status_code}")
        except requests.RequestException as e:
            st.error(f"Tidak bisa connect ke API: {e}")

tab_predict, tab_commute, tab_registry, tab_monitoring = st.tabs(
    ["📍 Live Prediction", "🧭 Safe Commute", "📦 Model Registry", "📊 Monitoring"]
)

# ---------------------------------------------------------------------
# TAB 1 — Live Prediction (POST /predict-risk/)
# ---------------------------------------------------------------------
with tab_predict:
    st.subheader("Real-time Risk Prediction")
    st.caption("Calls `POST /predict-risk/` — model runs live on the exact input given.")

    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=-6.20, format="%.5f")
        hour = st.slider("Hour of day", 0, 23, 20)
    with col2:
        lon = st.number_input("Longitude", value=106.80, format="%.5f")
        day = st.selectbox("Day of week", DAYS, index=5)

    if st.button("🔮 Predict Risk Score", type="primary"):
        payload = {"lat": lat, "lon": lon, "hour": hour, "day": day}
        try:
            r = requests.post(f"{api_base_url}/predict-risk/", json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                score = data.get("risk_score", 0)
                level = data.get("risk_level", "Unknown")
                badge = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(level, "⚪")
                m1, m2 = st.columns(2)
                m1.metric("Risk Score", f"{score:.1f} / 100")
                m2.metric("Risk Level", f"{badge} {level}")
            else:
                # 422 (invalid input) & other error cases are surfaced here as-is —
                # they're behaviors of this same endpoint, not separate endpoints.
                st.error(f"Request gagal ({r.status_code})")
                st.json(r.json())
        except requests.RequestException as e:
            st.error(f"Gagal menghubungi API: {e}")

# ---------------------------------------------------------------------
# TAB 2 — Safe Commute (POST /safe-commute/)
# ---------------------------------------------------------------------
with tab_commute:
    st.subheader("Safe Commute Route Planner")
    st.caption("Calls `POST /safe-commute/` — cari rute dan hitung skor risiko sepanjang rute.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Start**")
        start_lat = st.number_input("Start latitude", value=-6.20, format="%.5f", key="start_lat")
        start_lon = st.number_input("Start longitude", value=106.80, format="%.5f", key="start_lon")
    with col2:
        st.markdown("**Destination**")
        dest_lat = st.number_input("Destination latitude", value=-6.21, format="%.5f", key="dest_lat")
        dest_lon = st.number_input("Destination longitude", value=106.82, format="%.5f", key="dest_lon")

    col3, col4 = st.columns(2)
    with col3:
        commute_hour = st.slider("Departure hour", 0, 23, 22, key="commute_hour")
    with col4:
        commute_day = st.selectbox("Day", DAYS, index=5, key="commute_day")

    if st.button("🧭 Plan Safe Route", type="primary"):
        payload = {
            "start": {"lat": start_lat, "lon": start_lon},
            "destination": {"lat": dest_lat, "lon": dest_lon},
            "hour": commute_hour,
            "day": commute_day,
        }
        try:
            r = requests.post(f"{api_base_url}/safe-commute/", json=payload, timeout=20)
            if r.status_code == 200:
                data = r.json()
                m1, m2, m3 = st.columns(3)
                m1.metric("Route Risk Score", f"{data['route_risk_score']:.1f}")
                m2.metric("Distance", f"{data['distance_meters'] / 1000:.1f} km")
                m3.metric("Duration", f"{data['duration_seconds'] / 60:.1f} min")
                st.info(data.get("recommendation", ""))
                st.caption(f"Routing provider: {data.get('routing_provider', 'unknown')}")

                if data.get("segment_risks"):
                    df = pd.DataFrame(data["segment_risks"])
                    st.map(df.rename(columns={"lat": "latitude", "lon": "longitude"}))
                    st.dataframe(df, use_container_width=True)
            else:
                st.error(f"Request gagal ({r.status_code})")
                st.json(r.json())
        except requests.RequestException as e:
            st.error(f"Gagal menghubungi API: {e}")

# ---------------------------------------------------------------------
# TAB 3 — Model Registry (GET /model/info, GET /registry/)
# ---------------------------------------------------------------------
with tab_registry:
    st.subheader("Model Registry")

    st.markdown("#### 🟢 Model yang sedang aktif melayani prediksi")
    st.caption("`GET /model/info`")
    try:
        r = requests.get(f"{api_base_url}/model/info", timeout=10)
        if r.status_code == 200:
            info = r.json()
            m1, m2 = st.columns(2)
            m1.metric("Model name", info.get("model_name", "unknown"))
            m2.metric("Active version", info.get("model_version", "unknown"))
            with st.expander("Feature names"):
                st.write(info.get("feature_names", []))
            with st.expander("Metadata mentah"):
                st.json(info.get("metadata", {}))
        else:
            st.warning(f"Tidak bisa mengambil info model aktif ({r.status_code})")
    except requests.RequestException as e:
        st.error(f"Gagal menghubungi API: {e}")

    st.markdown("#### 📚 Semua versi model terdaftar")
    st.caption("`GET /registry/`")
    try:
        r = requests.get(f"{api_base_url}/registry/", timeout=10)
        if r.status_code == 200:
            models = r.json()
            if models:
                rows = []
                for m in models:
                    meta = m.get("metadata", {})
                    row = {
                        "version": m.get("version"),
                        "model_file_exists": m.get("model_file_exists"),
                        "trained_at": meta.get("trained_at") or meta.get("created_at"),
                    }
                    row.update({f"metric_{k}": v for k, v in meta.get("metrics", {}).items()})
                    rows.append(row)
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            else:
                st.info("Belum ada model terdaftar di registry.")
        else:
            st.warning(f"Tidak bisa mengambil registry ({r.status_code})")
    except requests.RequestException as e:
        st.error(f"Gagal menghubungi API: {e}")

# ---------------------------------------------------------------------
# TAB 4 — Monitoring (GET /metrics, /monitoring/drift, /monitoring/model-performance)
# ---------------------------------------------------------------------
with tab_monitoring:
    st.subheader("Production Monitoring")

    st.markdown("#### ⏱️ Application metrics")
    st.caption("`GET /metrics`")
    try:
        r = requests.get(f"{api_base_url}/metrics", timeout=10)
        if r.status_code == 200:
            m = r.json()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Status", m.get("status", "unknown"))
            c2.metric("Uptime (s)", f"{m.get('uptime_seconds', 0):.0f}")
            c3.metric("Total requests", m.get("requests_total", 0))
            c4.metric("Total predictions", m.get("predictions_total", 0))
        else:
            st.warning(f"Tidak bisa mengambil metrics ({r.status_code})")
    except requests.RequestException as e:
        st.error(f"Gagal menghubungi API: {e}")

    st.divider()
    st.markdown("#### 🌊 Drift detection")
    st.caption("`GET /monitoring/drift` — PSI antara baseline & window terbaru dari log prediksi.")
    if st.button("Refresh drift report"):
        try:
            r = requests.get(f"{api_base_url}/monitoring/drift", timeout=10)
            if r.status_code == 200:
                report = r.json()
                status_badge = {
                    "stable": "🟢 Stable",
                    "moderate_shift": "🟡 Moderate shift",
                    "significant_shift": "🔴 Significant shift",
                    "insufficient_data": "⚪ Insufficient data",
                }.get(report["overall_status"], report["overall_status"])
                st.metric("Overall status", status_badge)
                if report.get("note"):
                    st.info(report["note"])
                if report.get("metrics"):
                    df = pd.DataFrame(report["metrics"])
                    st.bar_chart(df.set_index("feature")["psi"])
                    st.dataframe(df, use_container_width=True)
            else:
                st.warning(f"Tidak bisa mengambil drift report ({r.status_code})")
        except requests.RequestException as e:
            st.error(f"Gagal menghubungi API: {e}")

    st.divider()
    st.markdown("#### 📈 Model performance across versions")
    st.caption("`GET /monitoring/model-performance`")
    if st.button("Refresh performance report"):
        try:
            r = requests.get(f"{api_base_url}/monitoring/model-performance", timeout=10)
            if r.status_code == 200:
                perf = r.json()
                st.caption(f"Active version: **{perf['active_version']}**")
                if perf.get("versions"):
                    rows = []
                    for v in perf["versions"]:
                        row = {
                            "version": v["version"],
                            "active": "✅" if v["is_active"] else "",
                            "trained_at": v.get("trained_at"),
                        }
                        row.update(v.get("metrics", {}))
                        rows.append(row)
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True)

                    numeric_cols = df.select_dtypes(include="number").columns.tolist()
                    if numeric_cols:
                        metric_choice = st.selectbox("Chart metric", numeric_cols)
                        st.bar_chart(df.set_index("version")[metric_choice])
                else:
                    st.info("Belum ada metadata metrics tersimpan di model_registry.")
            else:
                st.warning(f"Tidak bisa mengambil performance report ({r.status_code})")
        except requests.RequestException as e:
            st.error(f"Gagal menghubungi API: {e}")

st.divider()
st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
