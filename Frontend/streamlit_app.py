"""
CKD Clinical Diagnosis System  –  NephroScan
Professional Streamlit frontend: Landing page, Light / Dark mode, SQLite persistence,
Lottie animations, and Plotly interactive charts.
"""

import json
import sys
import os
import threading
import time
from datetime import datetime, date as dt_date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_lottie import st_lottie

# ── Auto-start Flask backend in a background thread ───────────────────────────
def _start_flask_backend():
    """Start the Flask API server in a daemon thread (once per process)."""
    try:
        import socket
        # Check if something is already listening on port 5000
        with socket.create_connection(("127.0.0.1", 5000), timeout=1):
            return  # Flask already running — do nothing
    except OSError:
        pass  # Port free — start Flask

    # Add Frontend directory to path so `from app import app` works
    _frontend_dir = os.path.dirname(os.path.abspath(__file__))
    if _frontend_dir not in sys.path:
        sys.path.insert(0, _frontend_dir)

    from app import app as _flask_app, load_models as _load_models
    _load_models()  # pre-load models before serving requests

    t = threading.Thread(
        target=lambda: _flask_app.run(host="127.0.0.1", port=5000,
                                      debug=False, use_reloader=False),
        daemon=True,
        name="flask-backend",
    )
    t.start()
    # Give Flask a moment to bind the port
    time.sleep(2)

# On Render (or any cloud with FLASK_API_URL set), the Flask service runs as a
# separate Render web service — no need to start it locally.
_IS_CLOUD = bool(os.environ.get("RENDER") or os.environ.get("FLASK_API_URL"))
if not _IS_CLOUD:
    _start_flask_backend()

from database import (
    authenticate_user,
    change_password,
    get_all_patients,
    get_patient_predictions,
    get_summary_stats,
    save_patient,
    save_prediction,
    add_user,
    get_all_users,
    update_patient,
    delete_patient,
    delete_user,
    update_user,
    get_patient,
)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be the very first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NephroScan – CKD Clinical System",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="auto",
)

_flask_base = os.environ.get("FLASK_API_URL", "http://127.0.0.1:5000").rstrip("/")
API_URL     = f"{_flask_base}/api/predict"
EXPLAIN_URL = f"{_flask_base}/api/explain"


# ─────────────────────────────────────────────────────────────────────────────
# ROLE-BASED ACCESS HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def get_role() -> str:
    """Return the current user's role: admin | doctor | nurse."""
    return st.session_state.get("user_info", {}).get("role", "nurse")


def is_verified_doctor() -> bool:
    """
    A Doctor sees FULL analysis only when their full_name starts with 'Dr.'.
    Admins always get full access regardless.
    """
    role = get_role()
    if role == "admin":
        return True
    if role == "doctor":
        name = st.session_state.get("user_info", {}).get("full_name", "")
        return name.strip().startswith("Dr.")
    return False


