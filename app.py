import os
import io
import time
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import importlib
import database
import timetable_generator
import utils

try:
    importlib.reload(database)
    importlib.reload(timetable_generator)
    importlib.reload(utils)
except Exception:
    pass

from database import DatabaseManager
from timetable_generator import TimetableOptimizer, parse_natural_language_adjustment
from utils import (
    ConflictValidator,
    build_timetable_grid,
    build_department_cohort_grid,
    compare_timetable_versions,
    export_timetable_pdf,
    export_timetable_excel,
    export_timetable_txt,
    DAYS_LIST,
    PERIODS_LIST,
    PERIOD_TIMES
)

# =====================================================================
# STREAMLIT PAGE CONFIG & MODERN ACADEMIC STYLING
# =====================================================================
st.set_page_config(
    page_title="AI Timetable Generation System | NEP 2020",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');

    /* =====================================================================
       1. GLOBAL THEME, TYPOGRAPHY & RESPONSIVE LAYOUT CONTAINER
       ===================================================================== */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', sans-serif !important;
        background-color: #ffffff !important;
        color: #0f172a !important;
    }

    [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
    }

    [data-testid="stHeader"] {
        background-color: transparent !important;
    }

    /* Streamlit block container: Remove default 96px top / 160px bottom padding */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 1280px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.75rem !important;
            padding-bottom: 1.75rem !important;
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }
    }

    /* Headings */
    h1:not(.hero-main-title), h2, h3, h4, h5, h6 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: #0f172a !important;
        letter-spacing: -0.025em !important;
    }

    p, span, label {
        font-family: 'Inter', sans-serif;
        color: #475569;
    }

    /* Sidebar clean light-mode */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #f1f5f9 !important;
    }

    /* =====================================================================
       2. SELF-CONTAINED ROYAL-BLUE RECTANGULAR HERO BOX (RESPONSIVE BANNER)
       ===================================================================== */
    .royal-hero-box {
        position: relative !important;
        width: 100% !important;
        box-sizing: border-box !important;
        border-radius: 18px !important;
        background: linear-gradient(135deg, #0f2557 0%, #1d4ed8 55%, #2563eb 100%) !important;
        box-shadow: 0 12px 36px -10px rgba(15, 37, 87, 0.35), 0 4px 14px rgba(15, 23, 42, 0.06) !important;
        padding: 32px 30px 26px 30px !important;
        margin: 0 0 28px 0 !important;
        overflow: hidden !important;
        text-align: center !important;
        color: #ffffff !important;
        will-change: transform, opacity;
        transform-origin: center top;
        transition: transform 0.08s ease-out, opacity 0.08s ease-out;
        animation: heroFloat 0.65s cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
    }

    @keyframes heroFloat {
        0% {
            opacity: 0;
            transform: translateY(14px);
        }
        100% {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Dotted Timetable Grid Animation */
    .royal-hero-box::before {
        content: "";
        position: absolute;
        top: -60%;
        left: -60%;
        width: 220%;
        height: 220%;
        background-image: radial-gradient(circle, rgba(255, 255, 255, 0.22) 1.5px, transparent 1.5px) !important;
        background-size: 26px 26px !important;
        pointer-events: none !important;
        animation: gridDrift 18s linear infinite !important;
    }

    @keyframes gridDrift {
        0% { transform: translate(0, 0); }
        50% { transform: translate(13px, 13px); }
        100% { transform: translate(26px, 26px); }
    }

    .royal-hero-content {
        position: relative;
        z-index: 2;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 10px;
        width: 100%;
    }

    /* Main Heading: High-contrast luminous gradient & glow */
    #royal-hero-box .hero-main-title,
    .royal-hero-box h1,
    .royal-hero-box .hero-main-title,
    h1.hero-main-title {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: clamp(1.75rem, 3.8vw, 2.75rem) !important;
        font-weight: 800 !important;
        letter-spacing: -0.03em !important;
        line-height: 1.18 !important;
        margin: 0 !important;
        padding: 0 !important;
        color: #ffffff !important;
        background: linear-gradient(90deg, #ffffff 0%, #fef08a 50%, #bae6fd 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        filter: drop-shadow(0 4px 14px rgba(0, 0, 0, 0.32)) !important;
        text-shadow: 0 4px 18px rgba(0, 0, 0, 0.22) !important;
        display: inline-block !important;
    }

    /* Subtitle: High-contrast warm butter-yellow/gold */
    #royal-hero-box .hero-subtitle,
    .royal-hero-box p.hero-subtitle,
    .royal-hero-box .hero-subtitle,
    p.hero-subtitle {
        font-family: 'Inter', sans-serif !important;
        font-size: clamp(0.88rem, 1.4vw, 1.12rem) !important;
        font-weight: 600 !important;
        color: #fde68a !important;
        margin: 0 !important;
        padding: 0 !important;
        letter-spacing: -0.01em !important;
        line-height: 1.35 !important;
        text-shadow: 0 2px 8px rgba(15, 23, 42, 0.3) !important;
    }

    /* Step Flow Bar: Sleek responsive horizontal ribbon */
    .hero-flow-bar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: center;
        gap: 8px 10px;
        margin-top: 14px;
        width: 100%;
        max-width: 100%;
    }

    /* Step Pills: Frosted glass, gold border, bright white text */
    #royal-hero-box .flow-step-pill,
    .royal-hero-box .flow-step-pill,
    span.flow-step-pill {
        display: inline-flex !important;
        align-items: center !important;
        background: rgba(255, 255, 255, 0.16) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(254, 240, 138, 0.45) !important;
        border-radius: 9999px !important;
        padding: 6px 15px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: #ffffff !important;
        letter-spacing: 0.01em !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        white-space: nowrap !important;
    }

    #royal-hero-box .flow-step-pill:hover,
    .royal-hero-box .flow-step-pill:hover,
    span.flow-step-pill:hover {
        background: rgba(255, 255, 255, 0.28) !important;
        border-color: rgba(254, 240, 138, 0.8) !important;
        transform: translateY(-2px) scale(1.02) !important;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2) !important;
    }

    /* Gold Arrows between pills */
    #royal-hero-box .flow-arrow,
    .royal-hero-box .flow-arrow,
    span.flow-arrow {
        color: #fde047 !important;
        font-size: 0.95rem !important;
        font-weight: 800 !important;
        user-select: none !important;
        text-shadow: 0 2px 6px rgba(0, 0, 0, 0.35) !important;
        flex-shrink: 0 !important;
    }

    /* Mobile & Tablet Specific Rectangle Hero Shape Overrides */
    @media (max-width: 768px) {
        .royal-hero-box {
            padding: 16px 14px 14px 14px !important;
            border-radius: 14px !important;
            margin: 0 0 16px 0 !important;
            box-shadow: 0 8px 24px -6px rgba(15, 37, 87, 0.3) !important;
        }

        .royal-hero-content {
            gap: 6px !important;
        }

        #royal-hero-box .hero-main-title,
        .royal-hero-box h1,
        .royal-hero-box .hero-main-title,
        h1.hero-main-title {
            font-size: clamp(1.2rem, 4.6vw, 1.55rem) !important;
            line-height: 1.2 !important;
            letter-spacing: -0.02em !important;
        }

        #royal-hero-box .hero-subtitle,
        .royal-hero-box p.hero-subtitle,
        .royal-hero-box .hero-subtitle,
        p.hero-subtitle {
            font-size: clamp(0.72rem, 2.6vw, 0.84rem) !important;
            margin-top: 1px !important;
            line-height: 1.3 !important;
        }

        .hero-flow-bar {
            display: flex !important;
            flex-wrap: nowrap !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
            justify-content: flex-start !important;
            gap: 6px !important;
            margin-top: 10px !important;
            padding: 4px 2px !important;
            scrollbar-width: none !important;
            width: 100% !important;
        }

        .hero-flow-bar::-webkit-scrollbar {
            display: none !important;
        }

        #royal-hero-box .flow-step-pill,
        .royal-hero-box .flow-step-pill,
        span.flow-step-pill {
            padding: 4px 10px !important;
            font-size: 0.72rem !important;
            flex-shrink: 0 !important;
        }

        #royal-hero-box .flow-arrow,
        .royal-hero-box .flow-arrow,
        span.flow-arrow {
            font-size: 0.76rem !important;
            flex-shrink: 0 !important;
        }
    }

    /* =====================================================================
       3. NUMBERED WORKSPACE CARD CONTAINERS & SCROLL REVEAL (RESPONSIVE)
       ===================================================================== */
    [data-testid="stVerticalBlockBorderWrapper"],
    .workspace-card {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 20px rgba(15, 23, 42, 0.04) !important;
        padding: 24px 28px !important;
        margin-bottom: 22px !important;
        transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.4s ease !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"]:hover,
    .workspace-card:hover {
        box-shadow: 0 8px 30px rgba(15, 23, 42, 0.07) !important;
    }

    @media (max-width: 768px) {
        [data-testid="stVerticalBlockBorderWrapper"],
        .workspace-card {
            padding: 16px 14px !important;
            border-radius: 12px !important;
            margin-bottom: 16px !important;
        }
    }

    /* Card scroll-reveal states */
    .card-reveal-init {
        opacity: 0;
        transform: translateY(20px);
    }
    .revealed {
        opacity: 1 !important;
        transform: translateY(0) !important;
    }

    /* Step Card Header */
    .step-card-header {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 18px;
        padding-bottom: 14px;
        border-bottom: 1px solid #f1f5f9;
    }

    .step-num-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
        color: #ffffff;
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-weight: 800;
        font-size: 15px;
        box-shadow: 0 3px 10px rgba(37, 99, 235, 0.28);
        flex-shrink: 0;
    }

    .step-header-text {
        display: flex;
        flex-direction: column;
    }

    .step-card-title {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        color: #0f172a !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.25 !important;
        letter-spacing: -0.02em !important;
    }

    .step-card-sub {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem !important;
        color: #64748b !important;
        margin: 3px 0 0 0 !important;
        padding: 0 !important;
        line-height: 1.4 !important;
    }

    @media (max-width: 768px) {
        .step-card-header {
            gap: 10px !important;
            margin-bottom: 12px !important;
            padding-bottom: 10px !important;
        }
        .step-num-badge {
            width: 28px !important;
            height: 28px !important;
            font-size: 13px !important;
            border-radius: 8px !important;
        }
        .step-card-title {
            font-size: 1.05rem !important;
        }
        .step-card-sub {
            font-size: 0.78rem !important;
        }
    }
        font-size: 0.85rem !important;
        color: #64748b !important;
        margin: 3px 0 0 0 !important;
        padding: 0 !important;
        line-height: 1.4 !important;
    }

    /* =====================================================================
       4. CLEAN LIGHT-MODE FILE UPLOADER & BUTTONS (NO BACKGROUND COLOR)
       ===================================================================== */
    /* File uploader container */
    [data-testid="stFileUploader"] section {
        background-color: #ffffff !important;
        border: 2px dashed #cbd5e1 !important;
        border-radius: 12px !important;
        color: #1e293b !important;
        padding: 22px !important;
        transition: all 0.2s ease !important;
    }

    [data-testid="stFileUploader"] section:hover {
        border-color: #2563eb !important;
        background-color: #ffffff !important;
    }

    [data-testid="stFileUploader"] section * {
        color: #1e293b !important;
    }

    [data-testid="stFileUploader"] section small {
        color: #64748b !important;
    }

    /* Browse files button inside uploader */
    [data-testid="stFileUploader"] button {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #cbd5e1 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }

    [data-testid="stFileUploader"] button:hover {
        background-color: #f8fafc !important;
        border-color: #94a3b8 !important;
        color: #0f172a !important;
        transform: translateY(-1px) !important;
    }

    /* Secondary & Demo buttons (e.g. Load Bundled Primary Dataset) */
    div[data-testid="stButton"] button:not([kind="primary"]),
    .stButton > button:not([kind="primary"]),
    button[data-testid="baseButton-secondary"],
    .stButton > button {
        background: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    }

    div[data-testid="stButton"] button:not([kind="primary"]):hover,
    .stButton > button:not([kind="primary"]):hover,
    button[data-testid="baseButton-secondary"]:hover,
    .stButton > button:hover {
        background: #f8fafc !important;
        border-color: #94a3b8 !important;
        color: #0f172a !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
    }

    /* Primary Generation Trigger Button */
    div[data-testid="stButton"] button[kind="primary"],
    .stButton button[kind="primary"],
    button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        letter-spacing: -0.01em !important;
        box-shadow: 0 4px 14px rgba(29, 78, 216, 0.35) !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    div[data-testid="stButton"] button[kind="primary"]:hover,
    .stButton button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(135deg, #1e40af 0%, #1d4ed8 100%) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(29, 78, 216, 0.45) !important;
    }

    div[data-testid="stButton"] button[kind="primary"]:active,
    button[data-testid="baseButton-primary"]:active {
        transform: translateY(0px) !important;
        box-shadow: 0 2px 8px rgba(29, 78, 216, 0.3) !important;
    }

    div[data-testid="stButton"] button[kind="secondary"],
    .stButton button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.2s ease !important;
    }

    /* KPI Metrics Cards */
    .stat-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 18px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
    }
    .stat-val {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 26px;
        font-weight: 800;
        color: #1d4ed8;
        margin: 4px 0;
    }
    .stat-lbl {
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.6px;
    }

    .status-draft { background-color: #fef3c7; color: #92400e; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 12px; }
    .status-approved { background-color: #dbeafe; color: #1e40af; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 12px; }
    .status-published { background-color: #d1fae5; color: #065f46; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 12px; }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #ffffff !important;
        border-bottom: 2px solid #e2e8f0 !important;
        padding: 4px 0 !important;
        border-radius: 0 !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px !important;
        padding: 8px 16px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 600 !important;
        color: #64748b !important;
        border: none !important;
        background: transparent !important;
    }
    .stTabs [aria-selected="true"] {
        background: transparent !important;
        color: #1d4ed8 !important;
        border-bottom: 2px solid #1d4ed8 !important;
        font-weight: 700 !important;
        box-shadow: none !important;
    }

    /* =====================================================================
       5. PLOTLY CHARTS & TIMETABLE TABLES CLEAN TRANSPARENT STYLING
       ===================================================================== */
    .js-plotly-plot,
    .js-plotly-plot .plotly,
    .js-plotly-plot .plotly .main-svg,
    .js-plotly-plot .plotly .svg-container,
    .js-plotly-plot .plotly .plot-container,
    .js-plotly-plot .plotly .bglayer,
    .js-plotly-plot .plotly .bglayer rect,
    .js-plotly-plot .plotly .bg,
    [data-testid="stPlotlyChart"],
    [data-testid="stPlotlyChart"] > div,
    [data-testid="stPlotlyChart"] iframe {
        background: transparent !important;
        background-color: transparent !important;
    }

    .js-plotly-plot .plotly .bglayer rect,
    .js-plotly-plot .plotly rect.bg {
        fill: transparent !important;
    }

    /* Timetable Grid & Tables clean white styling with responsive horizontal scroll */
    [data-testid="stTable"],
    div:has(> table),
    .stDataFrame {
        width: 100% !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }

    table {
        width: 100% !important;
        min-width: 620px !important;
        border-collapse: separate !important;
        border-spacing: 0 !important;
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        overflow: hidden !important;
        margin: 14px 0 !important;
    }

    @media (min-width: 1024px) {
        table {
            min-width: 100% !important;
        }
    }

    th {
        background-color: #ffffff !important;
        color: #0f172a !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        padding: 12px 14px !important;
        border-bottom: 2px solid #e2e8f0 !important;
        text-align: center !important;
    }
    td {
        background-color: #ffffff !important;
        border-bottom: 1px solid #f1f5f9 !important;
        border-right: 1px solid #f1f5f9 !important;
        padding: 10px !important;
        vertical-align: top !important;
        font-family: 'Inter', sans-serif !important;
    }
    td:last-child {
        border-right: none !important;
    }
    tr:last-child td {
        border-bottom: none !important;
    }

    /* =====================================================================
       6. GLOBAL MOBILE RESPONSIVENESS OVERRIDES
       ===================================================================== */
    @media (max-width: 768px) {
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: 10px !important;
        }

        .stButton > button,
        div[data-testid="stButton"] button {
            width: 100% !important;
            padding: 11px 16px !important;
            font-size: 0.92rem !important;
        }

        [data-testid="stFileUploader"] section {
            padding: 14px !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto !important;
            white-space: nowrap !important;
            -webkit-overflow-scrolling: touch !important;
            scrollbar-width: none !important;
            gap: 4px !important;
        }

        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
            display: none !important;
        }

        .stTabs [data-baseweb="tab"] {
            padding: 6px 12px !important;
            font-size: 0.82rem !important;
            white-space: nowrap !important;
        }

        .stat-card {
            padding: 12px 8px !important;
            margin-bottom: 8px !important;
        }

        .stat-val {
            font-size: 20px !important;
        }

        .stat-lbl {
            font-size: 10px !important;
        }

        th {
            padding: 8px 10px !important;
            font-size: 11px !important;
        }

        td {
            padding: 6px !important;
            font-size: 11px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# SESSION STATE & DATABASE INITIALIZATION
# =====================================================================
if "db" not in st.session_state:
    st.session_state.db = DatabaseManager()

db = st.session_state.db

# Dynamic Timetable Regeneration Session State
if "locked_sessions" not in st.session_state:
    st.session_state["locked_sessions"] = set()
if "last_moved_sessions" not in st.session_state:
    st.session_state["last_moved_sessions"] = set()
if "regeneration_summary" not in st.session_state:
    st.session_state["regeneration_summary"] = []
if "timetable_undo_snapshot" not in st.session_state:
    st.session_state["timetable_undo_snapshot"] = None

# Ensure primary dataset is loaded initially if tables are empty
dept_df = db.get_departments()
if dept_df.empty and os.path.exists("data/AI_Timetable_Demo_Data.xlsx"):
    is_v, _, dfs = db.validate_excel_workbook("data/AI_Timetable_Demo_Data.xlsx")
    if is_v:
        db.import_validated_data(dfs)

# =====================================================================
# SIDEBAR NAVIGATION (CLEAN & MINIMAL: 4 ESSENTIAL OPTIONS)
# =====================================================================
with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 10px 0;'>
            <span style='font-size: 38px;'>🏛️</span>
            <h3 style='margin: 5px 0 0 0; color: #1E3A8A;'>AcademiaPlan AI</h3>
            <p style='font-size: 11px; color: #64748B; margin: 0;'>NEP 2020 Timetable System</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    menu = st.radio(
        "Navigation",
        [
            "⚡ Timetable Generator & Export",
            "📅 View Timetables",
            "📊 Analytics & Dashboard",
            "📁 Data Management"
        ],
        index=0
    )

    st.markdown("---")
    sb_connected, sb_msg = db.is_supabase_connected()
    if sb_connected:
        st.success(f"🟢 **Supabase Connected**\n\n{sb_msg}")
    else:
        st.info("ℹ️ **Local Engine (Active)**\n\nPostgreSQL schema mirrored in SQLite")

    st.markdown("<p style='font-size:11px; color:#94A3B8; text-align:center;'>B.Tech CSE Mini Project<br/>OR-Tools CP-SAT Optimizer</p>", unsafe_allow_html=True)

# =====================================================================
# 2. SELF-CONTAINED ROYAL-BLUE RECTANGULAR HERO BOX & SCROLL ANIMATION
# =====================================================================
st.markdown("""
<div id="royal-hero-box" class="royal-hero-box">
    <div class="royal-hero-content">
        <h1 class="hero-main-title">AI Timetable Generator</h1>
        <p class="hero-subtitle">NEP 2020 for Multidisciplinary Higher Education</p>
        <div class="hero-flow-bar">
            <span class="flow-step-pill">1. Collect Inputs</span>
            <span class="flow-arrow">→</span>
            <span class="flow-step-pill">2. Apply Constraints</span>
            <span class="flow-arrow">→</span>
            <span class="flow-step-pill">3. Run Algorithm</span>
            <span class="flow-arrow">→</span>
            <span class="flow-step-pill">4. Analytics &amp; Graphs</span>
            <span class="flow-arrow">→</span>
            <span class="flow-step-pill">5. Validate &amp; Export</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Client-side requestAnimationFrame scroll listener (glides upward, scales down, fades out over 380px)
components.html("""
<script>
(function() {
    function setupScrollAnimation() {
        try {
            const pDoc = window.parent.document;
            const pWin = window.parent;
            if (!pDoc || !pWin) return;

            const heroBox = pDoc.getElementById("royal-hero-box");
            if (!heroBox) return;

            const stAppContainer = pDoc.querySelector('[data-testid="stAppViewContainer"]');
            const mainEl = pDoc.querySelector('.main');
            const scrollContainer = stAppContainer || mainEl || pDoc.documentElement || pWin;

            let ticking = false;

            function onScroll() {
                if (!ticking) {
                    pWin.requestAnimationFrame(() => {
                        const scrollTop = (scrollContainer && scrollContainer.scrollTop !== undefined)
                            ? scrollContainer.scrollTop
                            : (pWin.pageYOffset || pDoc.documentElement.scrollTop || 0);

                        const translateY = -scrollTop * 0.35;
                        const scale = Math.max(0.85, 1 - (scrollTop * 0.00015));
                        const maxFade = (pWin.innerWidth && pWin.innerWidth < 768) ? 220 : 320;
                        const opacity = Math.max(0, 1 - (scrollTop / maxFade));

                        heroBox.style.transform = `translate3d(0, ${translateY.toFixed(2)}px, 0) scale(${scale.toFixed(4)})`;
                        heroBox.style.opacity = `${opacity.toFixed(3)}`;
                        heroBox.style.pointerEvents = opacity < 0.05 ? 'none' : 'auto';

                        ticking = false;
                    });
                    ticking = true;
                }
            }

            [stAppContainer, mainEl, pWin].forEach(target => {
                if (target && target.addEventListener) {
                    target.removeEventListener('scroll', onScroll);
                    target.addEventListener('scroll', onScroll, { passive: true });
                }
            });

            onScroll();

            // Workspace cards scroll reveal observer
            if (pWin.IntersectionObserver) {
                const observer = new pWin.IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('revealed');
                        }
                    });
                }, {
                    root: scrollContainer === pWin ? null : scrollContainer,
                    threshold: 0.05,
                    rootMargin: "0px 0px -30px 0px"
                });

                const cards = pDoc.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"], .workspace-card');
                cards.forEach(card => {
                    if (!card.classList.contains('revealed')) {
                        card.classList.add('card-reveal-init');
                        observer.observe(card);
                    }
                });
            }
        } catch (e) {
            console.warn("Scroll animation initialization note:", e);
        }
    }

    setupScrollAnimation();
    setTimeout(setupScrollAnimation, 150);
    setTimeout(setupScrollAnimation, 500);
    setTimeout(setupScrollAnimation, 1200);
})();
</script>
""", height=0)

# =====================================================================
# SECTION 1: TIMETABLE GENERATOR & EXPORT (COMPLETE 1-CLICK PIPELINE)
# =====================================================================
if menu == "⚡ Timetable Generator & Export":
    # -------------------------------------------------------------
    # STEP 1: ACADEMIC DATASET INPUT
    # -------------------------------------------------------------
    with st.container(border=True):
        st.markdown("""
        <div class="step-card-header">
            <div class="step-num-badge">01</div>
            <div class="step-header-text">
                <h3 class="step-card-title">Academic Dataset Input</h3>
                <p class="step-card-sub">Upload institutional 9-sheet Excel workbook (.xlsx) or load the verified demo dataset</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c_up1, c_up2 = st.columns([2, 1])
        with c_up1:
            pipe_file = st.file_uploader(
                "Upload Institutional Excel Workbook (.xlsx) with all 9 sheets",
                type=["xlsx"],
                key="pipe_file_uploader"
            )

        with c_up2:
            st.write("Or use primary demo workbook:")
            if st.button("📁 Load Bundled Primary Dataset", use_container_width=True):
                with st.spinner("Validating and importing primary dataset..."):
                    is_v, errs, dfs = db.validate_excel_workbook("data/AI_Timetable_Demo_Data.xlsx")
                    if is_v:
                        db.import_validated_data(dfs)
                        st.success("Primary demo dataset loaded successfully!")
                        st.rerun()
                    else:
                        st.error(f"Validation failed: {errs}")

        if pipe_file is not None:
            with st.spinner("Validating uploaded workbook..."):
                is_valid, errors, dfs = db.validate_excel_workbook(pipe_file)
            if is_valid:
                st.success("✅ Workbook validation PASSED! All 9 worksheets & foreign-key relationships verified.")
                if st.button("📥 Import Uploaded Data into Database", type="secondary"):
                    ok, msg = db.import_validated_data(dfs)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.error("❌ Validation errors in workbook:")
                for err in errors:
                    st.write(f"- {err}")

    # -------------------------------------------------------------
    # STEP 2: CONSTRAINT SETTINGS & OPTIMIZATION WEIGHTS
    # -------------------------------------------------------------
    with st.container(border=True):
        st.markdown("""
        <div class="step-card-header">
            <div class="step-num-badge">02</div>
            <div class="step-header-text">
                <h3 class="step-card-title">Constraint Settings &amp; Optimization Weights</h3>
                <p class="step-card-sub">Fine-tune solver timeout and multi-objective balancing weights</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c_set1, c_set2 = st.columns(2)
        with c_set1:
            w_time = st.slider("Solver Time Limit (seconds)", min_value=5, max_value=60, value=25)
            w_workload = st.slider("Faculty Workload Balancing Weight", min_value=1, max_value=10, value=5)
        with c_set2:
            w_gap = st.slider("Student Gap Reduction Weight", min_value=1, max_value=10, value=8)
            w_room = st.slider("Room Utilization Balancing Weight", min_value=1, max_value=10, value=3)
        if st.button("💾 Save Constraint Preferences", use_container_width=True):
            db.update_constraint_value("solver_time_limit_seconds", str(w_time))
            db.update_constraint_value("soft_workload_weight", str(w_workload))
            db.update_constraint_value("soft_student_gap_weight", str(w_gap))
            db.update_constraint_value("soft_room_utilization_weight", str(w_room))
            st.success("Constraints updated successfully!")

    # -------------------------------------------------------------
    # STEP 3: GENERATE TIMETABLE (AI OPTIMIZATION ENGINE)
    # -------------------------------------------------------------
    with st.container(border=True):
        st.markdown("""
        <div class="step-card-header">
            <div class="step-num-badge">03</div>
            <div class="step-header-text">
                <h3 class="step-card-title">Generate Timetable (AI Optimization Engine)</h3>
                <p class="step-card-sub">Execute Google OR-Tools CP-SAT exact constraint solver for lectures, electives &amp; continuous lab blocks</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c_gen1, c_gen2 = st.columns([2, 1])
        with c_gen1:
            gen_clicked = st.button("🚀 Generate Complete Timetable & Analytics", type="primary", use_container_width=True)
        with c_gen2:
            st.markdown("<p style='font-size:12px; color:#64748B; margin-top:8px;'>Combinatorial optimization engine enforcing 10 hard NEP 2020 rules with zero student clashes.</p>", unsafe_allow_html=True)

        if gen_clicked:
            with st.status("Executing Google OR-Tools CP-SAT Optimization Engine...", expanded=True) as status_box:
                st.write("1. Reading academic cohorts, room capacities, and faculty availability...")
                time.sleep(0.3)
                st.write("2. Enforcing 10 Hard NEP 2020 Constraints & Continuous Lab Blocks...")
                time.sleep(0.3)
                st.write("3. Solving combinatorial exact constraint model...")

                optimizer = TimetableOptimizer(db)
                res = optimizer.generate()

                if res["success"]:
                    v_id = f"V{int(time.time())}"
                    db.save_timetable_version(
                        version_id=v_id,
                        version_name=f"NEP Schedule {time.strftime('%H:%M:%S')}",
                        entries=res["entries"],
                        metrics=res["metrics"],
                        notes="Generated via Timetable Generator"
                    )
                    st.session_state["active_pipeline_vid"] = v_id
                    status_box.update(label=f"✅ Timetable Solved in {res['metrics']['duration_seconds']}s ({res['status']})!", state="complete", expanded=False)
                    st.success(f"🎉 Generated Timetable Saved as **{v_id}** with **0 conflicts**!")
                    st.balloons()
                else:
                    status_box.update(label="❌ Timetable Infeasible!", state="error", expanded=True)
                    st.error(res["message"])
                    if res.get("diagnostics"):
                        for d in res["diagnostics"]:
                            st.warning(f"**[{d['severity']}] {d['category']}**: {d['reason']}\n\n👉 Fix: {d['suggestion']}")

    # -------------------------------------------------------------
    # STEP 4: ANALYTICS & GENERATED TIMETABLE GRIDS
    # -------------------------------------------------------------
    versions = db.get_timetable_versions()
    if not versions.empty:
        active_vid = st.session_state.get("active_pipeline_vid", versions["version_id"].iloc[0])
        if active_vid not in versions["version_id"].values:
            active_vid = versions["version_id"].iloc[0]

        v_rec = versions[versions["version_id"] == active_vid].iloc[0]
        entries_df = db.get_timetable_entries(active_vid)
        students_df = db.get_students()
        enroll_df = db.get_student_enrollments()
        courses_df = db.get_courses()
        rooms_df = db.get_classrooms()
        faculty_df = db.get_faculty()

        validator = ConflictValidator(db)
        audit = validator.validate(active_vid)

        with st.container(border=True):
            st.markdown("""
            <div class="step-card-header">
                <div class="step-num-badge">04</div>
                <div class="step-header-text">
                    <h3 class="step-card-title">Analytics &amp; Generated Timetable Grids</h3>
                    <p class="step-card-sub">Conflict-free department schedules, registered student counts &amp; resource utilization charts</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # KPI Cards
            k1, k2, k3, k4, k5 = st.columns(5)
            with k1:
                st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Version</div><div class='stat-val'>{active_vid}</div></div>", unsafe_allow_html=True)
            with k2:
                st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Sessions Scheduled</div><div class='stat-val'>{len(entries_df)}</div></div>", unsafe_allow_html=True)
            with k3:
                st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Quality Score</div><div class='stat-val' style='color:#059669;'>{audit['score']}%</div></div>", unsafe_allow_html=True)
            with k4:
                st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Hard Conflicts</div><div class='stat-val' style='color:#059669;'>{audit['hard_conflicts']}</div></div>", unsafe_allow_html=True)
            with k5:
                st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Status</div><div class='stat-val'><span class='status-{v_rec['status'].lower()}'>{v_rec['status']}</span></div></div>", unsafe_allow_html=True)

            st.markdown("<br/>", unsafe_allow_html=True)

            # Display Change Summary when dynamic regeneration has been executed
            if st.session_state.get("regeneration_summary"):
                moved_list = st.session_state["regeneration_summary"]
                st.markdown(f"""
                <div style="background:#ECFDF5; border:1px solid #6EE7B7; border-left:5px solid #10B981; border-radius:8px; padding:12px 16px; margin:8px 0 14px 0;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="font-weight:700; color:#065F46; font-size:14px;">
                            🔄 Dynamic Regeneration Summary: {len(moved_list)} Session(s) Relocated | {len(entries_df) - len(moved_list)} Slots Kept Fixed
                        </div>
                        <span style="background:#D1FAE5; color:#047857; font-size:11px; font-weight:700; padding:2px 8px; border-radius:12px;">Zero Clashes Guaranteed</span>
                    </div>
                    <div style="margin-top:8px; font-size:12px; color:#1E293B;">
                """, unsafe_allow_html=True)
                for m in moved_list:
                    st.markdown(f"• **{m['course_id']} ({m['course_name']})**: {m['old_day']} {m['old_period']} ({m['old_room']}) &nbsp;➔&nbsp; <b style='color:#059669;'>{m['new_day']} {m['new_period']} ({m['new_room']})</b> *({m['faculty_name']})*", unsafe_allow_html=True)
                st.markdown("</div></div>", unsafe_allow_html=True)
                if st.button("✖️ Clear Regeneration Highlights", key="btn_clear_highlights"):
                    st.session_state["last_moved_sessions"] = set()
                    st.session_state["regeneration_summary"] = []
                    st.rerun()

            # Department & Elective Timetable Tabs
            st.markdown("##### 🗓️ Department & Elective Timetables (Zero Clashes Guaranteed)")
            tab_cse, tab_ece, tab_it, tab_multi, tab_custom = st.tabs([
                "💻 CSE (30 Students)",
                "📡 ECE (15 Students)",
                "🌐 IT (15 Students)",
                "📚 Multidisciplinary & Open Electives",
                "🔍 Custom Resource Filter"
            ])

            active_locked = st.session_state.get("locked_sessions", set())
            active_moved = st.session_state.get("last_moved_sessions", set())

            with tab_cse:
                st.markdown("#### 💻 CSE Department Timetable (30 Students)")
                st.caption("👥 Cohort: 30 Students (CSE2A: 15, CSE2B: 15) | Core: C101, C102, C103, C104, C105 | Electives: X401 (14 CSE), I303 (16 CSE) | Skill: X403 (30 CSE)")
                grid_cse = build_department_cohort_grid(entries_df, "CSE", students_df, enroll_df, locked_sessions=active_locked, moved_sessions=active_moved)
                st.write("Timings: P1 (09:00-09:50) | P2 (09:50-10:40) | P3 (10:50-11:40) | P4 (11:40-12:30) | [Lunch 12:30-13:30] | P5 (13:30-14:20) | P6 (14:20-15:10)")
                st.write(grid_cse.to_html(escape=False), unsafe_allow_html=True)

                c_btn1, c_btn2, c_btn3 = st.columns(3)
                with c_btn1:
                    pdf_cse = export_timetable_pdf(active_vid, v_rec["version_name"], "CSE Department Timetable (30 Students)", grid_cse, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download CSE PDF", pdf_cse, f"Timetable_CSE_30_Students_{active_vid}.pdf", "application/pdf", use_container_width=True)
                with c_btn2:
                    excel_cse = export_timetable_excel(active_vid, v_rec["version_name"], "CSE Department Timetable (30 Students)", entries_df, grid_cse, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download CSE Excel", excel_cse, f"Timetable_CSE_30_Students_{active_vid}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                with c_btn3:
                    txt_cse = export_timetable_txt(active_vid, v_rec["version_name"], "CSE Department Timetable (30 Students)", grid_cse, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download CSE Text", txt_cse, f"Timetable_CSE_30_Students_{active_vid}.txt", "text/plain", use_container_width=True)

            with tab_ece:
                st.markdown("#### 📡 ECE Department Timetable (15 Students)")
                st.caption("👥 Cohort: 15 Students (ECE2A: 15) | Core: E201, E202, E203 | Skill: E204 (15 ECE), X403 (15 ECE) | Parallel Electives: X401 (8 ECE), X402 (7 ECE)")
                grid_ece = build_department_cohort_grid(entries_df, "ECE", students_df, enroll_df, locked_sessions=active_locked, moved_sessions=active_moved)
                st.write("Timings: P1 (09:00-09:50) | P2 (09:50-10:40) | P3 (10:50-11:40) | P4 (11:40-12:30) | [Lunch 12:30-13:30] | P5 (13:30-14:20) | P6 (14:20-15:10)")
                st.write(grid_ece.to_html(escape=False), unsafe_allow_html=True)

                e_btn1, e_btn2, e_btn3 = st.columns(3)
                with e_btn1:
                    pdf_ece = export_timetable_pdf(active_vid, v_rec["version_name"], "ECE Department Timetable (15 Students)", grid_ece, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download ECE PDF", pdf_ece, f"Timetable_ECE_15_Students_{active_vid}.pdf", "application/pdf", use_container_width=True)
                with e_btn2:
                    excel_ece = export_timetable_excel(active_vid, v_rec["version_name"], "ECE Department Timetable (15 Students)", entries_df, grid_ece, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download ECE Excel", excel_ece, f"Timetable_ECE_15_Students_{active_vid}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                with e_btn3:
                    txt_ece = export_timetable_txt(active_vid, v_rec["version_name"], "ECE Department Timetable (15 Students)", grid_ece, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download ECE Text", txt_ece, f"Timetable_ECE_15_Students_{active_vid}.txt", "text/plain", use_container_width=True)

            with tab_it:
                st.markdown("#### 🌐 IT Department Timetable (15 Students)")
                st.caption("👥 Cohort: 15 Students (IT2A: 15) | Core: I301, I302, I304 | Open Elective: I303 (15 IT) | Interdisciplinary: X404 (15 IT) | Parallel Electives: X401 (7 IT), X402 (8 IT)")
                grid_it = build_department_cohort_grid(entries_df, "IT", students_df, enroll_df, locked_sessions=active_locked, moved_sessions=active_moved)
                st.write("Timings: P1 (09:00-09:50) | P2 (09:50-10:40) | P3 (10:50-11:40) | P4 (11:40-12:30) | [Lunch 12:30-13:30] | P5 (13:30-14:20) | P6 (14:20-15:10)")
                st.write(grid_it.to_html(escape=False), unsafe_allow_html=True)

                i_btn1, i_btn2, i_btn3 = st.columns(3)
                with i_btn1:
                    pdf_it = export_timetable_pdf(active_vid, v_rec["version_name"], "IT Department Timetable (15 Students)", grid_it, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download IT PDF", pdf_it, f"Timetable_IT_15_Students_{active_vid}.pdf", "application/pdf", use_container_width=True)
                with i_btn2:
                    excel_it = export_timetable_excel(active_vid, v_rec["version_name"], "IT Department Timetable (15 Students)", entries_df, grid_it, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download IT Excel", excel_it, f"Timetable_IT_15_Students_{active_vid}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                with i_btn3:
                    txt_it = export_timetable_txt(active_vid, v_rec["version_name"], "IT Department Timetable (15 Students)", grid_it, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download IT Text", txt_it, f"Timetable_IT_15_Students_{active_vid}.txt", "text/plain", use_container_width=True)

            with tab_multi:
                st.markdown("#### 📚 NEP 2020 Multidisciplinary & Open Electives Timetable")
                st.caption("🌐 Combined Electives across CSE, ECE & IT: X401 ML (29 students), X402 IoT (15 students), X403 Communication (45 students), X404 Design Thinking (15 students), I303 Cloud Computing (31 students)")
                grid_multi = build_department_cohort_grid(entries_df, None, students_df, enroll_df, locked_sessions=active_locked, moved_sessions=active_moved)
                st.write("Timings: P1 (09:00-09:50) | P2 (09:50-10:40) | P3 (10:50-11:40) | P4 (11:40-12:30) | [Lunch 12:30-13:30] | P5 (13:30-14:20) | P6 (14:20-15:10)")
                st.write(grid_multi.to_html(escape=False), unsafe_allow_html=True)

                m_btn1, m_btn2, m_btn3 = st.columns(3)
                with m_btn1:
                    pdf_m = export_timetable_pdf(active_vid, v_rec["version_name"], "NEP 2020 Multidisciplinary Electives Timetable", grid_multi, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download Electives PDF", pdf_m, f"Timetable_Multidisciplinary_Electives_{active_vid}.pdf", "application/pdf", use_container_width=True)
                with m_btn2:
                    excel_m = export_timetable_excel(active_vid, v_rec["version_name"], "NEP 2020 Multidisciplinary Electives Timetable", entries_df, grid_multi, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download Electives Excel", excel_m, f"Timetable_Multidisciplinary_Electives_{active_vid}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                with m_btn3:
                    txt_m = export_timetable_txt(active_vid, v_rec["version_name"], "NEP 2020 Multidisciplinary Electives Timetable", grid_multi, {"scheduled_sessions": len(entries_df), "conflict_count": audit["conflict_count"]})
                    st.download_button("📥 Download Electives Text", txt_m, f"Timetable_Multidisciplinary_Electives_{active_vid}.txt", "text/plain", use_container_width=True)

            with tab_custom:
                st.markdown("#### 🔍 Filter Schedule by Resource")
                vt_c1, vt_c2 = st.columns([1, 2])
                with vt_c1:
                    pipe_view_mode = st.selectbox("View Timetable By", ["Department", "Faculty", "Student Group", "Classroom"], key="gen_view_mode")
                with vt_c2:
                    if pipe_view_mode == "Department":
                        depts = db.get_departments()["department_id"].tolist()
                        pipe_filter = st.selectbox("Select Department", ["All"] + depts, key="gen_filter_dept")
                    elif pipe_view_mode == "Faculty":
                        facs = db.get_faculty()["faculty_id"].tolist()
                        fac_names = db.get_faculty().set_index("faculty_id")["faculty_name"].to_dict()
                        pipe_filter = st.selectbox("Select Faculty", ["All"] + facs, format_func=lambda x: f"{x} - {fac_names.get(x, '')}" if x != "All" else "All Faculty", key="gen_filter_fac")
                    elif pipe_view_mode == "Student Group":
                        groups = sorted(students_df["student_group"].unique().tolist())
                        pipe_filter = st.selectbox("Select Student Group", ["All"] + groups, key="gen_filter_grp")
                    elif pipe_view_mode == "Classroom":
                        rooms_list = db.get_classrooms()["classroom_id"].tolist()
                        pipe_filter = st.selectbox("Select Classroom", ["All"] + rooms_list, key="gen_filter_room")

                grid_df = build_timetable_grid(entries_df, pipe_view_mode, pipe_filter, students_df, enroll_df, locked_sessions=active_locked, moved_sessions=active_moved)
                st.markdown(f"##### 🗓️ Schedule Grid: {pipe_view_mode} — {pipe_filter}")
                st.write("Timings: P1 (09:00-09:50) | P2 (09:50-10:40) | P3 (10:50-11:40) | P4 (11:40-12:30) | [Lunch 12:30-13:30] | P5 (13:30-14:20) | P6 (14:20-15:10)")
                st.write(grid_df.to_html(escape=False), unsafe_allow_html=True)

            # =========================================================
            # DYNAMIC TIMETABLE REGENERATION & SLOT PINNING PANEL
            # =========================================================
            st.markdown("<br/>", unsafe_allow_html=True)
            with st.expander("⚡ Dynamic Timetable Regeneration & Disruption Panel", expanded=True):
                st.markdown("""
                <div style="margin-bottom:14px;">
                    <h4 style="margin:0 0 4px 0; font-size:16px; font-weight:700; color:#0F172A;">⚡ Dynamic Timetable Regeneration &amp; Disruption Simulation</h4>
                    <p style="margin:0; font-size:12px; color:#64748B;">Pin / lock specific class or lab time slots, apply real-time faculty or classroom disruptions, and re-optimize ONLY affected slots with 0 clashes guaranteed.</p>
                </div>
                """, unsafe_allow_html=True)

                # 1. PIN / LOCK TIME SLOTS
                st.markdown("###### 📌 1. Pin / Lock Time Slots (Fixed Constraints)")
                c_q1, c_q2, c_q3, c_q4 = st.columns(4)
                with c_q1:
                    if st.button("🔒 Lock All Slots", use_container_width=True, key="btn_lock_all"):
                        st.session_state["locked_sessions"] = set(entries_df["session_id"].tolist())
                        st.toast(f"🔒 Locked all {len(entries_df)} scheduled sessions.")
                        st.rerun()
                with c_q2:
                    if st.button("🔬 Lock All Labs", use_container_width=True, key="btn_lock_labs"):
                        lab_sids = set(entries_df[entries_df["duration_periods"] == 2]["session_id"].tolist())
                        st.session_state["locked_sessions"].update(lab_sids)
                        st.toast(f"🔬 Locked {len(lab_sids)} continuous laboratory sessions.")
                        st.rerun()
                with c_q3:
                    if st.button("📚 Lock All Core Courses", use_container_width=True, key="btn_lock_cores"):
                        core_sids = set(entries_df[entries_df["course_type"] == "Major"]["session_id"].tolist())
                        st.session_state["locked_sessions"].update(core_sids)
                        st.toast(f"📚 Locked {len(core_sids)} core course sessions.")
                        st.rerun()
                with c_q4:
                    if st.button("🔓 Unlock All Slots", use_container_width=True, key="btn_unlock_all"):
                        st.session_state["locked_sessions"] = set()
                        st.toast("🔓 Unlocked all slots.")
                        st.rerun()

                col_lk1, col_lk2 = st.columns(2)
                with col_lk1:
                    all_course_ids = sorted(entries_df["course_id"].unique().tolist())
                    c_name_dict = entries_df.drop_duplicates("course_id").set_index("course_id")["course_name"].to_dict()
                    already_locked_courses = [c for c in all_course_ids if c in st.session_state["locked_sessions"]]
                    sel_lock_courses = st.multiselect(
                        "Lock by Course (Locks all sessions of selected courses):",
                        options=all_course_ids,
                        default=already_locked_courses,
                        format_func=lambda x: f"{x} - {c_name_dict.get(x, '')}",
                        key="ms_lock_courses"
                    )
                    # Update course-level locks in session state
                    for c in all_course_ids:
                        c_sids = set(entries_df[entries_df["course_id"] == c]["session_id"].tolist())
                        if c in sel_lock_courses:
                            st.session_state["locked_sessions"].update(c_sids)
                            st.session_state["locked_sessions"].add(c)
                        elif c in st.session_state["locked_sessions"]:
                            st.session_state["locked_sessions"].difference_update(c_sids)
                            st.session_state["locked_sessions"].discard(c)

                with col_lk2:
                    all_sids = entries_df["session_id"].tolist()
                    def _format_sid(sid):
                        row_m = entries_df[entries_df["session_id"] == sid].iloc[0]
                        return f"{sid}: {row_m['course_id']} ({row_m['day']} {row_m['period_id']} in {row_m['classroom_id']})"
                    
                    cur_locked_sids = [sid for sid in all_sids if sid in st.session_state["locked_sessions"]]
                    sel_lock_sids = st.multiselect(
                        "Lock / Unlock Specific Class or Lab Sessions:",
                        options=all_sids,
                        default=cur_locked_sids,
                        format_func=_format_sid,
                        key="ms_lock_sids"
                    )
                    # Merge individual session selections
                    for sid in all_sids:
                        if sid in sel_lock_sids:
                            st.session_state["locked_sessions"].add(sid)
                        elif sid in st.session_state["locked_sessions"] and not any(entries_df[entries_df["session_id"]==sid]["course_id"].isin(sel_lock_courses)):
                            st.session_state["locked_sessions"].discard(sid)

                locked_count = sum(1 for sid in entries_df["session_id"] if sid in st.session_state["locked_sessions"])
                st.caption(f"🔒 **{locked_count} of {len(entries_df)}** sessions currently locked (`locked=True`). Visually tagged with **🔒 Locked** badges above.")

                st.markdown("<hr style='margin:12px 0;'/>", unsafe_allow_html=True)

                # 2. DYNAMIC CHANGE / DISRUPTION PANEL
                st.markdown("###### ⚠️ 2. Dynamic Change & Disruption Inputs")
                col_dis1, col_dis2 = st.columns(2)

                with col_dis1:
                    st.markdown("👨‍🏫 **Faculty Unavailability**")
                    fac_options = faculty_df["faculty_id"].tolist()
                    fac_name_dict = faculty_df.set_index("faculty_id")["faculty_name"].to_dict()
                    sel_dis_fac = st.selectbox(
                        "Select Faculty Member:",
                        ["None (No Disruption)"] + fac_options,
                        format_func=lambda x: f"{x} - {fac_name_dict.get(x, '')}" if x != "None (No Disruption)" else x,
                        key="dis_fac_sel"
                    )
                    c_fday, c_fper = st.columns(2)
                    with c_fday:
                        sel_dis_fday = st.selectbox("Day Unavailable:", ["Entire Week / All Days"] + DAYS_LIST, key="dis_fday_sel")
                    with c_fper:
                        sel_dis_fper = st.selectbox("Slot Unavailable:", ["Entire Day", "Morning (P1-P4)", "Afternoon (P5-P6)"] + PERIODS_LIST, key="dis_fper_sel")

                with col_dis2:
                    st.markdown("🏫 **Room / Lab Blockage**")
                    room_options = rooms_df["classroom_id"].tolist()
                    room_name_dict = rooms_df.set_index("classroom_id")["classroom_name"].to_dict()
                    sel_dis_room = st.selectbox(
                        "Select Room / Lab to Block:",
                        ["None (No Disruption)"] + room_options,
                        format_func=lambda x: f"{x} - {room_name_dict.get(x, '')}" if x != "None (No Disruption)" else x,
                        key="dis_room_sel"
                    )
                    c_rday, c_rper = st.columns(2)
                    with c_rday:
                        sel_dis_rday = st.selectbox("Day Blocked:", ["Entire Week / All Days"] + DAYS_LIST, key="dis_rday_sel")
                    with c_rper:
                        sel_dis_rper = st.selectbox("Slot Blocked:", ["Entire Day", "Morning (P1-P4)", "Afternoon (P5-P6)"] + PERIODS_LIST, key="dis_rper_sel")

                st.markdown("💬 **Custom Adjustment Input (Natural Language Prompt)**")
                nlp_prompt = st.text_input(
                    "Custom Adjustment Prompt:",
                    placeholder="e.g. Move AI Lab to Friday afternoon, or Shift Cloud Computing to Wednesday morning, or Avoid back-to-back lectures for Batch A",
                    key="input_nlp_prompt"
                )
                parsed_custom_rule = None
                if nlp_prompt.strip():
                    parsed_custom_rule = parse_natural_language_adjustment(nlp_prompt, courses_df, faculty_df, rooms_df)
                    if parsed_custom_rule.get("parsed") and parsed_custom_rule.get("explanation"):
                        st.info(f"💡 **AI Interpreted Rule:** {parsed_custom_rule['explanation']}")
                    else:
                        st.caption("ℹ️ Natural language adjustment registered for optimizer soft preferences.")

                st.markdown("<hr style='margin:12px 0;'/>", unsafe_allow_html=True)

                # 3. REGENERATE & UNDO CONTROLS
                st.markdown("###### 🚀 3. Execute Partial Regeneration")
                c_act1, c_act2 = st.columns([2, 1])

                with c_act1:
                    btn_regen = st.button("⚡ Regenerate Affected Slots", type="primary", use_container_width=True, key="btn_exec_regen")
                with c_act2:
                    can_undo = (st.session_state.get("timetable_undo_snapshot") is not None)
                    btn_undo = st.button("↩️ Undo Regeneration", disabled=not can_undo, use_container_width=True, key="btn_exec_undo")

                if btn_undo and can_undo:
                    snap = st.session_state.pop("timetable_undo_snapshot")
                    st.session_state["active_pipeline_vid"] = snap["version_id"]
                    st.session_state["locked_sessions"] = set(snap.get("locked_sessions", []))
                    st.session_state["last_moved_sessions"] = set()
                    st.session_state["regeneration_summary"] = []
                    st.success(f"↩️ Timetable reverted back to snapshot of **{snap['version_id']}** (taken at {snap['timestamp']}).")
                    st.rerun()

                if btn_regen:
                    # 1. Take Snapshot
                    st.session_state["timetable_undo_snapshot"] = {
                        "version_id": active_vid,
                        "version_name": v_rec["version_name"],
                        "entries": entries_df.to_dict(orient="records"),
                        "locked_sessions": set(st.session_state.get("locked_sessions", set())),
                        "timestamp": time.strftime("%H:%M:%S")
                    }

                    # 2. Build Disruptions
                    f_dis = []
                    if sel_dis_fac != "None (No Disruption)":
                        f_dis.append({
                            "faculty_id": sel_dis_fac,
                            "day": "All" if "All" in sel_dis_fday else sel_dis_fday,
                            "period_id": sel_dis_fper
                        })

                    r_dis = []
                    if sel_dis_room != "None (No Disruption)":
                        r_dis.append({
                            "classroom_id": sel_dis_room,
                            "day": "All" if "All" in sel_dis_rday else sel_dis_rday,
                            "period_id": sel_dis_rper
                        })

                    # 3. Execute partial regeneration
                    opt = TimetableOptimizer(db)
                    with st.spinner("Executing Google OR-Tools CP-SAT Partial Rescheduling..."):
                        reg_res = opt.regenerate_partial(
                            current_entries=entries_df.to_dict(orient="records"),
                            locked_sessions=st.session_state.get("locked_sessions", set()),
                            faculty_disruptions=f_dis,
                            room_disruptions=r_dis,
                            custom_adjustment=parsed_custom_rule
                        )

                    if reg_res["success"]:
                        new_version_id = f"V{int(time.time())}"
                        new_version_name = f"Regenerated Schedule {time.strftime('%H:%M:%S')}"
                        note_txt = f"Partial Regeneration: {len(reg_res['moved_sessions'])} relocated sessions, {reg_res['metrics'].get('stability_score', 0)}% stability."
                        db.save_timetable_version(new_version_id, new_version_name, reg_res["entries"], reg_res["metrics"], note_txt)
                        st.session_state["active_pipeline_vid"] = new_version_id
                        st.session_state["last_moved_sessions"] = {m["session_id"] for m in reg_res["moved_sessions"]}
                        st.session_state["regeneration_summary"] = reg_res["moved_sessions"]
                        st.success(f"🎉 **Regeneration Successful!** Relocated {len(reg_res['moved_sessions'])} session(s) with 0 clashes. Saved as **{new_version_id}**.")
                        st.balloons()
                        st.rerun()
                    else:
                        st.warning(f"⚠️ **Could not reschedule without conflicts:** {reg_res['message']}")
                        if reg_res.get("diagnostics"):
                            for diag in reg_res["diagnostics"]:
                                st.info(f"👉 **Fix Suggestion:** {diag.get('suggestion', '')}")

            st.markdown("<br/>", unsafe_allow_html=True)
            st.markdown("##### 📊 Institutional Resource Utilization Charts")
            g_c1, g_c2 = st.columns(2)
            with g_c1:
                st.markdown("###### 📚 NEP 2020 Course Distribution")
                if not courses_df.empty:
                    type_counts = courses_df["course_type"].value_counts().reset_index()
                    type_counts.columns = ["Course Type", "Count"]
                    fig_pie = px.pie(
                        type_counts,
                        values="Count",
                        names="Course Type",
                        hole=0.45,
                        color="Course Type",
                        color_discrete_map={
                            "Major": "#3B82F6",
                            "Laboratory": "#8B5CF6",
                            "Open Elective": "#10B981",
                            "Interdisciplinary": "#F59E0B",
                            "Skill Enhancement": "#06B6D4"
                        }
                    )
                    fig_pie.update_layout(
                        template="plotly_white",
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=260,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", color="#334155")
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

            with g_c2:
                st.markdown("###### 🏫 Classroom Utilization")
                if not entries_df.empty and not rooms_df.empty:
                    room_usage = entries_df.groupby("classroom_id")["duration_periods"].sum().reset_index()
                    room_usage = rooms_df[["classroom_id", "classroom_name", "room_type"]].merge(room_usage, on="classroom_id", how="left").fillna(0)
                    room_usage["utilization_pct"] = (room_usage["duration_periods"] / 30.0) * 100.0

                    fig_bar = px.bar(
                        room_usage,
                        x="classroom_id",
                        y="duration_periods",
                        color="room_type",
                        hover_data=["classroom_name", "utilization_pct"],
                        labels={"duration_periods": "Periods Occupied (Weekly)", "classroom_id": "Classroom"},
                        color_discrete_map={
                            "Classroom": "#3B82F6",
                            "Computer Lab": "#8B5CF6",
                            "Electronics Lab": "#EC4899"
                        }
                    )
                    fig_bar.update_layout(
                        template="plotly_white",
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=260,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", color="#334155"),
                        xaxis=dict(showgrid=False),
                        yaxis=dict(showgrid=True, gridcolor="#f1f5f9")
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

            # Faculty workload
            st.markdown("###### 👨‍🏫 Faculty Teaching Load vs Maximum Limit")
            if not faculty_df.empty and not entries_df.empty:
                f_work = entries_df.groupby("faculty_id")["duration_periods"].sum().reset_index()
                fac_merged = faculty_df.merge(f_work, on="faculty_id", how="left").fillna(0)
                fac_merged["assigned_periods"] = fac_merged["duration_periods"].astype(int)

                fig_fac = go.Figure()
                fig_fac.add_trace(go.Bar(
                    name="Assigned Periods",
                    x=fac_merged["faculty_name"],
                    y=fac_merged["assigned_periods"],
                    marker_color="#2563EB"
                ))
                fig_fac.add_trace(go.Bar(
                    name="Max Weekly Limit",
                    x=fac_merged["faculty_name"],
                    y=fac_merged["max_weekly_periods"],
                    marker_color="#CBD5E1"
                ))
                fig_fac.update_layout(
                    template="plotly_white",
                    barmode="group",
                    height=280,
                    margin=dict(t=10, b=30, l=10, r=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", color="#334155"),
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#f1f5f9")
                )
                st.plotly_chart(fig_fac, use_container_width=True)

        # -------------------------------------------------------------
        # STEP 5: VALIDATE & EXPORT
        # -------------------------------------------------------------
        with st.container(border=True):
            st.markdown("""
            <div class="step-card-header">
                <div class="step-num-badge">05</div>
                <div class="step-header-text">
                    <h3 class="step-card-title">Validate &amp; Export Deliverables</h3>
                    <p class="step-card-sub">Independent conflict audit certificate and publication-ready multi-format downloads</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

            master_export_grid = build_timetable_grid(entries_df, "Department", "All", students_df, enroll_df)
            st.write(f"Download institutional master deliverables for version **{active_vid}** in your preferred format:")
            exp_d1, exp_d2, exp_d3 = st.columns(3)
            export_metrics = {
                "scheduled_sessions": len(entries_df),
                "conflict_count": audit["conflict_count"],
                "solver_status": "Validated"
            }

            with exp_d1:
                st.markdown("##### 📄 Master PDF Document")
                pdf_buf = export_timetable_pdf(active_vid, v_rec["version_name"], "Institutional Master Schedule", master_export_grid, export_metrics)
                st.download_button(
                    label="📥 Download Master PDF",
                    data=pdf_buf,
                    file_name=f"Timetable_{active_vid}_Master.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            with exp_d2:
                st.markdown("##### 📊 Master Excel Workbook (.xlsx)")
                excel_buf = export_timetable_excel(active_vid, v_rec["version_name"], "Institutional Master Schedule", entries_df, master_export_grid, export_metrics)
                st.download_button(
                    label="📥 Download Master Excel",
                    data=excel_buf,
                    file_name=f"Timetable_{active_vid}_Master.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            with exp_d3:
                st.markdown("##### 📝 Master Plain Text (.txt)")
                txt_str = export_timetable_txt(active_vid, v_rec["version_name"], "Institutional Master Schedule", master_export_grid, export_metrics)
                st.download_button(
                    label="📥 Download Master Text",
                    data=txt_str,
                    file_name=f"Timetable_{active_vid}_Master.txt",
                    mime="text/plain",
                    use_container_width=True
                )
    else:
        with st.container(border=True):
            st.markdown("""
            <div class="step-card-header">
                <div class="step-num-badge">04</div>
                <div class="step-header-text">
                    <h3 class="step-card-title">Analytics &amp; Generated Timetable Grids</h3>
                    <p class="step-card-sub">Conflict-free department schedules, registered student counts &amp; resource utilization charts</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.info("ℹ️ No timetable generated yet. Run the solver in **Step 3** to automatically populate analytics and schedules.")

        with st.container(border=True):
            st.markdown("""
            <div class="step-card-header">
                <div class="step-num-badge">05</div>
                <div class="step-header-text">
                    <h3 class="step-card-title">Validate &amp; Export Deliverables</h3>
                    <p class="step-card-sub">Independent conflict audit certificate and publication-ready multi-format downloads</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.info("ℹ️ Export options will unlock automatically once a timetable schedule is generated.")

# =====================================================================
# SECTION 2: VIEW TIMETABLES (DETAILED GRIDS & REGENERATION DIFF)
# =====================================================================
elif menu == "📅 View Timetables":
    st.subheader("📅 Academic Timetable Viewer & Simulation")

    versions = db.get_timetable_versions()
    if versions.empty:
        st.warning("No timetable versions generated yet. Go to '⚡ Timetable Generator & Export' to generate your first timetable.")
    else:
        tab_v_grid, tab_v_diff, tab_v_raw = st.tabs(["🗓️ Interactive Weekly Schedule Grid", "🔄 Dynamic Regeneration Diff", "📋 Raw Sessions Table"])

        with tab_v_grid:
            v_options = versions["version_id"].tolist()
            sel_vid = st.selectbox(
                "Select Timetable Version",
                v_options,
                format_func=lambda x: f"{x} - {versions[versions['version_id']==x]['version_name'].values[0]} [{versions[versions['version_id']==x]['status'].values[0]}]",
                key="vgrid_sel"
            )

            entries_df = db.get_timetable_entries(sel_vid)
            students_df = db.get_students()
            enroll_df = db.get_student_enrollments()

            active_locked_v = st.session_state.get("locked_sessions", set())
            active_moved_v = st.session_state.get("last_moved_sessions", set())

            st.markdown("#### 🏛️ Department & Elective Schedules (Clash-Free Grids)")
            v_tab_cse, v_tab_ece, v_tab_it, v_tab_multi, v_tab_filter = st.tabs([
                "💻 CSE (30 Students)",
                "📡 ECE (15 Students)",
                "🌐 IT (15 Students)",
                "📚 Multidisciplinary & Electives",
                "🔍 Custom Resource Filter"
            ])
            with v_tab_cse:
                st.markdown("##### 💻 CSE Department Timetable (30 Students)")
                st.caption("All 30 CSE Students | Core: C101-C105 | Electives: X401 (14 CSE), I303 (16 CSE) | Skill: X403 (30 CSE)")
                g_cse = build_department_cohort_grid(entries_df, "CSE", students_df, enroll_df, locked_sessions=active_locked_v, moved_sessions=active_moved_v)
                st.write(g_cse.to_html(escape=False), unsafe_allow_html=True)
            with v_tab_ece:
                st.markdown("##### 📡 ECE Department Timetable (15 Students)")
                st.caption("All 15 ECE Students | Core: E201-E203 | Skill: E204, X403 | Parallel Electives: X401 (8 ECE), X402 (7 ECE)")
                g_ece = build_department_cohort_grid(entries_df, "ECE", students_df, enroll_df, locked_sessions=active_locked_v, moved_sessions=active_moved_v)
                st.write(g_ece.to_html(escape=False), unsafe_allow_html=True)
            with v_tab_it:
                st.markdown("##### 🌐 IT Department Timetable (15 Students)")
                st.caption("All 15 IT Students | Core: I301, I302, I304 | Electives: I303, X404, X401 (7 IT), X402 (8 IT)")
                g_it = build_department_cohort_grid(entries_df, "IT", students_df, enroll_df, locked_sessions=active_locked_v, moved_sessions=active_moved_v)
                st.write(g_it.to_html(escape=False), unsafe_allow_html=True)
            with v_tab_multi:
                st.markdown("##### 📚 NEP 2020 Multidisciplinary & Open Electives Timetable")
                st.caption("Integrated Electives across branches: X401 ML, X402 IoT, X403 Comm, X404 Design Thinking, I303 Cloud")
                g_m = build_department_cohort_grid(entries_df, None, students_df, enroll_df, locked_sessions=active_locked_v, moved_sessions=active_moved_v)
                st.write(g_m.to_html(escape=False), unsafe_allow_html=True)
            with v_tab_filter:
                c_v1, c_v2, c_v3 = st.columns([1, 1, 1])
                with c_v1:
                    view_mode = st.selectbox("Timetable View Mode", ["Department", "Faculty", "Student Group", "Classroom"], key="vgrid_mode")
                with c_v2:
                    if view_mode == "Department":
                        depts = db.get_departments()["department_id"].tolist()
                        filter_val = st.selectbox("Select Department", ["All"] + depts, key="vgrid_f_dept")
                    elif view_mode == "Faculty":
                        facs = db.get_faculty()["faculty_id"].tolist()
                        fac_names = db.get_faculty().set_index("faculty_id")["faculty_name"].to_dict()
                        filter_val = st.selectbox("Select Faculty", ["All"] + facs, format_func=lambda x: f"{x} - {fac_names.get(x, '')}" if x != "All" else "All Faculty", key="vgrid_f_fac")
                    elif view_mode == "Student Group":
                        groups = sorted(students_df["student_group"].unique().tolist())
                        filter_val = st.selectbox("Select Student Group", ["All"] + groups, key="vgrid_f_grp")
                    elif view_mode == "Classroom":
                        rooms_list = db.get_classrooms()["classroom_id"].tolist()
                        filter_val = st.selectbox("Select Classroom", ["All"] + rooms_list, key="vgrid_f_room")
                with c_v3:
                    day_filter = st.selectbox("Filter by Day", ["Full Week"] + DAYS_LIST, key="vgrid_f_day")

                grid_df = build_timetable_grid(entries_df, view_mode, filter_val, students_df, enroll_df, locked_sessions=active_locked_v, moved_sessions=active_moved_v)
                display_grid = grid_df[[day_filter]] if day_filter != "Full Week" else grid_df

                st.markdown(f"### 🗓️ Weekly Schedule: {view_mode} - {filter_val}")
                st.write("Timings: P1 (09:00-09:50) | P2 (09:50-10:40) | P3 (10:50-11:40) | P4 (11:40-12:30) | Lunch (12:30-13:30) | P5 (13:30-14:20) | P6 (14:20-15:10)")
                st.write(display_grid.to_html(escape=False), unsafe_allow_html=True)

        with tab_v_diff:
            st.markdown("#### 🔄 Dynamic Timetable Regeneration & Disruption Simulation")
            st.write("Perform partial re-optimization with locked slots, faculty unavailability, room blockage, or natural language prompts.")
            col_r1, col_r2 = st.columns([1, 1])
            with col_r1:
                st.markdown("##### ⚙️ Disruption & Regeneration Settings")
                fac_list = db.get_faculty()
                fac_names_map = fac_list.set_index("faculty_id")["faculty_name"].to_dict()
                vsel_f = st.selectbox("Faculty Member", ["None"] + fac_list["faculty_id"].tolist(), format_func=lambda x: f"{x} - {fac_names_map.get(x, '')}" if x != "None" else "None", key="diff_fac")
                vsel_d = st.selectbox("Unavailable Day", ["All"] + DAYS_LIST, key="diff_day")
                vsel_p = st.selectbox("Unavailable Period", ["Entire Day", "Morning (P1-P4)", "Afternoon (P5-P6)"] + PERIODS_LIST, key="diff_per")

                vnlp_text = st.text_input("Custom NLP Adjustment:", placeholder="e.g. Move AI Lab to Friday afternoon", key="diff_nlp")
                v_parsed_rule = None
                if vnlp_text.strip():
                    v_parsed_rule = parse_natural_language_adjustment(vnlp_text, db.get_courses(), fac_list, db.get_classrooms())
                    if v_parsed_rule.get("parsed"):
                        st.info(f"💡 {v_parsed_rule['explanation']}")

                c_vact1, c_vact2 = st.columns([2, 1])
                with c_vact1:
                    if st.button("⚡ Regenerate Affected Slots (Lock Fixed)", type="primary", key="btn_v_regen"):
                        # Snapshot
                        st.session_state["timetable_undo_snapshot"] = {
                            "version_id": sel_vid,
                            "entries": entries_df.to_dict(orient="records"),
                            "locked_sessions": set(st.session_state.get("locked_sessions", set())),
                            "timestamp": time.strftime("%H:%M:%S")
                        }
                        f_dis = []
                        if vsel_f != "None":
                            f_dis.append({"faculty_id": vsel_f, "day": vsel_d, "period_id": vsel_p})
                        opt = TimetableOptimizer(db)
                        with st.spinner("Regenerating affected slots..."):
                            v_res = opt.regenerate_partial(
                                current_entries=entries_df.to_dict(orient="records"),
                                locked_sessions=st.session_state.get("locked_sessions", set()),
                                faculty_disruptions=f_dis,
                                custom_adjustment=v_parsed_rule
                            )
                        if v_res["success"]:
                            new_vid = f"V{int(time.time())}"
                            db.save_timetable_version(
                                version_id=new_vid,
                                version_name=f"Regenerated ({time.strftime('%H:%M:%S')})",
                                entries=v_res["entries"],
                                metrics=v_res["metrics"],
                                notes=f"Partial regeneration from {sel_vid}."
                            )
                            st.session_state["active_pipeline_vid"] = new_vid
                            st.session_state["last_moved_sessions"] = {m["session_id"] for m in v_res["moved_sessions"]}
                            st.session_state["regeneration_summary"] = v_res["moved_sessions"]
                            st.success(f"New Version **{new_vid}** generated with {len(v_res['moved_sessions'])} relocated session(s)!")
                            st.rerun()
                        else:
                            st.warning(f"⚠️ {v_res['message']}")
                with c_vact2:
                    has_v_undo = (st.session_state.get("timetable_undo_snapshot") is not None)
                    if st.button("↩️ Undo", disabled=not has_v_undo, key="btn_v_undo", use_container_width=True):
                        v_snap = st.session_state.pop("timetable_undo_snapshot")
                        st.session_state["active_pipeline_vid"] = v_snap["version_id"]
                        st.session_state["last_moved_sessions"] = set()
                        st.session_state["regeneration_summary"] = []
                        st.success(f"↩️ Reverted to {v_snap['version_id']}")
                        st.rerun()

            with col_r2:
                st.markdown("##### Version Comparison & Relocated Sessions")
                v_all = versions["version_id"].tolist()
                v_old = st.selectbox("Compare Version (Old)", v_all, index=0, key="diff_vold")
                v_new = st.selectbox("With Version (New)", v_all, index=min(1, len(v_all)-1), key="diff_vnew")

                if v_old and v_new:
                    e_old = db.get_timetable_entries(v_old)
                    e_new = db.get_timetable_entries(v_new)
                    diff_res = compare_timetable_versions(e_old, e_new)
                    st.metric("Schedule Similarity", f"{diff_res['similarity_percentage']}%")
                    st.write(f"**Unchanged Sessions:** {diff_res['unchanged_count']} | **Relocated Sessions:** {diff_res['changed_count']}")
                    if diff_res["differences"]:
                        st.dataframe(pd.DataFrame(diff_res["differences"]), use_container_width=True)
                    else:
                        st.info("Both versions have identical schedules.")

        with tab_v_raw:
            st.dataframe(entries_df[["session_id", "course_id", "course_name", "course_type", "faculty_name", "classroom_name", "day", "period_id", "duration_periods"]], use_container_width=True)

# =====================================================================
# SECTION 3: ANALYTICS & DASHBOARD (METRICS, AUDIT & APPROVAL)
# =====================================================================
elif menu == "📊 Analytics & Dashboard":
    st.subheader("📊 Institutional Analytics, Conflict Audit & Governance")

    depts = db.get_departments()
    students = db.get_students()
    courses = db.get_courses()
    faculty = db.get_faculty()
    rooms = db.get_classrooms()
    versions = db.get_timetable_versions()

    latest_version = versions.iloc[0] if not versions.empty else None
    latest_vid = latest_version["version_id"] if latest_version is not None else None
    entries = db.get_timetable_entries(latest_vid) if latest_vid else pd.DataFrame()

    validator = ConflictValidator(db)
    audit = validator.validate(latest_vid) if latest_vid else {"is_valid": False, "score": 0, "hard_conflicts": 0, "conflicts": []}

    # Top Metric Cards
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Departments</div><div class='stat-val'>{len(depts)}</div></div>", unsafe_allow_html=True)
    with m2:
        st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Students</div><div class='stat-val'>{len(students)}</div></div>", unsafe_allow_html=True)
    with m3:
        st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Courses</div><div class='stat-val'>{len(courses)}</div></div>", unsafe_allow_html=True)
    with m4:
        st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Faculty</div><div class='stat-val'>{len(faculty)}</div></div>", unsafe_allow_html=True)
    with m5:
        st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Classrooms</div><div class='stat-val'>{len(rooms)}</div></div>", unsafe_allow_html=True)
    with m6:
        st.markdown(f"<div class='stat-card'><div class='stat-lbl'>Audit Score</div><div class='stat-val' style='color:#059669;'>{audit['score']}%</div></div>", unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    tab_dash_charts, tab_dash_audit, tab_dash_appr = st.tabs(["📈 Resource Utilization Charts", "🛡️ Independent Conflict Audit", "✅ Approval & Publication"])

    with tab_dash_charts:
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown("##### 📚 NEP 2020 Course Distribution")
            if not courses.empty:
                type_counts = courses["course_type"].value_counts().reset_index()
                type_counts.columns = ["Course Type", "Count"]
                fig_pie = px.pie(type_counts, values="Count", names="Course Type", hole=0.45)
                fig_pie.update_layout(
                    template="plotly_white",
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=260,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", color="#334155")
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        with c_right:
            st.markdown("##### 🏫 Classroom Utilization")
            if not entries.empty and not rooms.empty:
                room_usage = entries.groupby("classroom_id")["duration_periods"].sum().reset_index()
                room_usage = rooms[["classroom_id", "classroom_name", "room_type"]].merge(room_usage, on="classroom_id", how="left").fillna(0)
                fig_bar = px.bar(room_usage, x="classroom_id", y="duration_periods", color="room_type")
                fig_bar.update_layout(
                    template="plotly_white",
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=260,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", color="#334155"),
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#f1f5f9")
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        # Faculty workload
        st.markdown("##### 👨‍🏫 Faculty Workload vs Maximum Allowed Limit")
        if not faculty.empty and not entries.empty:
            f_work = entries.groupby("faculty_id")["duration_periods"].sum().reset_index()
            fac_merged = faculty.merge(f_work, on="faculty_id", how="left").fillna(0)
            fig_fac = go.Figure()
            fig_fac.add_trace(go.Bar(name="Assigned Periods", x=fac_merged["faculty_name"], y=fac_merged["duration_periods"].astype(int), marker_color="#2563EB"))
            fig_fac.add_trace(go.Bar(name="Max Limit", x=fac_merged["faculty_name"], y=fac_merged["max_weekly_periods"], marker_color="#CBD5E1"))
            fig_fac.update_layout(
                template="plotly_white",
                barmode="group",
                height=280,
                margin=dict(t=10, b=30, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", color="#334155"),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#f1f5f9")
            )
            st.plotly_chart(fig_fac, use_container_width=True)

    with tab_dash_audit:
        if latest_vid:
            if audit["hard_conflicts"] == 0:
                st.success(f"🎉 **Zero Hard Conflicts Detected!** Timetable **{latest_vid}** satisfies all 10 hard constraints.")
            else:
                st.error(f"⚠️ **{audit['hard_conflicts']} Hard Conflicts Detected!**")
            if audit["conflicts"]:
                st.dataframe(pd.DataFrame(audit["conflicts"]), use_container_width=True)
            else:
                st.info("No clashes found across faculty, room, or student cohorts.")

    with tab_dash_appr:
        if latest_vid:
            st.markdown(f"**Active Version:** `{latest_vid}` | **Status:** <span class='status-{latest_version['status'].lower()}'>{latest_version['status']}</span>", unsafe_allow_html=True)
            performer = st.text_input("Approving Authority Name / Title", "Dr. Academic Dean / Principal")
            comments = st.text_input("Audit Notes", "Verified clash-free multidisciplinary schedule.")

            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("👍 Approve Timetable", disabled=(latest_version["status"] == "Approved" or audit["hard_conflicts"] > 0)):
                    ok, msg = db.update_version_status(latest_vid, "Approved", performer, comments)
                    if ok: st.success(msg); st.rerun()
            with col_btn2:
                if st.button("📢 Publish Timetable", type="primary", disabled=(latest_version["status"] != "Approved")):
                    ok, msg = db.update_version_status(latest_vid, "Published", performer, comments)
                    if ok: st.success(msg); st.rerun()
            with col_btn3:
                if st.button("↩️ Revert to Draft", disabled=(latest_version["status"] == "Draft")):
                    ok, msg = db.update_version_status(latest_vid, "Draft", performer, comments)
                    if ok: st.success(msg); st.rerun()

            st.markdown("##### 📜 Audit Trail Log")
            approvals = db.get_approval_records(latest_vid)
            if not approvals.empty:
                st.dataframe(approvals[["action", "performed_by", "timestamp", "comments"]], use_container_width=True)

# =====================================================================
# SECTION 4: DATA MANAGEMENT (WORKSHEETS & FACULTY AVAILABILITY)
# =====================================================================
elif menu == "📁 Data Management":
    st.subheader("📁 Academic Data Management & Faculty Availability")

    tab_dm_fac, tab_dm_course, tab_dm_room, tab_dm_std, tab_dm_avail = st.tabs([
        "👨‍🏫 Faculty", "📚 Courses", "🏫 Classrooms", "🎓 Students & Cohorts", "🗓️ Faculty Availability Matrix"
    ])

    with tab_dm_fac:
        st.dataframe(db.get_faculty(), use_container_width=True)

    with tab_dm_course:
        st.dataframe(db.get_courses(), use_container_width=True)

    with tab_dm_room:
        st.dataframe(db.get_classrooms(), use_container_width=True)

    with tab_dm_std:
        st.dataframe(db.get_students(), use_container_width=True)

    with tab_dm_avail:
        st.markdown("#### Weekly Faculty Teaching Availability")
        fac_list = db.get_faculty()
        if not fac_list.empty:
            sel_fac = st.selectbox("Select Faculty Member", fac_list["faculty_id"].tolist(), format_func=lambda x: f"{x} - {fac_list[fac_list['faculty_id']==x]['faculty_name'].values[0]}")
            avail_df = db.get_faculty_availability()
            fac_avail = avail_df[avail_df["faculty_id"] == sel_fac]
            matrix = {p: {d: 1 for d in DAYS_LIST} for p in PERIODS_LIST}
            for _, r in fac_avail.iterrows():
                if r["day"] in DAYS_LIST and r["period_id"] in PERIODS_LIST:
                    matrix[r["period_id"]][r["day"]] = int(r["is_available"])
            df_mat = pd.DataFrame(matrix).T[DAYS_LIST]
            st.dataframe(df_mat.style.map(lambda v: "background-color: #DCFCE7; color: #166534;" if v == 1 else "background-color: #FEE2E2; color: #991B1B;"), use_container_width=True)

            col_t1, col_t2, col_t3, col_t4 = st.columns(4)
            with col_t1: t_day = st.selectbox("Day", DAYS_LIST, key="dm_day")
            with col_t2: t_period = st.selectbox("Period", PERIODS_LIST, key="dm_per")
            with col_t3: t_status = st.selectbox("Status", ["Available (1)", "Unavailable (0)"], key="dm_stat")
            with col_t4:
                st.write("")
                st.write("")
                if st.button("Update Slot", type="primary"):
                    is_av = 1 if "Available" in t_status else 0
                    db.set_faculty_availability(sel_fac, t_day, t_period, is_av)
                    st.success(f"Updated {sel_fac} {t_day} {t_period} to {is_av}!")
                    st.rerun()