def require_role(*allowed_roles):
    """
    Guard function — shows an access-denied banner and returns False
    if the current user's role is not in allowed_roles.
    """
    if get_role() not in allowed_roles:
        t = get_t()
        role = get_role().title()
        st.markdown(
            f'<div class="alert-danger">'
            f'<strong>⛔ Access Denied</strong> — This section requires '
            f'higher privileges. Your role: <strong>{role}</strong>.</div>',
            unsafe_allow_html=True,
        )
        if st.button("← Back to Dashboard", key="rbac_back"):
            st.session_state.current_page = "dashboard"
            st.rerun()
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
def init_session():
    defaults = {
        "authenticated": False,
        "current_page": "landing",
        "patient_data": {},
        "medical_data": {},
        "prediction_result": None,
        "username": "",
        "user_info": {},
        "dark_mode": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# THEME PALETTES
# ─────────────────────────────────────────────────────────────────────────────
LIGHT = {
    "page_bg":        "#F0F4F8",
    "surface":        "#FFFFFF",
    "surface2":       "#EBF2F7",
    "border":         "#D1E3EE",
    "primary":        "#1B6CA8",
    "primary_dark":   "#134E7A",
    "primary_light":  "#E8F2FB",
    "accent":         "#28A0A0",
    "text":           "#1A202C",
    "text_muted":     "#5A6478",
    "danger":         "#C53030",
    "danger_bg":      "#FFF5F5",
    "success":        "#276749",
    "success_bg":     "#F0FFF4",
    "warning":        "#B7791F",
    "warning_bg":     "#FFFBEB",
    "input_bg":       "#FFFFFF",
    "input_border":   "#CBD5E0",
    "hr":             "#D1E3EE",
    "tag_ckd_bg":     "#FED7D7",
    "tag_ckd_text":   "#C53030",
    "tag_ok_bg":      "#C6F6D5",
    "tag_ok_text":    "#276749",
    "scrollbar":      "#CBD5E0",
}

DARK = {
    "page_bg":        "#0D1117",
    "surface":        "#161B22",
    "surface2":       "#1C2333",
    "border":         "#2D3748",
    "primary":        "#3B9EDD",
    "primary_dark":   "#2B7AB5",
    "primary_light":  "#1A2F45",
    "accent":         "#38B2AC",
    "text":           "#E2E8F0",
    "text_muted":     "#8B98A8",
    "danger":         "#FC8181",
    "danger_bg":      "#2D1B1B",
    "success":        "#68D391",
    "success_bg":     "#1A2D1A",
    "warning":        "#F6AD55",
    "warning_bg":     "#2D2410",
    "input_bg":       "#1C2333",
    "input_border":   "#3D4F63",
    "hr":             "#2D3748",
    "tag_ckd_bg":     "#4A1919",
    "tag_ckd_text":   "#FC8181",
    "tag_ok_bg":      "#1A3D2B",
    "tag_ok_text":    "#68D391",
    "scrollbar":      "#3D4F63",
}


def get_t():
    return DARK if st.session_state.get("dark_mode", False) else LIGHT


# ─────────────────────────────────────────────────────────────────────────────
# LOTTIE HELPER
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_lottie_url(url: str):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def inject_css():
    t = get_t()
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif !important;
        color: {t['text']} !important;
    }}
    .stApp, .main {{
        background-color: {t['page_bg']} !important;
    }}
    .main .block-container {{
        padding: 1.5rem 2rem 3rem 2rem !important;
        max-width: 1280px !important;
    }}
    #MainMenu, footer, header {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}

    section[data-testid="stSidebar"] {{
        background: {t['surface']} !important;
        border-right: 1px solid {t['border']} !important;
    }}

    /* ── System banner ── */
    .sys-banner {{
        background: linear-gradient(135deg, {t['primary_dark']} 0%, {t['primary']} 60%, {t['accent']} 100%);
        padding: 1.4rem 2rem;
        border-radius: 14px;
        color: #fff;
        text-align: center;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(27,108,168,0.25);
    }}
    .sys-banner h1 {{
        margin: 0; font-size: 2rem; font-weight: 700; letter-spacing: -0.02em;
    }}
    .sys-banner p {{
        margin: 0.3rem 0 0; opacity: 0.88; font-size: 0.97rem;
    }}

    /* ── Surface card ── */
    .card {{
        background: {t['surface']};
        border: 1px solid {t['border']};
        border-radius: 12px;
        padding: 1.5rem 1.8rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 1px 6px rgba(0,0,0,0.06);
    }}
    .card-title {{
        display: flex; align-items: center; gap: 0.5rem;
        font-size: 1.05rem; font-weight: 600; color: {t['primary']};
        padding-bottom: 0.75rem;
        border-bottom: 1px solid {t['border']};
        margin-bottom: 1.2rem;
    }}

    /* ── Login ── */
    .login-wrap {{
        max-width: 440px; margin: 0 auto;
        background: {t['surface']};
        border: 1px solid {t['border']};
        border-radius: 18px; padding: 2.5rem 2.5rem 2rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.10);
    }}
    .login-icon  {{ text-align:center; font-size:3.2rem; margin-bottom:0.4rem; }}
    .login-title {{ text-align:center; font-size:1.5rem; font-weight:700; color:{t['primary']}; margin-bottom:0.2rem; }}
    .login-sub   {{ text-align:center; font-size:0.88rem; color:{t['text_muted']}; margin-bottom:1.6rem; }}

    /* ── Navbar ── */
    .navbar {{
        background: {t['surface']};
        border: 1px solid {t['border']};
        border-radius: 12px; padding: 0.75rem 1.5rem;
        display: flex; align-items: center;
        margin-bottom: 1.4rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }}
    .nav-brand {{
        display: flex; align-items: center; gap: 0.6rem;
        font-size: 1.05rem; font-weight: 700; color: {t['primary']};
    }}
    .nav-user {{
        font-size: 0.83rem; color: {t['text_muted']};
        margin-left: 0.8rem; background: {t['primary_light']};
        padding: 0.2rem 0.7rem; border-radius: 20px; border: 1px solid {t['border']};
    }}

    /* ── Section label ── */
    .sec-label {{
        display: flex; align-items: center; gap: 0.5rem;
        font-size: 0.9rem; font-weight: 600; color: {t['primary']};
        background: {t['primary_light']};
        border-left: 3px solid {t['primary']};
        padding: 0.55rem 1rem; border-radius: 0 8px 8px 0;
        margin: 1.2rem 0 0.8rem;
    }}

    /* ── Patient strip ── */
    .patient-strip {{
        background: {t['surface2']}; border: 1px solid {t['border']};
        border-radius: 10px; padding: 0.75rem 1.2rem;
        font-size: 0.88rem; color: {t['text_muted']}; margin-bottom: 1rem;
    }}
    .patient-strip strong {{ color: {t['text']}; }}

    /* ── Step pills ── */
    .progress-row {{ display:flex; gap:0.5rem; margin-bottom:1.4rem; align-items:center; }}
    .step-pill {{
        padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.82rem; font-weight: 500;
        background: {t['surface2']}; border: 1px solid {t['border']}; color: {t['text_muted']};
    }}
    .step-pill.active {{ background:{t['primary']}; color:#fff; border-color:{t['primary']}; }}
    .step-pill.done   {{ background:{t['success_bg']}; color:{t['success']}; border-color:{t['success']}; }}

    /* ── Metric tiles ── */
    .metric-tile {{
        background: {t['surface']}; border: 1px solid {t['border']};
        border-radius: 12px; padding: 1.2rem 1.4rem; text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }}
    .metric-tile .val {{ font-size:2rem; font-weight:700; color:{t['primary']}; line-height:1.1; }}
    .metric-tile .lbl {{ font-size:0.8rem; color:{t['text_muted']}; margin-top:0.2rem;
                         text-transform:uppercase; letter-spacing:0.04em; }}

    /* ── Model card ── */
    .model-card {{
        background: {t['surface2']}; border: 1px solid {t['border']};
        border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.7rem;
    }}
    .model-name {{ font-size:0.88rem; font-weight:600; color:{t['text']}; margin-bottom:0.4rem; }}
    .tag {{ display:inline-block; padding:0.15rem 0.65rem; border-radius:12px;
             font-size:0.78rem; font-weight:600; }}
    .tag-ckd {{ background:{t['tag_ckd_bg']}; color:{t['tag_ckd_text']}; }}
    .tag-ok  {{ background:{t['tag_ok_bg']};  color:{t['tag_ok_text']};  }}
    .conf-track {{ background:{t['border']}; border-radius:8px; height:8px;
                   margin-top:0.45rem; overflow:hidden; }}
    .conf-fill-ckd {{ height:100%; border-radius:8px; background:{t['danger']}; }}
    .conf-fill-ok  {{ height:100%; border-radius:8px; background:{t['success']}; }}

    /* ── Ensemble banners ── */
    .ensemble-ckd {{
        background: linear-gradient(135deg,#7B1D1D 0%,{t['danger']} 100%);
        color:#fff; border-radius:14px; padding:2rem; text-align:center; margin:1.2rem 0;
    }}
    .ensemble-ok {{
        background: linear-gradient(135deg,#1A3D2B 0%,{t['accent']} 100%);
        color:#fff; border-radius:14px; padding:2rem; text-align:center; margin:1.2rem 0;
    }}
    .ens-verdict {{ font-size:1.6rem; font-weight:700; letter-spacing:0.02em; margin:0.5rem 0; }}
    .ens-sub {{ font-size:0.95rem; opacity:0.88; }}

    /* ── Alert boxes ── */
    .alert-danger  {{ background:{t['danger_bg']};  border-left:4px solid {t['danger']};
                      border-radius:0 10px 10px 0; padding:0.85rem 1.2rem;
                      color:{t['danger']};  font-size:0.9rem; margin:0.8rem 0; }}
    .alert-info    {{ background:{t['primary_light']}; border-left:4px solid {t['primary']};
                      border-radius:0 10px 10px 0; padding:0.85rem 1.2rem;
                      color:{t['primary']}; font-size:0.9rem; margin:0.8rem 0; }}
    .alert-success {{ background:{t['success_bg']}; border-left:4px solid {t['success']};
                      border-radius:0 10px 10px 0; padding:0.85rem 1.2rem;
                      color:{t['success']}; font-size:0.9rem; margin:0.8rem 0; }}
    .alert-warning {{ background:{t['warning_bg']}; border-left:4px solid {t['warning']};
                      border-radius:0 10px 10px 0; padding:0.85rem 1.2rem;
                      color:{t['warning']}; font-size:0.9rem; margin:0.8rem 0; }}

    /* ── Widgets ── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea textarea,
    .stSelectbox > div > div {{
        background-color: {t['input_bg']} !important;
        color: {t['text']} !important;
        border: 1.5px solid {t['input_border']} !important;
        border-radius: 8px !important;
    }}
    label, .stSelectbox label, .stTextInput label {{
        color: {t['text_muted']} !important;
        font-size: 0.85rem !important; font-weight: 500 !important;
    }}

    /* ── Buttons ── */
    .stButton > button {{
        border-radius: 8px !important; font-weight: 600 !important;
        font-size: 0.9rem !important; padding: 0.55rem 1.2rem !important;
        border: none !important;
        background: linear-gradient(135deg,{t['primary_dark']} 0%,{t['primary']} 100%) !important;
        color: #fff !important;
        transition: opacity 0.2s, transform 0.15s !important;
    }}
    .stButton > button:hover {{ opacity:0.92 !important; transform:translateY(-1px) !important; }}

    hr {{ border-color:{t['hr']} !important; margin:1rem 0 !important; }}

    ::-webkit-scrollbar {{ width:6px; }}
    ::-webkit-scrollbar-thumb {{ background:{t['scrollbar']}; border-radius:4px; }}

    .stProgress > div > div > div > div {{
        background: linear-gradient(90deg,{t['primary']},{t['accent']}) !important;
    }}

    .clinical-footer {{
        text-align:center; padding:1.8rem;
        color:{t['text_muted']}; font-size:0.8rem;
        border-top:1px solid {t['border']}; margin-top:2rem;
    }}

    /* ── Sidebar navigation ── */
    section[data-testid="stSidebar"] > div:first-child {{
        padding-top: 1.2rem;
    }}
    .sidebar-logo {{
        text-align:center; padding:0.8rem 0 1.2rem;
        border-bottom:1px solid {t['border']}; margin-bottom:0.8rem;
        font-size:1.3rem; font-weight:700; color:{t['primary']};
    }}
    .sidebar-user {{
        background:{t['surface2']}; border-radius:10px;
        padding:0.7rem 0.9rem; margin-bottom:1rem; font-size:0.85rem;
        color:{t['text_muted']}; text-align:center;
    }}
    .sidebar-nav-item {{
        display:flex; align-items:center; gap:0.7rem;
        padding:0.6rem 1rem; border-radius:10px; margin-bottom:0.3rem;
        cursor:pointer; font-size:0.9rem; color:{t['text']};
        transition: background 0.15s;
    }}
    .sidebar-nav-active {{
        background:{t['primary_light']}; color:{t['primary']};
        font-weight:600; border-left:3px solid {t['primary']};
    }}

    /* ── Landing page ── */
    .hero-section {{
        background: linear-gradient(135deg, {t['primary_dark']} 0%, {t['primary']} 55%, {t['accent']} 100%);
        border-radius:20px; padding:4rem 3rem; color:#fff;
        text-align:center; margin-bottom:2.5rem;
        box-shadow: 0 8px 40px rgba(27,108,168,0.28);
    }}
    .hero-section h1 {{ font-size:2.8rem; font-weight:800; margin:0 0 0.7rem; letter-spacing:-0.03em; }}
    .hero-section p  {{ font-size:1.15rem; opacity:0.9; max-width:680px; margin:0 auto 1.8rem; }}
    .hero-badge {{
        display:inline-block; background:rgba(255,255,255,0.2); color:#fff;
        border:1px solid rgba(255,255,255,0.4); border-radius:30px;
        padding:0.3rem 1rem; font-size:0.85rem; margin-bottom:1.2rem;
    }}
    .hero-cta {{
        background:#fff !important; color:{t['primary']} !important;
        font-size:1rem !important; font-weight:700 !important;
        padding:0.8rem 2.2rem !important; border-radius:40px !important;
        box-shadow:0 4px 18px rgba(0,0,0,0.18) !important;
        border:none !important; cursor:pointer;
    }}
    .hero-cta:hover {{ transform:translateY(-2px) !important; box-shadow:0 8px 28px rgba(0,0,0,0.22) !important; }}

    .feature-card {{
        background:{t['surface']}; border:1px solid {t['border']};
        border-radius:16px; padding:1.8rem 1.5rem; text-align:center;
        box-shadow:0 2px 12px rgba(0,0,0,0.06); height:100%;
        transition: transform 0.2s, box-shadow 0.2s;
    }}
    .feature-card:hover {{ transform:translateY(-4px); box-shadow:0 8px 28px rgba(0,0,0,0.1); }}
    .feature-icon {{ font-size:2.8rem; margin-bottom:0.8rem; }}
    .feature-title {{ font-size:1.1rem; font-weight:700; color:{t['primary']}; margin-bottom:0.5rem; }}
    .feature-desc  {{ font-size:0.9rem; color:{t['text_muted']}; line-height:1.6; }}

    .stat-pill {{
        background:{t['primary_light']}; border:1px solid {t['border']};
        border-radius:14px; padding:1.2rem 1rem; text-align:center;
    }}
    .stat-pill h2 {{ font-size:2rem; font-weight:800; color:{t['primary']}; margin:0; }}
    .stat-pill p  {{ font-size:0.82rem; color:{t['text_muted']}; margin:0.25rem 0 0; }}

    .section-heading {{
        font-size:1.6rem; font-weight:700; color:{t['text']};
        text-align:center; margin:2.5rem 0 0.5rem;
    }}
    .section-sub {{
        font-size:0.95rem; color:{t['text_muted']}; text-align:center;
        margin-bottom:2rem;
    }}

    .about-box {{
        background:{t['surface']}; border:1px solid {t['border']};
        border-radius:16px; padding:2rem 2.5rem;
        box-shadow:0 2px 12px rgba(0,0,0,0.05);
    }}
    .contact-field {{
        background:{t['input_bg']}; border:1.5px solid {t['input_border']};
        border-radius:10px; padding:0.7rem 1rem; width:100%;
        color:{t['text']}; font-size:0.9rem; margin-bottom:0.8rem;
        resize:vertical; font-family:'Inter',sans-serif;
    }}

    .landing-login-btn > button {{
        background: linear-gradient(135deg, {t['primary_dark']}, {t['accent']}) !important;
        color:#fff !important; font-size:1.05rem !important; font-weight:700 !important;
        padding:0.7rem 2rem !important; border-radius:40px !important; border:none !important;
        width:100%;
    }}

    /* ── Role badges ── */
    .role-badge {{
        display:inline-block; border-radius:20px; padding:0.2rem 0.75rem;
        font-size:0.75rem; font-weight:700; letter-spacing:0.04em; text-transform:uppercase;
    }}
    .role-admin  {{ background:#FED7AA; color:#9C4221; }}
    .role-doctor {{ background:#BEE3F8; color:#1A365D; }}
    .role-nurse  {{ background:#C6F6D5; color:#1C4532; }}

    /* ── Nurse immediate-action cards ── */
    .action-card {{
        background:{t['surface']}; border:1.5px solid {t['border']};
        border-radius:14px; padding:1.3rem 1.5rem; margin-bottom:0.9rem;
    }}
    .action-card-urgent {{ border-left:5px solid {t['danger']};  }}
    .action-card-warn   {{ border-left:5px solid {t['warning']}; }}
    .action-card-ok     {{ border-left:5px solid {t['success']}; }}
    .action-card-title  {{ font-size:1rem; font-weight:700; margin-bottom:0.5rem; }}
    .action-step        {{
        display:flex; align-items:flex-start; gap:0.6rem;
        font-size:0.88rem; color:{t['text']}; padding:0.3rem 0;
    }}
    .action-step-num {{
        background:{t['primary']}; color:#fff; border-radius:50%;
        width:1.5rem; height:1.5rem; display:flex; align-items:center;
        justify-content:center; flex-shrink:0; font-size:0.75rem; font-weight:700;
    }}

    /* ── Admin CRUD table buttons ── */
    .crud-danger > button {{
        background: linear-gradient(135deg,#9B1C1C,{t['danger']}) !important;
        color:#fff !important; font-size:0.8rem !important; padding:0.35rem 0.8rem !important;
    }}
    .crud-warn > button {{
        background: linear-gradient(135deg,#92400E,{t['warning']}) !important;
        color:#fff !important; font-size:0.8rem !important; padding:0.35rem 0.8rem !important;
    }}

    /* ── Restricted banner ── */
    .restricted-banner {{
        background:{t['warning_bg']}; border:1.5px solid {t['warning']};
        border-radius:12px; padding:1rem 1.5rem; color:{t['warning']}; margin-bottom:1rem;
        display:flex; align-items:center; gap:0.7rem; font-size:0.92rem;
    }}
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# REUSABLE COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────

def page_banner(title, subtitle="", icon="🩺"):
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="sys-banner"><h1>{icon} {title}</h1>{sub}</div>',
                unsafe_allow_html=True)


def step_pills(current: int):
    steps = ["Patient Details", "Medical Parameters", "Results"]
    pills = ""
    for i, s in enumerate(steps):
        cls  = "done" if i < current else ("active" if i == current else "")
        icon = "✓ " if i < current else f"{i+1}. "
        pills += f'<span class="step-pill {cls}">{icon}{s}</span>'
    st.markdown(f'<div class="progress-row">{pills}</div>', unsafe_allow_html=True)


def sec_label(label, icon=""):
    st.markdown(f'<div class="sec-label">{icon} {label}</div>', unsafe_allow_html=True)


def patient_strip():
    p = st.session_state.patient_data
    if p:
        st.markdown(f"""
        <div class="patient-strip">
            <strong>Patient:</strong> {p.get('first_name','')} {p.get('last_name','')} &nbsp;|&nbsp;
            <strong>ID:</strong> {p.get('patient_id','')} &nbsp;|&nbsp;
            <strong>Age:</strong> {p.get('age','')} yrs &nbsp;|&nbsp;
            <strong>Gender:</strong> {p.get('gender','')} &nbsp;|&nbsp;
            <strong>Dept:</strong> {p.get('department','')}
        </div>""", unsafe_allow_html=True)


def theme_toggle():
    icon = "☀️ Light" if st.session_state.dark_mode else "🌙 Dark"
    if st.button(icon, key="theme_btn"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()


def navigation_bar():
    t  = get_t()
    ui = st.session_state.user_info
    c_brand, c_np, c_dash, c_theme, c_logout = st.columns([4, 1.3, 1.3, 1, 1])

    with c_brand:
        role_icon = "👑" if ui.get("role") == "admin" else ("👨‍⚕️" if ui.get("role") == "doctor" else "👩‍⚕️")
        st.markdown(f"""
        <div class="navbar">
            <span class="nav-brand">🩺 NephroScan</span>
            <span class="nav-user">{role_icon} {ui.get('full_name', st.session_state.username)}</span>
        </div>""", unsafe_allow_html=True)

    with c_np:
        if st.button("＋ New Patient", use_container_width=True, key="nav_np"):
            st.session_state.update(
                current_page="patient_details", patient_data={},
                medical_data={}, prediction_result=None)
            st.rerun()

    with c_dash:
        if st.button("📊 Dashboard", use_container_width=True, key="nav_dash"):
            st.session_state.current_page = "dashboard"
            st.rerun()

    with c_theme:
        theme_toggle()

    with c_logout:
        if st.button("⏻ Logout", use_container_width=True, key="nav_logout"):
            st.session_state.update(
                authenticated=False, current_page="landing",
                username="", user_info={}, patient_data={},
                medical_data={}, prediction_result=None)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR  (shown only when authenticated)
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    ui  = st.session_state.user_info
    rol = ui.get("role", "nurse")
    pg  = st.session_state.current_page

    role_icon  = "👑" if rol == "admin" else ("👨‍⚕️" if rol == "doctor" else "👩‍⚕️")
    role_class = f"role-{rol}"

    with st.sidebar:
        st.markdown(f'<div class="sidebar-logo">🩺 NephroScan</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sidebar-user">{role_icon} <strong>{ui.get("full_name", st.session_state.username)}</strong>'
            f'<br><span class="role-badge {role_class}">{rol}</span></div>',
            unsafe_allow_html=True,
        )

        def nav_btn(label, icon, page_key, key_suffix=""):
            active = "sidebar-nav-active" if pg == page_key else ""
            st.markdown(f'<div class="sidebar-nav-item {active}">{icon} {label}</div>',
                        unsafe_allow_html=True)
            if st.button(label, key=f"sb_{page_key}{key_suffix}", use_container_width=True):
                st.session_state.current_page = page_key
                st.rerun()

        st.markdown("**Navigation**")
        nav_btn("Dashboard",      "📊", "dashboard")

        # Nurses can run assessments but not register/edit patients
        if rol in ("admin", "doctor"):
            nav_btn("New Patient",    "➕", "patient_details")

        nav_btn("Patient Lookup", "🔍", "patient_lookup")

        st.markdown("---")
        st.markdown("**Account**")
        nav_btn("Change Password", "🔒", "change_password")

        # Admin-only section
        if rol == "admin":
            st.markdown("---")
            st.markdown("**Administration**")
            nav_btn("User Management", "👥", "user_management")

        st.markdown("---")
        icon = "☀️ Light Mode" if st.session_state.dark_mode else "🌙 Dark Mode"
        if st.button(icon, key="sb_theme", use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

        if st.button("⏻ Logout", key="sb_logout", use_container_width=True):
            st.session_state.update(
                authenticated=False, current_page="landing",
                username="", user_info={}, patient_data={},
                medical_data={}, prediction_result=None)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# LANDING PAGE
# ─────────────────────────────────────────────────────────────────────────────
def landing_page():
    t = get_t()

    # ── Top bar: theme toggle + login button ──────────────────────────────────
    c_logo, c_space, c_theme, c_login = st.columns([3, 4, 1, 1.2])
    with c_logo:
        st.markdown(f"<h3 style='color:{t['primary']};margin:0.4rem 0'>🩺 NephroScan</h3>",
                    unsafe_allow_html=True)
    with c_theme:
        theme_toggle()
    with c_login:
        if st.button("🔐 Login", key="landing_login", use_container_width=True):
            st.session_state.current_page = "login"
            st.rerun()

    # ── Hero ──────────────────────────────────────────────────────────────────
    hero_l, hero_r = st.columns([3, 2])
    with hero_l:
        st.markdown("""
        <div class="hero-section">
            <div class="hero-badge">🏥 AI-Powered Clinical Decision Support</div>
            <h1>Early CKD Detection<br>Saves Lives</h1>
            <p>NephroScan uses an ensemble of 9 machine-learning models to identify
            Chronic Kidney Disease risk from routine clinical tests — in seconds.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("🚀  Get Started — Sign In", key="hero_cta", use_container_width=True):
            st.session_state.current_page = "login"
            st.rerun()

    with hero_r:
        lottie_med = load_lottie_url(
            "https://assets9.lottiefiles.com/packages/lf20_5njp3vgg.json")
        if lottie_med:
            st_lottie(lottie_med, height=320, key="lottie_hero")
        else:
            st.image("https://img.icons8.com/color/240/000000/kidney.png", width=220)

    st.markdown("<hr style='margin:1.5rem 0'>", unsafe_allow_html=True)

    # ── Stats row ─────────────────────────────────────────────────────────────
    s1, s2, s3, s4 = st.columns(4)
    for col, val, label in [
        (s1, "850M+",  "People affected by CKD worldwide"),
        (s2, "9",      "Ensemble ML models in NephroScan"),
        (s3, "24",     "Clinical parameters analysed"),
        (s4, "~97%",   "Ensemble prediction accuracy"),
    ]:
        with col:
            st.markdown(f"""
            <div class="stat-pill">
                <h2>{val}</h2><p>{label}</p>
            </div>""", unsafe_allow_html=True)

    # ── Features ──────────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">Why NephroScan?</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">A complete clinical intelligence platform for nephrology teams</div>',
                unsafe_allow_html=True)

    f1, f2, f3 = st.columns(3)
    features = [
        ("🤖", "9-Model Ensemble",
         "Logistic Regression, SVM, Random Forest, XGBoost, CatBoost, Gradient Boosting, "
         "Decision Tree, KNN and Naive Bayes vote together for the most reliable diagnosis."),
        ("📋", "Complete Patient Records",
         "Securely store patient demographics, clinical measurements and prediction history "
         "in an encrypted local SQLite database — fully offline capable."),
        ("📊", "Interactive Reports",
         "Visualise confidence scores across all models, track patient trends over time, "
         "and export findings with a single click."),
    ]
    for col, (icon, title, desc) in zip([f1, f2, f3], features):
        with col:
            st.markdown(f"""
            <div class="feature-card">
                <div class="feature-icon">{icon}</div>
                <div class="feature-title">{title}</div>
                <div class="feature-desc">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Interactive CKD Chart ─────────────────────────────────────────────────
    st.markdown('<div class="section-heading">📈 Global CKD Burden by Age Group</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Estimated CKD prevalence (%) — data based on published epidemiological studies</div>',
                unsafe_allow_html=True)

    age_groups = ["18–29", "30–39", "40–49", "50–59", "60–69", "70–79", "80+"]
    base_prev  = [1.2, 2.1, 4.5, 10.3, 18.7, 28.4, 38.2]

    chart_col, ctrl_col = st.columns([4, 1])
    with ctrl_col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        chart_type = st.selectbox("Chart type", ["Bar", "Line", "Area"], key="ckd_chart_type")
        gender_adj = st.select_slider(
            "Gender factor", options=["Male –10%", "Average", "Female +8%"],
            value="Average", key="ckd_gender")
        adj = -0.10 if "Male" in gender_adj else (0.08 if "Female" in gender_adj else 0.0)
        prev = [round(p * (1 + adj), 1) for p in base_prev]

    with chart_col:
        bar_color = t["primary"]
        if chart_type == "Bar":
            fig = go.Figure(go.Bar(
                x=age_groups, y=prev,
                marker=dict(
                    color=prev,
                    colorscale=[[0, t["accent"]], [1, t["primary_dark"]]],
                    showscale=False,
                    line=dict(color=t["border"], width=0.5),
                ),
                text=[f"{v}%" for v in prev],
                textposition="outside",
            ))
        elif chart_type == "Line":
            fig = go.Figure(go.Scatter(
                x=age_groups, y=prev, mode="lines+markers+text",
                line=dict(color=bar_color, width=3),
                marker=dict(size=9, color=bar_color),
                text=[f"{v}%" for v in prev],
                textposition="top center",
            ))
        else:  # Area
            fig = go.Figure(go.Scatter(
                x=age_groups, y=prev, fill="tozeroy",
                fillcolor=f"rgba(27,108,168,0.18)",
                line=dict(color=bar_color, width=2.5),
                mode="lines+markers",
                marker=dict(size=8, color=bar_color),
            ))

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=t["text"], family="Inter"),
            yaxis=dict(title="Prevalence (%)", gridcolor=t["border"],
                       ticksuffix="%", range=[0, max(prev) * 1.25]),
            xaxis=dict(title="Age Group", gridcolor=t["border"]),
            margin=dict(t=20, b=10, l=10, r=10),
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<hr style='margin:1.5rem 0'>", unsafe_allow_html=True)

    # ── About ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">About NephroScan</div>', unsafe_allow_html=True)
    a1, a2 = st.columns([3, 2])
    with a1:
        st.markdown(f"""
        <div class="about-box">
            <p style="font-size:1rem;line-height:1.8;color:{t['text']}">
            <strong>NephroScan</strong> is an AI-powered clinical decision-support platform designed
            to assist nephrologists, general practitioners and nursing staff in detecting
            Chronic Kidney Disease (CKD) at its earliest stage.
            </p>
            <p style="font-size:0.95rem;line-height:1.8;color:{t['text_muted']}">
            The system ingests 24 routine clinical and biochemical markers — including serum creatinine,
            blood urea, hemoglobin, blood pressure, and urinalysis findings — and passes them through
            an ensemble of nine independently-trained machine-learning classifiers.  A majority-vote
            mechanism produces a final CKD / Not-CKD verdict alongside per-model confidence scores,
            enabling clinicians to understand the reasoning behind each recommendation.
            </p>
            <p style="font-size:0.9rem;color:{t['danger']};margin-top:0.5rem">
            ⚠️ For clinical decision <em>support</em> only. Always confirm with a qualified nephrologist.
            </p>
        </div>""", unsafe_allow_html=True)
    with a2:
        lottie_data = load_lottie_url(
            "https://assets4.lottiefiles.com/packages/lf20_qp1q7mct.json")
        if lottie_data:
            st_lottie(lottie_data, height=260, key="lottie_about")
        else:
            st.info("NephroScan — AI for Nephrology")

    st.markdown("<hr style='margin:1.5rem 0'>", unsafe_allow_html=True)

    # ── Contact ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">Contact Us</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Have questions or want to request access? Get in touch.</div>',
                unsafe_allow_html=True)

    ct1, ct2, ct3 = st.columns([1, 2, 1])
    with ct2:
        st.markdown(f'<div class="card">', unsafe_allow_html=True)
        with st.form("contact_form"):
            con_name = st.text_input("Your Name", placeholder="Dr. Jane Smith")
            con_email = st.text_input("Email Address", placeholder="jsmith@hospital.org")
            con_dept  = st.selectbox("Department", [
                "Nephrology", "General Practice", "Internal Medicine",
                "Emergency Medicine", "Research", "Administration", "Other"])
            con_msg   = st.text_area("Message", placeholder="Describe your query or access request…",
                                     height=110)
            submitted = st.form_submit_button("📨  Send Message", use_container_width=True)
        if submitted:
            if con_name and con_email and con_msg:
                st.success(f"Thank you, {con_name}! Your message has been received. "
                           f"We'll respond to {con_email} within 24 hours.")
            else:
                st.warning("Please fill in your name, email and message.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── CTA footer ────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    cc1, cc2, cc3 = st.columns([1, 2, 1])
    with cc2:
        st.markdown(f"""
        <div class="hero-section" style="padding:2rem">
            <h2 style="margin:0 0 0.5rem;font-size:1.6rem">Ready to get started?</h2>
            <p style="margin:0 0 1.2rem;font-size:0.95rem">
            Sign in to access the full NephroScan platform.
            </p>
        </div>""", unsafe_allow_html=True)
        st.markdown('<div class="landing-login-btn">', unsafe_allow_html=True)
        if st.button("🔐  Sign In to NephroScan", key="cta_footer_login", use_container_width=True):
            st.session_state.current_page = "login"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)



# ── LOGIN ─────────────────────────────────────────────────────────────────────
def login_page():
    t = get_t()

    # Top bar
    c_back, c_sp, c_theme = st.columns([1.5, 6, 1])
    with c_back:
        if st.button("← Home", key="login_back"):
            st.session_state.current_page = "landing"
            st.rerun()
    with c_theme:
        theme_toggle()

    page_banner("NephroScan", "AI-Powered Chronic Kidney Disease Clinical Platform")

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div class="login-wrap">
            <div class="login-icon">🏥</div>
            <div class="login-title">Healthcare Provider Login</div>
            <div class="login-sub">Authorised clinical personnel only</div>
        </div>""", unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit   = st.form_submit_button("🔐  Sign In", use_container_width=True)

        if submit:
            user = authenticate_user(username, password)
            if user:
                st.session_state.update(
                    authenticated=True, username=username,
                    user_info=user, current_page="dashboard")
                st.success(f"Welcome, {user.get('full_name', username)}!")
                time.sleep(0.8)
                st.rerun()
            else:
                st.error("Invalid username or password.")

        st.markdown(f"""
        <div style="text-align:center;margin-top:1.2rem;
                    font-size:0.82rem;color:{t['text_muted']};">
            Demo: <code>admin / admin123</code> &nbsp;|&nbsp; <code>doctor / doctor123</code>
        </div>""", unsafe_allow_html=True)


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
def dashboard_page():
    navigation_bar()
    role = get_role()
    page_banner("Clinical Dashboard", "Overview & quick actions", "📊")

    # Role restriction banner for nurses
    if role == "nurse":
        st.markdown(
            '<div class="restricted-banner">🔒 <strong>Nurse Access:</strong> '
            'You can run CKD assessments and view predictions. '
            'Patient registration, editing and user management require Doctor or Admin privileges.</div>',
            unsafe_allow_html=True)

    stats = get_summary_stats()
    c1, c2, c3, c4 = st.columns(4)
    metrics = [
        (stats["total_patients"],    "Registered Patients"),
        (stats["total_predictions"], "Assessments Run"),
        (stats["ckd_positive"],      "CKD Positive"),
    ]
    # Nurses don't see user count
    if role in ("admin", "doctor"):
        metrics.append((stats["total_users"], "Clinical Users"))
    else:
        metrics.append(("—", "User Management\n(Admin only)"))

    for col, (val, lbl) in zip([c1, c2, c3, c4], metrics):
        with col:
            st.markdown(f'<div class="metric-tile"><div class="val">{val}</div>'
                        f'<div class="lbl">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<div class="card"><div class="card-title">🤖 Available ML Models</div>',
                    unsafe_allow_html=True)
        for m in ["Logistic Regression","Support Vector Machine","Decision Tree",
                  "Random Forest","Gradient Boosting","XGBoost",
                  "CatBoost","K-Nearest Neighbours","Naïve Bayes"]:
            st.markdown(f"&nbsp;&nbsp;✔ {m}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="card"><div class="card-title">📋 Recent Patients</div>',
                    unsafe_allow_html=True)
        patients = get_all_patients()
        if patients:
            for p in patients[:6]:
                st.markdown(
                    f"**{p['first_name']} {p['last_name']}** — {p['patient_id']} — Age {p['age']}")
        else:
            st.info("No patients registered yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card"><div class="card-title">⚡ Quick Actions</div>',
                unsafe_allow_html=True)
    if role == "nurse":
        qa1, qa2, qa3 = st.columns(3)
        with qa1:
            if st.button("🔬 Run Assessment",   use_container_width=True):
                st.session_state.current_page = "medical_parameters"; st.rerun()
        with qa2:
            if st.button("🔍 Patient Lookup",   use_container_width=True):
                st.session_state.current_page = "patient_lookup";     st.rerun()
        with qa3:
            if st.button("🔒 Change Password",  use_container_width=True):
                st.session_state.current_page = "change_password";    st.rerun()
    else:
        qa1, qa2, qa3, qa4 = st.columns(4)
        with qa1:
            if st.button("📋 New Assessment",  use_container_width=True):
                st.session_state.current_page = "patient_details"; st.rerun()
        with qa2:
            if st.button("🔍 Patient Lookup",  use_container_width=True):
                st.session_state.current_page = "patient_lookup";  st.rerun()
        with qa3:
            if role == "admin" and st.button("👥 Manage Users", use_container_width=True):
                st.session_state.current_page = "user_management"; st.rerun()
            elif role == "doctor":
                if st.button("🔬 Run Assessment", use_container_width=True):
                    st.session_state.current_page = "medical_parameters"; st.rerun()
        with qa4:
            if st.button("🔒 Change Password", use_container_width=True):
                st.session_state.current_page = "change_password"; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ── PATIENT DETAILS ───────────────────────────────────────────────────────────
def patient_details_page():
    navigation_bar()
    # Nurses cannot register patients
    if not require_role("admin", "doctor"):
        return
    page_banner("Patient Registration", "Step 1 – Demographics", "📋")
    step_pills(0)

    with st.form("patient_form"):
        st.markdown('<div class="card"><div class="card-title">👤 Personal Details</div>',
                    unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            patient_id = st.text_input("Patient ID *", placeholder="PAT-2026-001")
            first_name = st.text_input("First Name *", placeholder="John")
            dob        = st.date_input("Date of Birth *",
                                       value=dt_date(1990, 1, 1),
                                       min_value=dt_date(1900, 1, 1),
                                       max_value=dt_date.today())
        with c2:
            mrn        = st.text_input("Medical Record No.", placeholder="MRN-XXXXXX")
            last_name  = st.text_input("Last Name *", placeholder="Doe")
            today      = dt_date.today()
            age        = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            age        = max(0, age)
            st.number_input("Age (years) — auto-calculated", min_value=0, max_value=150,
                            value=age, disabled=True, key="age_display")
        with c3:
            gender      = st.selectbox("Gender *", ["Male","Female","Other"])
            blood_group = st.selectbox("Blood Group", ["--","A+","A-","B+","B-","AB+","AB-","O+","O-","Unknown"])
            phone       = st.text_input("Phone", placeholder="+91 XXXXX XXXXX")
        st.markdown("</div>", unsafe_allow_html=True)

        sec_label("Contact & Address", "📍")
        c4, c5, c6 = st.columns(3)
        with c4: email   = st.text_input("Email", placeholder="patient@email.com")
        with c5:
            city    = st.text_input("City",  placeholder="City")
            state   = st.text_input("State", placeholder="State")
        with c6: address = st.text_area("Address", placeholder="Street address…", height=95)

        sec_label("Referring Physician", "👨‍⚕️")
        c7, c8 = st.columns(2)
        with c7: physician  = st.text_input("Physician Name", placeholder="Dr. Smith")
        with c8: department = st.selectbox("Department", [
            "Nephrology","Internal Medicine","General Practice",
            "Urology","Emergency Medicine","Endocrinology","Other"])

        cs, cc = st.columns([3, 1])
        with cs: submit = st.form_submit_button("Continue → Medical Parameters", use_container_width=True)
        with cc: st.form_submit_button("Clear", use_container_width=True)

    if submit:
        if patient_id and first_name and last_name:
            data = dict(patient_id=patient_id, mrn=mrn, first_name=first_name,
                        last_name=last_name, date_of_birth=str(dob), age=age,
                        gender=gender, blood_group=blood_group, phone=phone,
                        email=email, address=address, city=city, state=state,
                        physician=physician, department=department)
            ok, msg = save_patient(data, registered_by=st.session_state.username)
            if ok or "already exists" in msg:
                st.session_state.patient_data     = data
                st.session_state.assessment_source = "new"
                st.session_state.current_page     = "medical_parameters"
                st.success("Patient saved! Proceeding to medical parameters…")
                time.sleep(0.5); st.rerun()
            else:
                st.error(msg)
        else:
            st.error("Patient ID, First Name and Last Name are required.")


# ── MEDICAL PARAMETERS ────────────────────────────────────────────────────────
def medical_parameters_page():
    navigation_bar()

    # Show reassessment context if patient was loaded from lookup
    source = st.session_state.get("assessment_source", "new")
    p = st.session_state.patient_data
    if source == "lookup" and p:
        t = get_t()
        st.markdown(
            f'<div class="restricted-banner" style="border-color:{t["primary"]};'
            f'background:{t["primary_light"]};color:{t["primary"]};">'
            f'🔄 <strong>Reassessment</strong> — Running new analysis for existing patient '
            f'<strong>{p.get("first_name","")} {p.get("last_name","")} '
            f'({p.get("patient_id","")})</strong>. '
            f'Demographics already loaded — enter updated medical parameters below.</div>',
            unsafe_allow_html=True)

    page_banner("Medical Parameters", "Step 2 – Clinical Test Results", "🔬")
    step_pills(1)
    patient_strip()

    with st.form("medical_form"):
        # ── Patient Age (pre-filled, editable) ───────────────────────────────
        _stored_age = int(st.session_state.patient_data.get("age", 45) or 45)
        sec_label("Patient Age", "🧑")
        age = st.number_input("Age (years)", min_value=1, max_value=120,
                              value=_stored_age,
                              help="Auto-filled from patient record — edit if needed")

        sec_label("Urine Analysis", "🧪")
        u1, u2, u3, u4 = st.columns(4)
        with u1: sg  = st.number_input("Specific Gravity", min_value=1.000, max_value=1.030,
                                        value=1.015, step=0.001, format="%.3f")
        with u2: al  = st.number_input("Albumin (0–5)",    min_value=0, max_value=5, value=0)
        with u3: su  = st.number_input("Sugar (0–5)",      min_value=0, max_value=5, value=0)
        with u4: rbc = st.selectbox("RBC in Urine",      ["normal","abnormal"])

        u5, u6, u7, u8 = st.columns(4)
        with u5: pc  = st.selectbox("Pus Cells",         ["normal","abnormal"])
        with u6: pcc = st.selectbox("Pus Cell Clumps",   ["notpresent","present"])
        with u7: ba  = st.selectbox("Bacteria",          ["notpresent","present"])
        with u8: bp  = st.number_input("Blood Pressure (mm Hg)", 50, 200, 80,
                                        help="Diastolic BP")

        sec_label("Blood Biochemistry", "🩸")
        b1, b2, b3, b4 = st.columns(4)
        with b1: bgr = st.number_input("Glucose Random (mg/dl)", 20,  500, 120)
        with b2: bu  = st.number_input("Blood Urea (mg/dl)",     1,   400,  40)
        with b3: sc  = st.number_input("Serum Creatinine (mg/dl)",0.1,20.0, 1.0, 0.1,
                                        help="Key CKD marker")
        with b4: sod = st.number_input("Sodium (mEq/L)",        100,  170, 140)

        b5, b6 = st.columns(2)
        with b5: pot  = st.number_input("Potassium (mEq/L)",  2.0, 8.0, 4.5, 0.1)
        with b6: hemo = st.number_input("Haemoglobin (g/dl)", 3.0,20.0,13.0, 0.1)

        sec_label("Haematology", "🔴")
        h1, h2, h3 = st.columns(3)
        with h1: pcv = st.number_input("Packed Cell Volume (%)",     10, 60, 40)
        with h2: wc  = st.number_input("WBC Count (cells/cumm)", 2000,30000,8000)
        with h3: rc  = st.number_input("RBC Count (millions/cmm)",1.0,10.0, 5.0, 0.1)

        sec_label("Medical History & Clinical Findings", "📋")
        m1, m2, m3 = st.columns(3)
        with m1:
            htn   = st.selectbox("Hypertension",           ["no","yes"])
            dm    = st.selectbox("Diabetes Mellitus",       ["no","yes"])
        with m2:
            cad   = st.selectbox("Coronary Artery Disease", ["no","yes"])
            appet = st.selectbox("Appetite",                ["good","poor"])
        with m3:
            pe    = st.selectbox("Pedal Oedema",            ["no","yes"])
            ane   = st.selectbox("Anaemia",                 ["no","yes"])

        st.markdown("<br>", unsafe_allow_html=True)
        fb, _, fp = st.columns([1, 2, 3])
        back_label = "← Back to Lookup" if st.session_state.get("assessment_source") == "lookup" else "← Back"
        with fb: back    = st.form_submit_button(back_label,          use_container_width=True)
        with fp: predict = st.form_submit_button("🔍 Run CKD Analysis", use_container_width=True)

    if back:
        if st.session_state.get("assessment_source") == "lookup":
            st.session_state.current_page = "patient_lookup"
        else:
            st.session_state.current_page = "patient_details"
        st.rerun()

    if predict:
        medical = dict(
            age=age,
            bp=bp, sg=sg, al=al, su=su, rbc=rbc, pc=pc, pcc=pcc, ba=ba,
            bgr=bgr, bu=bu, sc=sc, sod=sod, pot=pot, hemo=hemo,
            pcv=pcv, wc=wc, rc=rc, htn=htn, dm=dm, cad=cad,
            appet=appet, pe=pe, ane=ane)
        st.session_state.medical_data = medical

        with st.spinner("Analysing parameters across 9 ML models…"):
            try:
                resp = requests.post(API_URL, json=medical, timeout=30)
                if resp.status_code == 200:
                    result = resp.json()

                    # API may return 200 but with status='error' (preprocessing failure)
                    if result.get("status") != "success":
                        st.markdown(
                            f'<div class="alert-danger">⚠️ Prediction error: '
                            f'{result.get("message", "Unknown error from model server.")}</div>',
                            unsafe_allow_html=True)
                    else:
                        preds   = result.get("predictions", {})
                        total   = len(preds)

                        if total == 0:
                            st.markdown(
                                '<div class="alert-danger">⚠️ No model predictions returned. '
                                'The Flask server may not have loaded its model files. '
                                'Check the Flask terminal for errors.</div>',
                                unsafe_allow_html=True)
                        else:
                            ckd_cnt = sum(1 for p in preds.values() if p.get("prediction") == 1)
                            is_ckd  = ckd_cnt > total / 2
                            conf    = round((max(ckd_cnt, total - ckd_cnt) / total) * 100, 2)

                            save_prediction(
                                patient_id          = st.session_state.patient_data.get("patient_id", "UNKNOWN"),
                                ensemble_result     = "CKD" if is_ckd else "No CKD",
                                ensemble_conf       = conf,
                                ckd_detected        = int(is_ckd),
                                model_results_json  = json.dumps(preds),
                                medical_params_json = json.dumps(medical),
                                performed_by        = st.session_state.username,
                            )
                            st.session_state.prediction_result = result
                            st.session_state.current_page      = "results"
                            st.success("Analysis complete!"); time.sleep(0.4); st.rerun()
                elif resp.status_code == 500:
                    err_body = resp.json() if resp.content else {}
                    st.markdown(
                        f'<div class="alert-danger">⚠️ Model server error (500): '
                        f'{err_body.get("message", "Check the Flask terminal for details.")}</div>',
                        unsafe_allow_html=True)
                else:
                    st.error(f"API returned HTTP {resp.status_code}")
            except requests.exceptions.ConnectionError:
                st.markdown("""
                <div class="alert-danger">
                    ⚠️ <strong>Cannot reach the Flask API</strong> at
                    <code>http://127.0.0.1:5000</code>.<br>
                    Start the backend first: <code>python Frontend/app.py</code>
                </div>""", unsafe_allow_html=True)
            except ZeroDivisionError:
                st.error("No model predictions were returned (empty predictions dict). "
                         "Ensure the Flask backend has all model .pkl files loaded.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")


# ── XAI ──────────────────────────────────────────────────────────────────────
def _feat_label(f: str) -> str:
    return {
        "age": "Age", "bp": "Blood Pressure", "sg": "Specific Gravity",
        "al": "Albumin", "su": "Sugar", "rbc": "RBC in Urine",
        "pc": "Pus Cells", "pcc": "Pus Cell Clumps", "ba": "Bacteria",
        "bgr": "Blood Glucose", "bu": "Blood Urea", "sc": "Serum Creatinine",
        "sod": "Sodium", "pot": "Potassium", "hemo": "Haemoglobin",
        "pcv": "Packed Cell Volume", "wc": "WBC Count", "rc": "RBC Count",
        "htn": "Hypertension", "dm": "Diabetes", "cad": "Coronary Artery Disease",
        "appet": "Appetite", "pe": "Pedal Oedema", "ane": "Anaemia",
    }.get(f, f)


def render_shap_explanation(medical: dict, model_name: str):
    t = get_t()
    with st.spinner(f"Computing SHAP explanations for {model_name}…"):
        try:
            resp = requests.post(EXPLAIN_URL, json=medical, timeout=40)
        except requests.exceptions.ConnectionError:
            st.markdown('<div class="alert-danger">⚠️ Flask backend not reachable.</div>',
                        unsafe_allow_html=True)
            return
        except Exception as e:
            st.warning(f"Explanation request failed: {e}")
            return

    if resp.status_code != 200:
        st.warning(f"Explanation API returned HTTP {resp.status_code}.")
        return
    data = resp.json()
    if data.get("status") != "success":
        st.warning(f"Explanation error: {data.get('message', 'unknown')}")
        return
    exp = data.get("explanations", {}).get(model_name)
    if not exp:
        st.info(f"No explanation available for {model_name}.")
        return
    if "error" in exp:
        st.warning(f"{model_name} explanation failed: {exp['error']}")
        return

    # ── Prepare data ────────────────────────────────────────────────────────
    all_items  = list(exp.items())                          # sorted by |shap| desc
    all_labels = [_feat_label(k) for k, _ in all_items]
    all_values = [v for _, v in all_items]

    risk_items = [(l, v) for l, v in zip(all_labels, all_values) if v > 0]
    prot_items = [(l, v) for l, v in zip(all_labels, all_values) if v < 0]
    top12_lbl  = all_labels[:12]
    top12_val  = all_values[:12]

    CLR_CKD  = "#C53030"
    CLR_OK   = "#276749"
    CLR_NEU  = "#718096"
    bar_colors = [CLR_CKD if v > 0 else CLR_OK for v in top12_val]

    # ── Clinical reference bands ─────────────────────────────────────────────
    CLINICAL_NORMS = {
        "Haemoglobin":        ("13–17 g/dl",  float(medical.get("hemo", 0))),
        "Serum Creatinine":   ("0.6–1.2 mg/dl", float(medical.get("sc", 0))),
        "Blood Urea":         ("7–25 mg/dl",  float(medical.get("bu", 0))),
        "Blood Glucose":      ("70–140 mg/dl", float(medical.get("bgr", 0))),
        "Sodium":             ("136–145 mEq/L", float(medical.get("sod", 0))),
        "Potassium":          ("3.5–5.0 mEq/L", float(medical.get("pot", 0))),
        "Specific Gravity":   ("1.010–1.025",  float(medical.get("sg", 0))),
        "Blood Pressure":     ("60–90 mm Hg",  float(medical.get("bp", 0))),
        "Packed Cell Volume": ("36–50 %",      float(str(medical.get("pcv","0")).replace("\\t","").strip() or 0)),
    }

    # ═══════════════════════════════════════════════════════════════════════
    # PLOT 1 — Feature Impact Bar Chart (top 12, sorted by magnitude)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("#### 📊 Plot 1 — Feature Impact (SHAP Values)")
    st.caption("Each bar shows how strongly a feature pushes the prediction toward CKD (red) or away from it (green). "
               "Bar length = magnitude of influence.")

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=top12_val, y=top12_lbl, orientation="h",
        marker=dict(
            color=bar_colors,
            line=dict(color="rgba(0,0,0,0.15)", width=0.5),
            opacity=0.9,
        ),
        text=[f"  {v:+.4f}" for v in top12_val],
        textposition="outside",
        textfont=dict(size=11, color=[CLR_CKD if v > 0 else CLR_OK for v in top12_val]),
        hovertemplate="<b>%{y}</b><br>SHAP: %{x:.5f}<br>%{customdata}<extra></extra>",
        customdata=["▲ Pushes toward CKD" if v > 0 else "▼ Protects against CKD" for v in top12_val],
    ))
    fig1.add_vline(x=0, line_width=2, line_color=t["border"])
    # Shade positive (risk) region
    if any(v > 0 for v in top12_val):
        fig1.add_vrect(x0=0, x1=max(top12_val)*1.3,
                       fillcolor="rgba(197,48,48,0.05)", line_width=0,
                       annotation_text="CKD Risk Zone", annotation_position="top right",
                       annotation_font=dict(color=CLR_CKD, size=10))
    fig1.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=t["text"], family="Inter", size=12),
        xaxis=dict(title="SHAP Value  (+ = increases CKD risk,  − = decreases CKD risk)",
                   gridcolor=t["border"], zeroline=False, tickformat=".3f"),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12), gridcolor="rgba(0,0,0,0)"),
        height=460, margin=dict(t=20, b=50, l=20, r=110),
    )
    st.plotly_chart(fig1, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════
    # PLOT 2 — Waterfall (cumulative SHAP)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("#### 🌊 Plot 2 — Waterfall: How Each Feature Shifts the Prediction")
    st.caption("Starting from the model baseline, each bar adds or subtracts from the prediction score. "
               "The final bar is the total SHAP contribution for this patient.")

    wf_labels = top12_lbl[:10]
    wf_values = top12_val[:10]
    cumsum     = 0.0
    measures   = []
    texts      = []
    for v in wf_values:
        measures.append("relative")
        texts.append(f"{v:+.4f}")
        cumsum += v
    measures.append("total")
    texts.append(f"Total: {cumsum:+.4f}")
    wf_labels_full = wf_labels + ["Net SHAP Score"]

    wf_colors = [CLR_CKD if v > 0 else CLR_OK for v in wf_values] + [CLR_CKD if cumsum > 0 else CLR_OK]

    fig2 = go.Figure(go.Waterfall(
        orientation="v",
        measure=measures,
        x=wf_labels_full,
        y=wf_values + [cumsum],
        text=texts,
        textposition="outside",
        connector=dict(line=dict(color=t["border"], width=1, dash="dot")),
        increasing=dict(marker=dict(color=CLR_CKD)),
        decreasing=dict(marker=dict(color=CLR_OK)),
        totals=dict(marker=dict(color=CLR_CKD if cumsum > 0 else CLR_OK)),
    ))
    fig2.add_hline(y=0, line_width=1.5, line_color=t["border"], line_dash="dash")
    fig2.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=t["text"], family="Inter", size=11),
        yaxis=dict(title="Cumulative SHAP contribution", gridcolor=t["border"], zeroline=False),
        xaxis=dict(tickangle=-30, gridcolor="rgba(0,0,0,0)"),
        height=420, margin=dict(t=20, b=100, l=20, r=20),
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════
    # PLOT 3 — Risk vs Protective split (donut)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("#### 🥧 Plot 3 — Risk vs Protective Balance")
    st.caption("Proportion of total absolute SHAP weight attributed to risk-increasing vs risk-reducing features.")

    col_donut, col_gauge = st.columns([1, 1])

    risk_sum = sum(v for _, v in risk_items)
    prot_sum = abs(sum(v for _, v in prot_items))
    total_abs = risk_sum + prot_sum if (risk_sum + prot_sum) > 0 else 1

    with col_donut:
        fig3 = go.Figure(go.Pie(
            labels=["Risk Features", "Protective Features"],
            values=[risk_sum, prot_sum],
            hole=0.55,
            marker=dict(colors=[CLR_CKD, CLR_OK],
                        line=dict(color="white", width=2)),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>Weight: %{value:.4f}<br>%{percent}<extra></extra>",
            pull=[0.04, 0],
        ))
        net_label = "⚠️ Risk" if risk_sum > prot_sum else "✅ Protected"
        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=t["text"], family="Inter", size=12),
            height=300, margin=dict(t=10, b=10, l=10, r=10),
            annotations=[dict(text=net_label, x=0.5, y=0.5, font_size=16,
                              font_color=CLR_CKD if risk_sum > prot_sum else CLR_OK,
                              showarrow=False)],
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15),
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ── PLOT 4 — Risk-o-meter gauge ─────────────────────────────────────────
    with col_gauge:
        st.markdown("#### 🎯 Plot 4 — Risk-o-Meter")
        risk_pct = round((risk_sum / total_abs) * 100, 1)
        fig4 = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=risk_pct,
            number=dict(suffix="%", font=dict(size=28, color=t["text"])),
            delta=dict(reference=50, increasing=dict(color=CLR_CKD),
                       decreasing=dict(color=CLR_OK)),
            gauge=dict(
                axis=dict(range=[0, 100], tickwidth=1, tickcolor=t["border"],
                          tickvals=[0, 25, 50, 75, 100],
                          ticktext=["Safe", "Low", "Mid", "High", "Critical"]),
                bar=dict(color=CLR_CKD if risk_pct > 50 else CLR_OK, thickness=0.25),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=1, bordercolor=t["border"],
                steps=[
                    dict(range=[0, 33],  color="rgba(39,103,73,0.15)"),
                    dict(range=[33, 66], color="rgba(214,158,46,0.15)"),
                    dict(range=[66, 100],color="rgba(197,48,48,0.15)"),
                ],
                threshold=dict(line=dict(color=CLR_NEU, width=3), thickness=0.8, value=50),
            ),
            title=dict(text="% Feature Weight<br>driving CKD Risk", font=dict(size=13, color=t["text"])),
        ))
        fig4.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=t["text"], family="Inter"),
            height=300, margin=dict(t=30, b=10, l=30, r=30),
        )
        st.plotly_chart(fig4, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════
    # PLOT 5 — Clinical Value vs Normal Range (scatter)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("#### 🩺 Plot 5 — Patient Values vs Clinical Normal Ranges")
    st.caption("Each point shows the patient's measured value. Green band = normal clinical range. "
               "Points outside the band are potential concern areas.")

    norm_rows = []
    for feat_label, (norm_str, patient_val) in CLINICAL_NORMS.items():
        feat_key = next((k for k, _ in all_items if _feat_label(k) == feat_label), None)
        shap_v = exp.get(feat_key, 0) if feat_key else 0
        norm_rows.append(dict(Feature=feat_label, Patient=patient_val,
                              Norm=norm_str, SHAP=shap_v))

    if norm_rows:
        NORM_RANGES = {
            "Haemoglobin": (13.0, 17.0),
            "Serum Creatinine": (0.6, 1.2),
            "Blood Urea": (7.0, 25.0),
            "Blood Glucose": (70.0, 140.0),
            "Sodium": (136.0, 145.0),
            "Potassium": (3.5, 5.0),
            "Specific Gravity": (1.010, 1.025),
            "Blood Pressure": (60.0, 90.0),
            "Packed Cell Volume": (36.0, 50.0),
        }
        fig5 = go.Figure()
        features_list = [r["Feature"] for r in norm_rows]
        patient_vals  = [r["Patient"]  for r in norm_rows]

        # Normalise each value to % of normal range midpoint for comparability
        norm_pct, status_color, hover_texts = [], [], []
        for r in norm_rows:
            lo, hi = NORM_RANGES.get(r["Feature"], (r["Patient"], r["Patient"]))
            mid   = (lo + hi) / 2
            rng   = (hi - lo) / 2 if hi != lo else 1
            pct   = ((r["Patient"] - mid) / rng) * 100  # 0 = mid-normal
            norm_pct.append(pct)
            outside = r["Patient"] < lo or r["Patient"] > hi
            status_color.append(CLR_CKD if (outside and r["SHAP"] > 0) else
                                 CLR_OK  if not outside else CLR_NEU)
            direction = "above" if r["Patient"] > hi else ("below" if r["Patient"] < lo else "within")
            hover_texts.append(
                f"<b>{r['Feature']}</b><br>"
                f"Patient: {r['Patient']}<br>"
                f"Normal: {r['Norm']}<br>"
                f"Status: {direction} range<br>"
                f"SHAP contribution: {r['SHAP']:+.4f}"
            )

        fig5.add_trace(go.Bar(
            x=features_list, y=norm_pct,
            marker=dict(color=status_color, opacity=0.8,
                        line=dict(color="rgba(0,0,0,0.1)", width=0.5)),
            text=[f"{v:.1f}%" for v in norm_pct],
            textposition="outside",
            hovertext=hover_texts, hoverinfo="text",
        ))
        fig5.add_hrect(y0=-100, y1=100, fillcolor="rgba(39,103,73,0.08)",
                       line_width=0, annotation_text="Normal Range",
                       annotation_position="top left",
                       annotation_font=dict(color=CLR_OK, size=10))
        fig5.add_hline(y=0,    line_width=1.5, line_color=CLR_OK,  line_dash="dash")
        fig5.add_hline(y=100,  line_width=1,   line_color=CLR_CKD, line_dash="dot")
        fig5.add_hline(y=-100, line_width=1,   line_color=CLR_CKD, line_dash="dot")
        fig5.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=t["text"], family="Inter", size=11),
            yaxis=dict(title="Deviation from Normal Range Mid-point (%)",
                       gridcolor=t["border"], zeroline=False),
            xaxis=dict(tickangle=-25, gridcolor="rgba(0,0,0,0)"),
            height=380, margin=dict(t=20, b=100, l=20, r=20),
        )
        st.plotly_chart(fig5, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════
    # Clinical Narrative
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("#### 📋 Clinical Interpretation")
    top_risk = risk_items[:4]
    top_prot = prot_items[:3]

    narrative_html = "<div style='font-size:0.9rem;line-height:1.9;'>"
    if top_risk:
        narrative_html += "<p><strong>🔴 Top Risk Drivers:</strong></p><ul>"
        for label, v in top_risk:
            norm_info = CLINICAL_NORMS.get(label, ("", None))
            norm_text = f" (Normal: {norm_info[0]})" if norm_info[0] else ""
            narrative_html += (f"<li><strong>{label}</strong>{norm_text} — "
                               f"SHAP <span style='color:{CLR_CKD}'>{v:+.4f}</span>: "
                               f"This feature is pushing the model <em>toward CKD</em>. "
                               f"The higher this value, the greater the kidney stress signal.</li>")
        narrative_html += "</ul>"

    if top_prot:
        narrative_html += "<p><strong>🟢 Top Protective Factors:</strong></p><ul>"
        for label, v in top_prot:
            norm_info = CLINICAL_NORMS.get(label, ("", None))
            norm_text = f" (Normal: {norm_info[0]})" if norm_info[0] else ""
            narrative_html += (f"<li><strong>{label}</strong>{norm_text} — "
                               f"SHAP <span style='color:{CLR_OK}'>{v:+.4f}</span>: "
                               f"This feature is <em>reducing</em> CKD likelihood in this prediction.</li>")
        narrative_html += "</ul>"

    net = sum(all_values)
    verdict_color = CLR_CKD if net > 0 else CLR_OK
    verdict_text  = "net CKD risk" if net > 0 else "net protective effect"
    narrative_html += (f"<p><strong>📌 Net SHAP Score: "
                       f"<span style='color:{verdict_color}'>{net:+.4f}</span></strong> — "
                       f"The combined SHAP signal shows a <strong>{verdict_text}</strong> "
                       f"for this patient according to the <em>{model_name}</em> model.</p>")
    narrative_html += "</div>"
    st.markdown(narrative_html, unsafe_allow_html=True)

    st.caption(
        "🟥 Red = feature increases CKD risk &nbsp;|&nbsp; "
        "🟩 Green = feature decreases CKD risk &nbsp;|&nbsp; "
        "Bar length = strength of influence &nbsp;|&nbsp; "
        f"Model: {model_name}"
    )



# ── NURSE IMMEDIATE-ACTION PROTOCOL ──────────────────────────────────────────
def nurse_actions_section(is_ckd: bool, medical: dict):
    """Display structured immediate-action checklist for nurses."""
    t = get_t()

    if is_ckd:
        st.markdown("""
        <div class="action-card action-card-urgent">
            <div class="action-card-title">🚨 Immediate Actions — CKD Detected</div>
        </div>""", unsafe_allow_html=True)

        steps_urgent = [
            ("Notify the attending physician immediately and document the time of notification.", "🔴"),
            ("Ensure the patient remains calm and seat them comfortably. Monitor vital signs (BP, pulse, temperature).", "🩺"),
            ("Prepare request forms for confirmatory tests: serum creatinine, GFR, urine albumin-to-creatinine ratio.", "🧪"),
            ("Check and document current medications — NSAIDs, ACE inhibitors, metformin may need dose review.", "💊"),
            ("Restrict fluid intake as per physician order if oedema is present.", "💧"),
            ("Schedule urgent nephrology referral appointment within 24–48 hours.", "📅"),
        ]
        for i, (step, icon) in enumerate(steps_urgent, 1):
            st.markdown(f"""
            <div class="action-step">
                <div class="action-step-num">{i}</div>
                <div>{icon} {step}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="action-card action-card-warn">
            <div class="action-card-title">⚠️ Patient Monitoring Checklist</div>
        </div>""", unsafe_allow_html=True)

        checks = [
            "Record weight daily (fluid retention monitoring)",
            "Monitor urine output every 4–6 hours",
            "Blood pressure check every 2–4 hours",
            "Reassess for signs of confusion, breathlessness, or chest pain",
            "Educate patient on low-sodium, low-potassium diet",
            "Confirm patient has emergency contact details on file",
        ]
        for c in checks:
            st.checkbox(c, key=f"nurse_check_{c[:20]}")

        # Flag high-risk markers from medical params
        flags = []
        if float(medical.get("sc", 0)) > 2.0:
            flags.append(f"⚠️ Serum Creatinine elevated: **{medical.get('sc')} mg/dl** (normal ≤ 1.2)")
        if float(medical.get("bu", 0)) > 50:
            flags.append(f"⚠️ Blood Urea elevated: **{medical.get('bu')} mg/dl** (normal ≤ 40)")
        if float(medical.get("hemo", 15)) < 9:
            flags.append(f"⚠️ Haemoglobin low: **{medical.get('hemo')} g/dl** — possible renal anaemia")
        if medical.get("htn") == "yes":
            flags.append("⚠️ Hypertension present — strict BP monitoring required")
        if medical.get("pe") == "yes":
            flags.append("⚠️ Pedal oedema noted — record and report fluid balance")

        if flags:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
            <div class="action-card action-card-urgent">
                <div class="action-card-title">🔴 High-Risk Markers Detected</div>
            </div>""", unsafe_allow_html=True)
            for f in flags:
                st.markdown(f"- {f}")

    else:
        st.markdown("""
        <div class="action-card action-card-ok">
            <div class="action-card-title">✅ No CKD Detected — Follow-Up Protocol</div>
        </div>""", unsafe_allow_html=True)

        steps_ok = [
            ("Inform the patient of the reassuring result and explain it does not eliminate future risk.", "✅"),
            ("Advise annual kidney function check if any risk factors present (diabetes, hypertension, family history).", "📅"),
            ("Encourage 1.5–2 L fluid intake per day and low-sodium diet.", "💧"),
            ("Recommend regular BP and blood glucose monitoring at home.", "🩺"),
            ("Document result in patient file and notify attending physician.", "📋"),
            ("Provide patient education leaflet on CKD prevention.", "📄"),
        ]
        for i, (step, icon) in enumerate(steps_ok, 1):
            st.markdown(f"""
            <div class="action-step">
                <div class="action-step-num">{i}</div>
                <div>{icon} {step}</div>
            </div>""", unsafe_allow_html=True)


# ── RESULTS ───────────────────────────────────────────────────────────────────
def results_page():
    navigation_bar()
    page_banner("CKD Assessment Report", "Step 3 – Prediction Results", "📊")
    step_pills(2)
    patient_strip()

    role    = get_role()
    is_doc  = is_verified_doctor()   # True for admin or doctor with "Dr." prefix

    result = st.session_state.prediction_result
    if not (result and result.get("status") == "success"):
        st.error("No results available. Complete a medical assessment first.")
        if st.button("← Back to Medical Parameters"):
            st.session_state.current_page = "medical_parameters"; st.rerun()
        return

    predictions = result.get("predictions", {})
    total   = len(predictions)

    if total == 0:
        st.markdown(
            '<div class="alert-danger">⚠️ No model predictions found in this result. '
            'Please run a new assessment.</div>',
            unsafe_allow_html=True)
        if st.button("← Run New Assessment"):
            st.session_state.update(current_page="medical_parameters",
                                    prediction_result=None)
            st.rerun()
        return

    ckd_cnt = sum(1 for p in predictions.values() if p.get("prediction") == 1)
    is_ckd  = ckd_cnt > total / 2
    conf    = round((max(ckd_cnt, total - ckd_cnt) / total) * 100, 2)

    # ── Ensemble verdict (visible to all roles) ───────────────────────────────
    if is_ckd:
        st.markdown(f"""
        <div class="ensemble-ckd">
            <div style="font-size:2.2rem;">⚠️</div>
            <div class="ens-verdict">CHRONIC KIDNEY DISEASE DETECTED</div>
            <div class="ens-sub">Ensemble confidence: <strong>{conf}%</strong>
             &nbsp;|&nbsp; {ckd_cnt}/{total} models agree</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("""<div class="alert-danger">
            <strong>⚠️ Clinical Recommendation:</strong> Immediate nephrology referral advised.
            Confirm with GFR staging and early intervention planning.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="ensemble-ok">
            <div style="font-size:2.2rem;">✅</div>
            <div class="ens-verdict">NO CKD DETECTED</div>
            <div class="ens-sub">Ensemble confidence: <strong>{conf}%</strong>
             &nbsp;|&nbsp; {total - ckd_cnt}/{total} models agree</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("""<div class="alert-success">
            <strong>✅ Clinical Note:</strong> No CKD indicators detected.
            Encourage annual renal function tests if high-risk profile.
        </div>""", unsafe_allow_html=True)

    # ── NURSE VIEW: action protocol only, no model details ───────────────────
    if role == "nurse":
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div class="restricted-banner">🔒 <strong>Nurse View:</strong> '
            'Detailed model analysis and clinical parameters are visible to Doctors and Admins only. '
            'Your action checklist is below.</div>',
            unsafe_allow_html=True)
        nurse_actions_section(is_ckd, st.session_state.medical_data)
        st.markdown("<br>", unsafe_allow_html=True)
        r1, r2, r3 = st.columns(3)
        with r1:
            if st.button("🔄 Reassess Same Patient", use_container_width=True, key="nurse_reassess"):
                st.session_state.update(medical_data={}, prediction_result=None,
                                        assessment_source="lookup",
                                        current_page="medical_parameters")
                st.rerun()
        with r2:
            if st.button("📊 Dashboard", use_container_width=True):
                st.session_state.current_page = "dashboard"; st.rerun()
        with r3:
            if st.button("🔍 Patient History", use_container_width=True):
                st.session_state.current_page = "patient_lookup"; st.rerun()
        return

    # ── DOCTOR (no Dr. prefix): verdict + confidence only ────────────────────
    if role == "doctor" and not is_doc:
        st.markdown(
            '<div class="restricted-banner">ℹ️ <strong>Access Notice:</strong> '
            'Full model-level breakdown is available only to verified physicians (name prefixed "Dr."). '
            'Contact admin to update your profile.</div>',
            unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            if st.button("🔄 Reassess Same Patient", use_container_width=True, key="doc_unverified_reassess"):
                st.session_state.update(medical_data={}, prediction_result=None,
                                        assessment_source="lookup",
                                        current_page="medical_parameters")
                st.rerun()
        with r2:
            if st.button("🔄 New Assessment", use_container_width=True):
                st.session_state.update(current_page="patient_details",
                                        patient_data={}, medical_data={}, prediction_result=None)
                st.rerun()
        with r3:
            if st.button("📊 Dashboard", use_container_width=True):
                st.session_state.current_page = "dashboard"; st.rerun()
        with r4:
            if st.button("🔍 Patient History", use_container_width=True):
                st.session_state.current_page = "patient_lookup"; st.rerun()
        return

    # ── FULL VIEW: admin or verified doctor (Dr. prefix) ─────────────────────
    # Model grid
    st.markdown('<div class="card"><div class="card-title">🤖 Individual Model Results</div>',
                unsafe_allow_html=True)
    cols = st.columns(3)
    for idx, (name, pred) in enumerate(predictions.items()):
        pos    = pred.get("prediction") == 1
        conf_m = pred.get("confidence") or 0
        tag    = '<span class="tag tag-ckd">CKD +ve</span>' if pos else '<span class="tag tag-ok">No CKD</span>'
        fill   = "conf-fill-ckd" if pos else "conf-fill-ok"
        with cols[idx % 3]:
            st.markdown(f"""
            <div class="model-card">
                <div class="model-name">{name}</div>
                {tag}
                <div class="conf-track">
                    <div class="{fill}" style="width:{conf_m}%"></div>
                </div>
                <small style="font-size:0.78rem;color:gray;">Confidence: {conf_m}%</small>
            </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── XAI: SHAP explanation (admin + verified doctor only) ───────────
    st.markdown(
        '<div class="card"><div class="card-title">'
        '🔍 Why this prediction? — Explainable AI (SHAP Feature Impact)</div>',
        unsafe_allow_html=True)
    xai_col, info_col = st.columns([3, 1])
    with xai_col:
        xai_model = st.selectbox(
            "Explain using model:",
            ["Random Forest", "Gradient Boosting", "XGBoost",
             "CatBoost", "Decision Tree", "Logistic Regression",
             "SVM", "K-Nearest Neighbors", "Naive Bayes"],
            index=0, key="xai_model_select"
        )
    with info_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📊 Generate", key="xai_run_btn", use_container_width=True):
            st.session_state["xai_generate"] = True

    if st.session_state.get("xai_generate"):
        render_shap_explanation(st.session_state.medical_data, xai_model)
    else:
        t = get_t()
        st.markdown(
            f'<div style="text-align:center;padding:2rem;color:{t["text_muted"]};'
            f'font-size:0.9rem;">'
            f'Select a model and click <strong>📊 Generate</strong> to compute '
            f'SHAP feature-importance values for this prediction.</div>',
            unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Summary table
    med = st.session_state.medical_data
    st.markdown('<div class="card"><div class="card-title">📋 Submitted Parameters</div>',
                unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("**Urine Analysis**")
        for k, v in [("Spec. Gravity", med.get("sg")), ("Albumin", med.get("al")),
                     ("Sugar", med.get("su")), ("RBC", med.get("rbc"))]:
            st.write(f"{k}: {v}")
    with col2:
        st.markdown("**Biochemistry**")
        for k, v in [("BP", f"{med.get('bp')} mm Hg"), ("Glucose", f"{med.get('bgr')} mg/dl"),
                     ("Urea", f"{med.get('bu')} mg/dl"), ("Creatinine", f"{med.get('sc')} mg/dl")]:
            st.write(f"{k}: {v}")
    with col3:
        st.markdown("**Electrolytes / Hb**")
        for k, v in [("Sodium", f"{med.get('sod')} mEq/L"), ("Potassium", f"{med.get('pot')} mEq/L"),
                     ("Haemoglobin", f"{med.get('hemo')} g/dl"), ("PCV", f"{med.get('pcv')}%")]:
            st.write(f"{k}: {v}")
    with col4:
        st.markdown("**Medical History**")
        for k, v in [("Hypertension", med.get("htn")), ("Diabetes", med.get("dm")),
                     ("CAD", med.get("cad")), ("Anaemia", med.get("ane"))]:
            st.write(f"{k}: {str(v).title()}")
    st.markdown("</div>", unsafe_allow_html=True)

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button("🔄 Reassess Same Patient", use_container_width=True, key="full_reassess"):
            st.session_state.update(medical_data={}, prediction_result=None,
                                    assessment_source="lookup",
                                    current_page="medical_parameters")
            st.rerun()
    with a2:
        if st.button("🔄 New Patient Assessment", use_container_width=True):
            st.session_state.update(current_page="patient_details",
                                    patient_data={}, medical_data={}, prediction_result=None,
                                    assessment_source="new")
            st.rerun()
    with a3:
        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state.current_page = "dashboard"; st.rerun()
    with a4:
        if st.button("🔍 Patient History", use_container_width=True):
            st.session_state.current_page = "patient_lookup"; st.rerun()


# ── PATIENT LOOKUP ────────────────────────────────────────────────────────────
def patient_lookup_page():
    navigation_bar()
    role = get_role()
    page_banner("Patient History", "Search past assessments", "🔍")

    # ── Search ────────────────────────────────────────────────────────────────
    pid = st.text_input("Enter Patient ID", placeholder="PAT-2026-001")
    if st.button("Search"):
        if pid:
            patient = get_patient(pid)
            if patient:
                st.markdown(f"""
                <div class="patient-strip">
                    <strong>{patient['first_name']} {patient['last_name']}</strong> &nbsp;|&nbsp;
                    {patient['patient_id']} &nbsp;|&nbsp; Age {patient['age']} &nbsp;|&nbsp;
                    {patient.get('physician','–')}
                </div>""", unsafe_allow_html=True)

                # Admin: inline edit & delete
                if role == "admin":
                    with st.expander("✏️ Edit Patient Details"):
                        with st.form(f"edit_patient_{pid}"):
                            ec1, ec2, ec3 = st.columns(3)
                            with ec1:
                                e_fn = st.text_input("First Name", value=patient.get("first_name",""))
                                e_age = st.number_input("Age", 1, 120, int(patient.get("age",45)))
                                e_phone = st.text_input("Phone", value=patient.get("phone",""))
                            with ec2:
                                e_ln = st.text_input("Last Name", value=patient.get("last_name",""))
                                e_gender = st.selectbox("Gender", ["Male","Female","Other"],
                                    index=["Male","Female","Other"].index(patient.get("gender","Male")) if patient.get("gender") in ["Male","Female","Other"] else 0)
                                e_email = st.text_input("Email", value=patient.get("email",""))
                            with ec3:
                                e_bg = st.selectbox("Blood Group", ["--","A+","A-","B+","B-","AB+","AB-","O+","O-","Unknown"],
                                    index=["--","A+","A-","B+","B-","AB+","AB-","O+","O-","Unknown"].index(patient.get("blood_group","--")) if patient.get("blood_group") in ["--","A+","A-","B+","B-","AB+","AB-","O+","O-","Unknown"] else 0)
                                e_phys = st.text_input("Physician", value=patient.get("physician",""))
                                e_dept = st.selectbox("Department", ["Nephrology","Internal Medicine","General Practice","Urology","Emergency Medicine","Endocrinology","Other"])
                            e_addr = st.text_area("Address", value=patient.get("address",""), height=70)
                            ec_city, ec_state = st.columns(2)
                            with ec_city: e_city = st.text_input("City", value=patient.get("city",""))
                            with ec_state: e_state = st.text_input("State", value=patient.get("state",""))
                            if st.form_submit_button("💾 Save Changes", use_container_width=True):
                                ok, msg = update_patient(pid, dict(
                                    first_name=e_fn, last_name=e_ln, age=e_age, gender=e_gender,
                                    blood_group=e_bg, phone=e_phone, email=e_email,
                                    address=e_addr, city=e_city, state=e_state,
                                    physician=e_phys, department=e_dept))
                                (st.success if ok else st.error)(msg)

                    st.markdown('<div class="crud-danger">', unsafe_allow_html=True)
                    if st.button(f"🗑️ Delete Patient '{pid}' and all records",
                                 key=f"del_pat_{pid}"):
                        st.session_state[f"confirm_del_{pid}"] = True
                    st.markdown("</div>", unsafe_allow_html=True)
                    if st.session_state.get(f"confirm_del_{pid}"):
                        st.warning(f"⚠️ This will permanently delete **{pid}** and all predictions. Confirm?")
                        cd1, cd2 = st.columns(2)
                        with cd1:
                            if st.button("✅ Yes, Delete", key=f"confirm_yes_{pid}"):
                                ok, msg = delete_patient(pid)
                                (st.success if ok else st.error)(msg)
                                st.session_state.pop(f"confirm_del_{pid}", None)
                                time.sleep(0.5); st.rerun()
                        with cd2:
                            if st.button("❌ Cancel", key=f"confirm_no_{pid}"):
                                st.session_state.pop(f"confirm_del_{pid}", None)
                                st.rerun()

                preds = get_patient_predictions(pid)
                if preds:
                    for pr in preds:
                        ckd = pr.get("ckd_detected") == 1
                        css = "ensemble-ckd" if ckd else "ensemble-ok"
                        # Expandable: show per-model breakdown from stored JSON
                        with st.expander(
                            f"{'⚠️ CKD' if ckd else '✅ No CKD'}  —  "
                            f"{pr.get('ensemble_conf')}% confidence  |  "
                            f"{pr.get('prediction_date')}  |  By: {pr.get('performed_by')}"
                        ):
                            st.markdown(
                                f'<div class="{css}" style="padding:0.8rem 1.2rem;border-radius:8px;'
                                f'margin-bottom:0.6rem"><strong>{"⚠️ CKD Detected" if ckd else "✅ No CKD"}</strong>'
                                f' &nbsp; Ensemble confidence: <strong>{pr.get("ensemble_conf")}%</strong></div>',
                                unsafe_allow_html=True)
                            model_results = pr.get("model_results", {})
                            if isinstance(model_results, dict) and model_results:
                                cols = st.columns(3)
                                for i, (mname, mdata) in enumerate(model_results.items()):
                                    pos = mdata.get("prediction") == 1
                                    conf_m = mdata.get("confidence") or 0
                                    tag = '❌ CKD' if pos else '✅ No CKD'
                                    with cols[i % 3]:
                                        st.markdown(
                                            f"**{mname}** &mdash; {tag}  "
                                            f"({conf_m}%)")
                            med = pr.get("medical_params", {})
                            if isinstance(med, dict) and med:
                                with st.expander("📋 Parameters used in this assessment"):
                                    mc1, mc2, mc3 = st.columns(3)
                                    with mc1:
                                        st.write(f"BP: {med.get('bp')} mm Hg")
                                        st.write(f"Glucose: {med.get('bgr')} mg/dl")
                                        st.write(f"Urea: {med.get('bu')} mg/dl")
                                        st.write(f"Creatinine: {med.get('sc')} mg/dl")
                                    with mc2:
                                        st.write(f"Sodium: {med.get('sod')} mEq/L")
                                        st.write(f"Potassium: {med.get('pot')} mEq/L")
                                        st.write(f"Haemoglobin: {med.get('hemo')} g/dl")
                                        st.write(f"PCV: {med.get('pcv')}%")
                                    with mc3:
                                        st.write(f"Hypertension: {med.get('htn')}")
                                        st.write(f"Diabetes: {med.get('dm')}")
                                        st.write(f"Anaemia: {med.get('ane')}")
                                        st.write(f"Albumin: {med.get('al')}")
                else:
                    st.info("No predictions recorded for this patient.")

                # ── Run new assessment for this patient ───────────────────────
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(
                    f"🔄 Run New Assessment for {patient['first_name']} {patient['last_name']}",
                    key=f"reassess_{pid}",
                    use_container_width=True,
                ):
                    st.session_state.patient_data = dict(patient)
                    st.session_state.medical_data = {}
                    st.session_state.prediction_result = None
                    st.session_state.assessment_source = "lookup"
                    st.session_state.current_page = "medical_parameters"
                    st.rerun()
            else:
                st.warning(f"No patient found with ID '{pid}'.")

    # ── Patient table ─────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">👥 All Registered Patients</div>',
                unsafe_allow_html=True)
    patients = get_all_patients()
    if patients:
        df = pd.DataFrame(patients)
        df.columns = ["Patient ID","First Name","Last Name","Age","Gender","Physician","Registered"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Quick-assess: type/pick a patient ID and jump straight to medical params
        st.markdown("**Run new assessment for a listed patient:**")
        qa_c1, qa_c2 = st.columns([3, 1])
        with qa_c1:
            qa_pid = st.selectbox(
                "Select Patient",
                options=[p["patient_id"] for p in patients],
                format_func=lambda pid: next(
                    (f"{p['patient_id']} — {p['first_name']} {p['last_name']} (Age {p['age']})"
                     for p in patients if p["patient_id"] == pid), pid),
                key="qa_pid_select",
                label_visibility="collapsed",
            )
        with qa_c2:
            if st.button("🔄 Reassess", key="qa_assess_btn", use_container_width=True):
                full_patient = get_patient(qa_pid)
                if full_patient:
                    st.session_state.patient_data = dict(full_patient)
                    st.session_state.medical_data = {}
                    st.session_state.prediction_result = None
                    st.session_state.assessment_source = "lookup"
                    st.session_state.current_page = "medical_parameters"
                    st.rerun()

        # Admin gets a quick-delete column below the table
        if role == "admin":
            st.markdown("**Quick-delete patient by ID:**")
            qd_col1, qd_col2 = st.columns([3, 1])
            with qd_col1:
                del_pid = st.text_input("Patient ID to delete", key="quick_del_pid",
                                        placeholder="PAT-2026-001")
            with qd_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown('<div class="crud-danger">', unsafe_allow_html=True)
                if st.button("🗑️ Delete", key="quick_del_btn", use_container_width=True):
                    if del_pid:
                        ok, msg = delete_patient(del_pid)
                        (st.success if ok else st.error)(msg)
                        if ok: time.sleep(0.4); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No patients registered yet.")
    st.markdown("</div>", unsafe_allow_html=True)


# ── USER MANAGEMENT ───────────────────────────────────────────────────────────
def user_management_page():
    navigation_bar()
    page_banner("User Management", "Admin: manage clinical accounts", "👥")

    if not require_role("admin"):
        return

    users = get_all_users()

    # ── Current users table ───────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">👥 Current Users</div>',
                unsafe_allow_html=True)
    if users:
        df = pd.DataFrame(users)[["id","username","full_name","role","email","created_at"]]
        df.columns = ["ID","Username","Full Name","Role","Email","Created"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Edit user ─────────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">✏️ Edit User</div>',
                unsafe_allow_html=True)
    usernames = [u["username"] for u in users if u["username"] != st.session_state.username]
    if usernames:
        sel_user = st.selectbox("Select user to edit", usernames, key="edit_user_select")
        sel_data = next((u for u in users if u["username"] == sel_user), {})
        with st.form("edit_user_form"):
            eu1, eu2 = st.columns(2)
            with eu1:
                eu_fn   = st.text_input("Full Name",  value=sel_data.get("full_name",""))
                eu_email= st.text_input("Email",      value=sel_data.get("email",""))
            with eu2:
                roles = ["doctor","nurse","admin"]
                eu_role = st.selectbox("Role", roles,
                    index=roles.index(sel_data.get("role","doctor")) if sel_data.get("role") in roles else 0)
                st.markdown(
                    "<small>⚠️ Setting <strong>Dr.</strong> in Full Name grants full analysis view to that doctor.</small>",
                    unsafe_allow_html=True)
            if st.form_submit_button("💾 Update User", use_container_width=True):
                ok, msg = update_user(sel_user, eu_fn, eu_role, eu_email)
                (st.success if ok else st.error)(msg)
                if ok: time.sleep(0.4); st.rerun()
    else:
        st.info("No other users to edit.")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Create user ───────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">➕ Create User</div>',
                unsafe_allow_html=True)
    with st.form("add_user_form"):
        c1, c2 = st.columns(2)
        with c1:
            nu  = st.text_input("Username")
            np_ = st.text_input("Password", type="password")
            nf  = st.text_input("Full Name",
                                 help="Prefix with 'Dr.' to grant full analysis access for Doctor role")
        with c2:
            nr = st.selectbox("Role", ["doctor","nurse","admin"])
            ne = st.text_input("Email")
            st.markdown(
                "<small>Doctor accounts must have full name starting with <strong>Dr.</strong> "
                "to access detailed model analysis.</small>",
                unsafe_allow_html=True)
        if st.form_submit_button("Create User", use_container_width=True):
            if nu and np_:
                ok, msg = add_user(nu, np_, nf, nr, ne)
                (st.success if ok else st.error)(msg)
                if ok: time.sleep(0.4); st.rerun()
            else:
                st.warning("Username and password required.")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Delete user ───────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">🗑️ Delete User</div>',
                unsafe_allow_html=True)
    del_usernames = [u["username"] for u in users if u["username"] != st.session_state.username]
    if del_usernames:
        del1, del2 = st.columns([3, 1])
        with del1:
            del_sel = st.selectbox("Select user to delete", del_usernames, key="del_user_select")
            del_info = next((u for u in users if u["username"] == del_sel), {})
            role_badge_cls = f"role-{del_info.get('role','nurse')}"
            st.markdown(
                f"<small>{del_info.get('full_name','')} &nbsp;"
                f'<span class="role-badge {role_badge_cls}">{del_info.get("role","")}</span></small>',
                unsafe_allow_html=True)
        with del2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="crud-danger">', unsafe_allow_html=True)
            if st.button("🗑️ Delete", key="del_user_btn", use_container_width=True):
                st.session_state["confirm_del_user"] = del_sel
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.get("confirm_del_user") == del_sel:
            st.warning(f"⚠️ Permanently delete user **{del_sel}**?")
            ca, cb = st.columns(2)
            with ca:
                if st.button("✅ Confirm Delete", key="confirm_del_user_yes"):
                    ok, msg = delete_user(del_sel)
                    (st.success if ok else st.error)(msg)
                    st.session_state.pop("confirm_del_user", None)
                    if ok: time.sleep(0.4); st.rerun()
            with cb:
                if st.button("❌ Cancel", key="confirm_del_user_no"):
                    st.session_state.pop("confirm_del_user", None)
                    st.rerun()
    else:
        st.info("No other users to delete.")
    st.markdown("</div>", unsafe_allow_html=True)


# ── CHANGE PASSWORD ───────────────────────────────────────────────────────────
def change_password_page():
    navigation_bar()
    page_banner("Change Password", "Update your access credential", "🔒")

    _, col, _ = st.columns([2,3,2])
    with col:
        st.markdown('<div class="card"><div class="card-title">🔒 Change Password</div>',
                    unsafe_allow_html=True)
        with st.form("chpwd_form"):
            old = st.text_input("Current Password", type="password")
            new = st.text_input("New Password",     type="password")
            cfm = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Update Password", use_container_width=True):
                if new != cfm:
                    st.error("Passwords do not match.")
                elif len(new) < 6:
                    st.error("Minimum 6 characters required.")
                else:
                    ok, msg = change_password(st.session_state.username, old, new)
                    (st.success if ok else st.error)(msg)
        st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ROUTER
# ─────────────────────────────────────────────────────────────────────────────
def main():
    init_session()
    inject_css()

    authenticated = st.session_state.authenticated
    page = st.session_state.current_page

    if not authenticated:
        # Public pages — no sidebar
        if page == "login":
            login_page()
        else:
            landing_page()
    else:
        # Authenticated — render sidebar + page content
        render_sidebar()
        PAGE_MAP = {
            "dashboard":          dashboard_page,
            "patient_details":    patient_details_page,
            "medical_parameters": medical_parameters_page,
            "results":            results_page,
            "patient_lookup":     patient_lookup_page,
            "user_management":    user_management_page,
            "change_password":    change_password_page,
        }
        PAGE_MAP.get(page, dashboard_page)()

    st.markdown("""
    <div class="clinical-footer">
        🩺 NephroScan – AI-Powered CKD Clinical Decision Support &nbsp;|&nbsp;
        For clinical decision support only. Always confirm with a qualified nephrologist.<br>
        © 2026 Healthcare AI Solutions
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
