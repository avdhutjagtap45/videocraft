import io
import csv
import re
import time
import zipfile
from pathlib import Path
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

from script_parser import parse_script_to_scenes, SAMPLE_PRESETS
try:
    from script_parser import extract_scenario_search, calculate_content_duration, generate_creator_scripts_and_shorts
except ImportError:
    pass

import os
import shutil
DEFAULT_PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "57909969-ce94fac88b6effdff830e1aff")
DEFAULT_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

try:
    from pixabay_api import (
        search_assets,
        DEFAULT_PIXABAY_KEY,
        DEFAULT_OPENAI_KEY,
        generate_ai_image,
        ensure_unique_selections,
        pick_unique_candidate
    )
except ImportError:
    try:
        from pixabay_api import search_assets
    except ImportError:
        pass
    try:
        from pixabay_api import generate_ai_image
    except ImportError:
        def generate_ai_image(prompt, openai_key=DEFAULT_OPENAI_KEY, dest_path=None):
            return None
    try:
        from pixabay_api import ensure_unique_selections, pick_unique_candidate
    except ImportError:
        def pick_unique_candidate(candidates, used_ids):
            if not candidates:
                return -1, None
            for idx, c in enumerate(candidates):
                if c.get("id") not in used_ids:
                    return idx, c
            return 0, candidates[0]

        def ensure_unique_selections(scenes, scene_assets, selected_assets):
            return selected_assets
import importlib
import inspect
import video_engine
importlib.reload(video_engine)
import script_parser
importlib.reload(script_parser)
import pixabay_api
importlib.reload(pixabay_api)
import tts_engine
importlib.reload(tts_engine)
import niche_engine
importlib.reload(niche_engine)
from niche_engine import NICHE_CATALOG, generate_youtube_seo_kit, generate_youtube_thumbnail


from video_engine import (
    download_file,
    create_overlay_image,
    create_fallback_slide,
    process_scene_clip,
    merge_clips_to_final_video,
    make_numbered_zip,
    get_ffmpeg_path,
    BGM_CATALOG,
    BGM_DIR,
    add_background_music_to_video,
    render_single_short_video,
    render_shorts_package
)

def safe_process_scene_clip(**kwargs):
    """Safely executes process_scene_clip with supported parameters only."""
    sig = inspect.signature(video_engine.process_scene_clip)
    valid_args = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return video_engine.process_scene_clip(**valid_args)

try:
    from tts_engine import generate_human_voiceover, estimate_speech_duration, get_audio_duration, VOICE_CATALOG, DEFAULT_VOICE
except ImportError:
    VOICE_CATALOG = {
        "hi-IN-MadhurNeural": "🇮🇳 Madhur (Hindi / Indian Accent Male - Deep & Cinematic)",
        "hi-IN-SwaraNeural": "🇮🇳 Swara (Hindi / Indian Accent Female - Expressive & Clear)",
        "en-US-ChristopherNeural": "🇺🇸 Christopher (Storyteller Male - Documentary / Mystery)",
        "en-US-JennyNeural": "🇺🇸 Jenny (Natural Crisp Female - Clean Narration)"
    }
    DEFAULT_VOICE = "hi-IN-MadhurNeural"
    def generate_human_voiceover(text, output_path, voice=DEFAULT_VOICE, rate="+25%", **kwargs):
        return None
    def estimate_speech_duration(text, speed=1.25, **kwargs):
        return 4.0
    def get_audio_duration(path, **kwargs):
        return 5.0



APP_DIR = Path(__file__).parent
DOWNLOADS_DIR = APP_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

def cleanup_storage_cache(max_age_hours: float = 2.0, max_folder_mb: float = 350.0):
    """
    Automatic Cloud Storage Manager (Optimized for Free Cloud 1GB Limits):
    1. Removes temporary job folders and audio samples older than max_age_hours.
    2. If downloads directory total size exceeds max_folder_mb, automatically deletes
       the oldest job folders and files until disk space is safely below 200MB.
    Guarantees cloud servers never crash with 'Disk quota exceeded'.
    """
    try:
        if not DOWNLOADS_DIR.exists():
            return

        now = time.time()
        max_age_sec = max_age_hours * 3600

        items = []
        total_bytes = 0

        for item in DOWNLOADS_DIR.iterdir():
            try:
                mtime = item.stat().st_mtime
                if item.is_dir():
                    sz = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                else:
                    sz = item.stat().st_size
                items.append((item, mtime, sz))
                total_bytes += sz
            except Exception:
                continue

        # Rule 1: Delete files/folders older than max_age_hours
        remaining_items = []
        for item, mtime, sz in items:
            if (now - mtime) > max_age_sec:
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                    total_bytes -= sz
                except Exception:
                    pass
            else:
                remaining_items.append((item, mtime, sz))

        # Rule 2: If total folder size exceeds max_folder_mb, delete oldest remaining items
        max_bytes = max_folder_mb * 1024 * 1024
        if total_bytes > max_bytes:
            remaining_items.sort(key=lambda x: x[1])
            for item, _, sz in remaining_items:
                if total_bytes <= (max_bytes * 0.5):
                    break
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                    total_bytes -= sz
                except Exception:
                    pass
    except Exception as e:
        print(f"Storage cleanup exception: {e}")

# Run automatic cleanup on app start
cleanup_storage_cache()

# Page configuration
st.set_page_config(
    page_title="VideoCraft Pro Studio · AI Video Engine",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="auto"
)

# Mobile PWA & Responsive Viewport Meta Tags
st.markdown("""
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="theme-color" content="#2563EB">
</head>
""", unsafe_allow_html=True)

# Custom High-End Pure Light Theme CSS (InVideo / Modern Creator Studio Aesthetic)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* Global Typography & Light Canvas */
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-color: #F8FAFC !important;
        color: #0F172A !important;
    }

    /* Ambient Clean Light Canvas */
    .stApp {
        background: radial-gradient(ellipse 90% 50% at 50% -10%, rgba(37, 99, 235, 0.04) 0%, transparent 60%),
                    radial-gradient(ellipse 70% 40% at 85% 15%, rgba(16, 185, 129, 0.03) 0%, transparent 50%),
                    #F8FAFC !important;
    }

    /* Polished Light Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
        box-shadow: 2px 0 12px rgba(0, 0, 0, 0.03) !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #E2E8F0 !important;
        margin: 1.2rem 0 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h3 {
        font-size: 0.82rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
        color: #475569 !important;
        margin-top: 1.3rem !important;
        margin-bottom: 0.6rem !important;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    /* Sidebar Brand Card */
    .sidebar-brand-card {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 16px;
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(79, 70, 229, 0.04) 100%);
        border: 1px solid rgba(37, 99, 235, 0.18);
        border-radius: 12px;
        margin-bottom: 20px;
    }
    .sidebar-brand-icon {
        font-size: 1.8rem;
    }
    .sidebar-brand-title {
        font-size: 1.05rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: #1E3A8A;
        line-height: 1.2;
    }
    .sidebar-brand-subtitle {
        font-size: 0.72rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Clean Card Surfaces */
    .studio-card {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 20px 24px !important;
        margin-bottom: 18px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.02) !important;
        transition: all 0.2s ease !important;
    }
    .studio-card:hover {
        border-color: #CBD5E1 !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06) !important;
    }

    /* Studio Script Editor Card */
    .script-editor-card {
        background: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 14px !important;
        padding: 18px 22px !important;
        margin-top: 14px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03), 0 8px 24px rgba(37, 99, 235, 0.03) !important;
        transition: all 0.25s ease !important;
    }
    .script-editor-card:focus-within {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12), 0 8px 24px rgba(37, 99, 235, 0.06) !important;
    }
    .script-editor-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        flex-wrap: wrap;
        gap: 10px;
    }
    .script-editor-title {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .script-editor-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 38px;
        height: 38px;
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.1) 0%, rgba(79, 70, 229, 0.08) 100%);
        border: 1px solid rgba(37, 99, 235, 0.22);
        border-radius: 10px;
        font-size: 1.25rem;
    }
    .script-editor-heading {
        font-size: 1.05rem;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: -0.01em;
        line-height: 1.2;
    }
    .script-editor-subheading {
        font-size: 0.78rem;
        color: #64748B;
        margin-top: 2px;
    }
    .script-live-stats {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }
    .script-stat-chip {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 5px 12px;
        border-radius: 8px;
        background: #F1F5F9;
        color: #334155;
        border: 1px solid #E2E8F0;
    }
    .script-stat-chip.active {
        background: #EFF6FF;
        color: #1D4ED8;
        border-color: #BFDBFE;
    }
    .script-editor-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px solid #F1F5F9;
        font-size: 0.78rem;
        color: #64748B;
        flex-wrap: wrap;
        gap: 8px;
    }

    /* Hero Header */
    .hero-container {
        padding: 6px 0 16px 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(37, 99, 235, 0.08);
        border: 1px solid rgba(37, 99, 235, 0.25);
        color: #2563EB;
        padding: 4px 14px;
        border-radius: 9999px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        width: fit-content;
    }
    .hero-title {
        font-size: 2.3rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #0F172A;
        line-height: 1.15;
        margin: 0;
    }
    .hero-desc {
        color: #475569;
        font-size: 1.02rem;
        line-height: 1.5;
        max-width: 920px;
        margin: 0;
    }
    .hero-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 4px;
    }
    .hero-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #F1F5F9;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 4px 12px;
        font-size: 0.78rem;
        color: #334155;
        font-weight: 600;
    }

    /* Stepper */
    .stepper-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 10px 18px;
        margin-bottom: 22px;
        overflow-x: auto;
        gap: 6px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
    }
    .step-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.82rem;
        font-weight: 600;
        color: #64748B;
        padding: 6px 14px;
        border-radius: 8px;
        transition: all 0.2s ease;
        white-space: nowrap;
    }
    .step-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        background: #F1F5F9;
        color: #64748B;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .step-item.active {
        color: #2563EB;
        background: rgba(37, 99, 235, 0.08);
        border: 1px solid rgba(37, 99, 235, 0.25);
    }
    .step-item.active .step-num {
        background: #2563EB;
        color: #FFFFFF;
    }
    .step-item.completed {
        color: #059669;
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.2);
    }
    .step-item.completed .step-num {
        background: #10B981;
        color: #FFFFFF;
    }
    .step-arrow {
        color: #CBD5E1;
        font-size: 0.75rem;
    }

    /* Section Headings */
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .section-badge {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        padding: 3px 9px;
        border-radius: 6px;
        background: rgba(37, 99, 235, 0.08);
        color: #2563EB;
        border: 1px solid rgba(37, 99, 235, 0.2);
    }

    /* InVideo AI Multi-Track Timeline Box */
    .timeline-container {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 22px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
    }
    .timeline-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #F1F5F9;
    }
    .timeline-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #1E293B;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .timeline-track-title {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748B;
        margin-bottom: 6px;
    }
    .timeline-track {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 6px;
    }
    .timeline-clip {
        flex: 1;
        min-width: 150px;
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        transition: all 0.2s ease;
    }
    .timeline-clip:hover {
        border-color: #93C5FD;
        background: #F1F5F9;
    }
    .timeline-clip-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .timeline-clip-label {
        font-size: 0.75rem;
        font-weight: 700;
        color: #0F172A;
    }
    .timeline-clip-dur {
        font-size: 0.72rem;
        font-weight: 700;
        color: #2563EB;
        background: #EFF6FF;
        border: 1px solid #DBEAFE;
        padding: 2px 6px;
        border-radius: 4px;
    }
    .timeline-clip-text {
        font-size: 0.73rem;
        color: #64748B;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Scene Header Banner */
    .scene-header-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #2563EB;
        border-radius: 10px;
        padding: 12px 18px;
        margin: 20px 0 12px 0;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
    }
    .scene-badge-num {
        background: linear-gradient(135deg, #2563EB, #4F46E5);
        color: white;
        font-weight: 800;
        font-size: 0.8rem;
        padding: 4px 10px;
        border-radius: 6px;
        letter-spacing: 0.03em;
    }
    .scene-quote {
        color: #1E293B;
        font-size: 0.95rem;
        font-weight: 600;
    }
    .scene-duration-badge {
        background: #F1F5F9;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 3px 10px;
        font-size: 0.78rem;
        color: #475569;
        font-weight: 600;
        white-space: nowrap;
    }

    /* Asset Grid & Card Styling */
    .asset-card-wrapper {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
    }
    .asset-card-wrapper:hover {
        border-color: #93C5FD;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.08);
    }
    .asset-card-selected {
        border: 2px solid #2563EB !important;
        background: rgba(37, 99, 235, 0.02) !important;
        box-shadow: 0 0 12px rgba(37, 99, 235, 0.15) !important;
    }
    .chip {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 5px;
        font-size: 0.72rem;
        font-weight: 700;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .chip-video {
        background: #EFF6FF;
        color: #1D4ED8;
        border: 1px solid #BFDBFE;
    }
    .chip-photo {
        background: #FAF5FF;
        color: #7E22CE;
        border: 1px solid #E9D5FF;
    }
    .chip-ai {
        background: #FEF3C7;
        color: #B45309;
        border: 1px solid #FDE68A;
    }
    .chip-conflict {
        background: #FFFBEB;
        color: #B45309;
        border: 1px solid #FCD34D;
    }
    .chip-match {
        background: #ECFDF5;
        color: #047857;
        border: 1px solid #A7F3D0;
    }

    /* Metric Cards */
    .metric-card-box {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
    }
    .metric-card-label {
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748B;
        margin-bottom: 6px;
    }
    .metric-card-val {
        font-size: 1.6rem;
        font-weight: 800;
        color: #0F172A;
        line-height: 1.2;
    }

    /* Streamlit Tab Enhancements */
    .stTabs [data-baseweb="tab-list"] {
        background: #F1F5F9 !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        padding: 5px 6px !important;
        gap: 6px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px !important;
        padding: 8px 18px !important;
        font-weight: 600 !important;
        color: #64748B !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }
    .stTabs [aria-selected="true"] {
        background: #FFFFFF !important;
        color: #2563EB !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06) !important;
    }

    /* Buttons */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #4F46E5 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        letter-spacing: 0.01em !important;
        padding: 0.55rem 1.25rem !important;
        box-shadow: 0 3px 12px rgba(37, 99, 235, 0.25) !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.35) !important;
    }
    div.stButton > button[kind="secondary"] {
        background: #FFFFFF !important;
        color: #1E293B !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.55rem 1.1rem !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background: #F8FAFC !important;
        border-color: #94A3B8 !important;
    }

    /* Inputs & Textareas */
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
        background-color: #FFFFFF !important;
        border-radius: 8px !important;
        border: 1px solid #CBD5E1 !important;
        color: #0F172A !important;
    }
    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600 !important;
        color: #0F172A !important;
    }

    /* Progress Bar */
    div[data-testid="stProgress"] > div > div > div > div {
        background: linear-gradient(90deg, #2563EB, #10B981) !important;
        border-radius: 8px !important;
    }

    /* Video Frame */
    div[data-testid="stVideo"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
    }

    /* ============================================================ */
    /* 📱 FULL RESPONSIVE & MOBILE APP ADAPTATIONS (<= 768px)       */
    /* ============================================================ */
    @media (max-width: 768px) {
        /* Remove wasteful desktop padding and fit to mobile edge */
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 2.5rem !important;
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            max-width: 100% !important;
        }

        /* Fluid Hero Section */
        .hero-container {
            padding: 4px 0 12px 0 !important;
            gap: 6px !important;
        }
        .hero-title {
            font-size: 1.55rem !important;
            line-height: 1.22 !important;
            letter-spacing: -0.02em !important;
        }
        .hero-desc {
            font-size: 0.85rem !important;
            line-height: 1.4 !important;
        }
        .hero-pill {
            font-size: 0.68rem !important;
            padding: 3px 10px !important;
        }
        .hero-chips {
            gap: 5px !important;
            margin-top: 2px !important;
        }
        .hero-chip {
            font-size: 0.72rem !important;
            padding: 3px 8px !important;
        }

        /* Compact Touch-Friendly Stepper with Horizontal Scroll */
        .stepper-container {
            padding: 8px 10px !important;
            gap: 4px !important;
            margin-bottom: 16px !important;
            -webkit-overflow-scrolling: touch !important;
            scrollbar-width: none !important;
        }
        .stepper-container::-webkit-scrollbar {
            display: none !important;
        }
        .step-item {
            padding: 5px 10px !important;
            font-size: 0.72rem !important;
            gap: 5px !important;
        }
        .step-num {
            width: 18px !important;
            height: 18px !important;
            font-size: 0.68rem !important;
        }
        .step-arrow {
            font-size: 0.65rem !important;
        }

        /* Responsive Studio Cards */
        .studio-card {
            padding: 14px 14px !important;
            margin-bottom: 14px !important;
            border-radius: 10px !important;
        }
        .section-title {
            font-size: 1.02rem !important;
            margin-bottom: 10px !important;
            flex-wrap: wrap !important;
            gap: 6px !important;
        }

        /* Scene Header Bar */
        .scene-header-bar {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 8px !important;
            padding: 10px 14px !important;
        }
        .scene-header-bar > div:first-child {
            flex-wrap: wrap !important;
            gap: 8px !important;
        }
        .scene-quote {
            font-size: 0.86rem !important;
            word-break: break-word !important;
        }
        .scene-duration-badge {
            align-self: flex-start !important;
        }

        /* Touch-Friendly Large Buttons */
        div.stButton > button {
            min-height: 44px !important;
            font-size: 0.88rem !important;
            touch-action: manipulation !important;
            -webkit-tap-highlight-color: transparent !important;
            border-radius: 8px !important;
        }

        /* Streamlit Tabs on Mobile */
        .stTabs [data-baseweb="tab-list"] {
            padding: 3px 4px !important;
            gap: 4px !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 6px 12px !important;
            font-size: 0.8rem !important;
            white-space: nowrap !important;
        }

        /* Touch Timeline Track */
        .timeline-container {
            padding: 12px !important;
            margin-bottom: 16px !important;
        }
        .timeline-track {
            -webkit-overflow-scrolling: touch !important;
            padding-bottom: 4px !important;
        }
        .timeline-clip {
            min-width: 130px !important;
            padding: 6px 8px !important;
        }

        /* Metric Cards on Mobile */
        .metric-card-box {
            padding: 10px 12px !important;
            border-radius: 10px !important;
            margin-bottom: 6px !important;
        }
        .metric-card-val {
            font-size: 1.25rem !important;
        }
        .metric-card-label {
            font-size: 0.68rem !important;
        }

        /* Mobile Asset Cards */
        .asset-card-wrapper {
            padding: 12px !important;
        }

        /* Sidebar Branding on Mobile */
        .sidebar-brand-card {
            padding: 10px 12px !important;
            margin-bottom: 14px !important;
        }

        /* Script Editor on Mobile */
        .script-editor-card {
            padding: 12px 14px !important;
            border-radius: 12px !important;
        }
        .script-editor-header {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 8px !important;
        }
        .script-editor-heading {
            font-size: 0.95rem !important;
        }
        .script-editor-subheading {
            font-size: 0.74rem !important;
        }
        .script-editor-footer {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 6px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def slugify(text: str) -> str:
    return (re.sub(r'[^A-Za-z0-9]+', '_', str(text)).strip('_') or 'asset')[:50]

def safe_search_assets(
    query: str,
    key: str = DEFAULT_PIXABAY_KEY,
    media_type: str = "both",
    orientation: str = "horizontal",
    per_page: int = 10,
    sentence: str = "",
    openai_key: str = DEFAULT_OPENAI_KEY,
    dalle_prompt: str = ""
):
    try:
        return search_assets(
            query=query,
            key=key,
            media_type=media_type,
            orientation=orientation,
            per_page=per_page,
            sentence=sentence,
            openai_key=openai_key,
            dalle_prompt=dalle_prompt
        )
    except TypeError:
        return search_assets(query=query, key=key, media_type=media_type, orientation=orientation, per_page=per_page)

def render_pipeline_stepper(current_stage: int):
    """Renders clean light responsive 5-step workflow tracker."""
    steps = [
        ("1", "📝 Script & Storyboard", 1),
        ("2", "🎬 Timeline & Durations", 2),
        ("3", "🔍 Asset Selector", 3),
        ("4", "⚡ Render Engine", 4),
        ("5", "📥 Final Export", 5)
    ]
    html_parts = ['<div class="stepper-container">']
    for idx, (num, label, step_val) in enumerate(steps):
        if step_val < current_stage:
            cls = "step-item completed"
            icon = "✓"
        elif step_val == current_stage:
            cls = "step-item active"
            icon = num
        else:
            cls = "step-item"
            icon = num
        html_parts.append(f'<div class="{cls}"><span class="step-num">{icon}</span><span>{label}</span></div>')
        if idx < len(steps) - 1:
            html_parts.append('<span class="step-arrow">➔</span>')
    html_parts.append('</div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand-card">
        <div class="sidebar-brand-icon">🎬</div>
        <div>
            <div class="sidebar-brand-title">VideoCraft Studio</div>
            <div class="sidebar-brand-subtitle">InVideo AI Creator Engine</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🔑 API Authentication")
    pixabay_key = st.text_input(
        "Pixabay API Key",
        value=DEFAULT_PIXABAY_KEY,
        type="password",
        help="Pixabay stock footage key."
    )
    if pixabay_key:
        st.markdown('<span class="chip chip-match">🟢 Pixabay Connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="chip chip-conflict">⚠️ Pixabay Key Required</span>', unsafe_allow_html=True)

    openai_key = st.text_input(
        "OpenAI API Key (DALL-E Visual Fallback)",
        value=DEFAULT_OPENAI_KEY,
        type="password",
        help="Used to generate custom photorealistic images when Pixabay clips are not found."
    )
    if openai_key:
        st.markdown('<span class="chip chip-ai">✨ OpenAI DALL-E Fallback Active</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📐 Video Output Settings")
    format_choice = st.selectbox(
        "Resolution & Aspect Ratio",
        options=[
            "16:9 Landscape (1920x1080 - YouTube)",
            "9:16 Portrait (1080x1920 - Shorts/Reels)",
            "1:1 Square (1080x1080 - Social)"
        ],
        index=0
    )
    
    if "16:9" in format_choice:
        target_w, target_h = 1920, 1080
        orientation = "horizontal"
    elif "9:16" in format_choice:
        target_w, target_h = 1080, 1920
        orientation = "vertical"
    else:
        target_w, target_h = 1080, 1080
        orientation = "all"

    fit_mode = st.radio(
        "Framing Mode",
        options=["cover", "fit"],
        format_func=lambda x: "Crop & Fill (No black bars)" if x == "cover" else "Fit & Pad (Preserve ratio)",
        index=0
    )

    auto_generate_shorts = False

    st.markdown("---")
    st.markdown("### ⚡ Creator Pacing & Speech Speed")
    speed_mode = st.selectbox(
        "Voiceover & Visual Pace",
        options=[
            "1.25x Top Creator Fast (Punchy & Viral)",
            "1.00x Normal Speech (Traditional)",
            "1.15x Energetic YouTube Pace",
            "1.35x Hyper Fast Pacing"
        ],
        index=0,
        help="1.25x pace prevents boring robotic pauses and keeps viewers hooked (Top YouTuber standard)."
    )
    if "1.25x" in speed_mode:
        speed_multiplier = 1.25
        tts_rate_str = "+25%"
    elif "1.15x" in speed_mode:
        speed_multiplier = 1.15
        tts_rate_str = "+15%"
    elif "1.35x" in speed_mode:
        speed_multiplier = 1.35
        tts_rate_str = "+35%"
    else:
        speed_multiplier = 1.0
        tts_rate_str = "+0%"

    st.markdown("---")
    st.markdown("### 🎙️ Human AI Voiceover")
    if "enable_voiceover" not in st.session_state:
        st.session_state.enable_voiceover = True
    if "selected_voice" not in st.session_state:
        st.session_state.selected_voice = DEFAULT_VOICE

    active_v_code = st.session_state.get("selected_voice", DEFAULT_VOICE)
    active_v_name = VOICE_CATALOG.get(active_v_code, active_v_code)
    st.markdown(f"""
    <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px; padding:10px 12px; margin-bottom:8px;">
        <div style="font-size:0.72rem; color:#166534; font-weight:700;">🟢 ACTIVE SPEECH MODEL ({speed_mode.split(' ')[0]}):</div>
        <div style="font-size:0.82rem; color:#0F172A; font-weight:600; margin-top:3px; line-height:1.3;">
            {active_v_name}
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("✨ Change voice model & test audio samples in **Step 1 (Main Page)**.")

    st.markdown("---")
    st.markdown("### ⏱️ Audio-Driven Sync & Transitions")
    st.markdown("""
    <div style="background:#EFF6FF; padding:10px 12px; border-radius:8px; border:1px solid #BFDBFE; font-size:0.75rem; color:#1E40AF; margin-bottom:10px; line-height:1.4;">
        🎯 <strong>Audio-Driven Pacing:</strong> Visual clips & images change strictly according to voice narration length (+ natural pause buffer). No dead silence gaps!
    </div>
    """, unsafe_allow_html=True)
    pause_buffer = st.slider(
        "Sentence Breath Buffer (s)",
        min_value=0.10,
        max_value=0.60,
        value=0.20,
        step=0.05,
        help="Natural breathing space after each line so sentences never feel cut off."
    )
    pacing_mode = "audio_driven"
    default_duration = 3.5

    st.markdown("---")
    st.markdown("### 🎵 Background Music (BGM)")
    bgm_options = list(BGM_CATALOG.keys()) + ["custom_upload"]
    selected_bgm_key = st.selectbox(
        "Suspense / Cinematic Track",
        options=bgm_options,
        format_func=lambda k: "📁 Upload Custom Track (.mp3)" if k == "custom_upload" else BGM_CATALOG.get(k, {}).get("name", k),
        index=0
    )

    custom_bgm_file = None
    if selected_bgm_key == "custom_upload":
        custom_bgm_file = st.file_uploader("Upload MP3 / WAV Music Track", type=["mp3", "wav"])
    elif selected_bgm_key != "none":
        bgm_fname = BGM_CATALOG[selected_bgm_key]["filename"]
        track_local_p = BGM_DIR / bgm_fname
        if track_local_p.exists():
            st.caption(f"🎧 Preview ({BGM_CATALOG[selected_bgm_key]['mood']}):")
            st.audio(str(track_local_p), format="audio/mp3")

    bgm_volume = st.slider(
        "BGM Volume (Ducked under Voice)",
        min_value=0.02,
        max_value=0.40,
        value=BGM_CATALOG.get(selected_bgm_key, {}).get("default_volume", 0.12),
        step=0.01,
        format="%.2f",
        disabled=(selected_bgm_key == "none"),
        help="Keeps voice narration 100% crystal-clear while suspense music sets the mood."
    )

    st.markdown("---")
    st.markdown("### 🖼️ Ken Burns Photo Motion")
    ken_burns_style = st.selectbox(
        "Image Zoom / Pan Effect",
        [
            "Dynamic Auto (Rotate Zoom & Pan)",
            "Smooth Zoom In (Center Push)",
            "Smooth Zoom Out (Reveal)",
            "Cinematic Pan (Left to Right)",
            "Cinematic Pan (Right to Left)"
        ],
        index=0,
        help="Cinematic documentary camera movement applied to still photos."
    )

    st.markdown("---")
    st.markdown("### 🔢 Scene Badges & Subtitles")
    burn_badge = st.checkbox("Burn Scene Number Badge on Video", value=True)
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        badge_style = st.selectbox("Badge Style", ["Pill (#01)", "Scene Name (Scene 01)", "Minimal (01)"])
    with col_b2:
        badge_position = st.selectbox("Badge Position", ["Top Left", "Top Right", "Bottom Left", "Bottom Right"])

    burn_subtitles = st.checkbox("Burn Script Subtitles on Video", value=True)
    subtitle_style_choice = st.selectbox(
        "Subtitle Aesthetic Style",
        [
            "🔥 Creator Viral (Yellow/White Accent + Stroke)",
            "🎬 Studio Box (Translucent Dark Banner)",
            "✨ Minimal Clean (Drop Shadow)"
        ],
        index=0,
        help="Top YouTubers use Creator Viral with bold yellow trigger words for max retention."
    )

    st.markdown("---")
    st.markdown("""
    <div style="background:#F1F5F9; padding:10px 12px; border-radius:8px; border:1px solid #E2E8F0; font-size:0.75rem; color:#475569;">
        <strong style="color:#2563EB;">⚡ Engine:</strong> Top Creator 1.25x Studio Pipeline · FFmpeg 7.1 H.264 · Ken Burns Zoom
    </div>
    """, unsafe_allow_html=True)

# --- MAIN APP HEADER ---
st.markdown("""
<div class="hero-container">
    <div class="hero-pill">⚡ INVIDEO AI STUDIO ENGINE · LIGHT THEME EDITION</div>
    <h1 class="hero-title">AI Script-to-Video Studio</h1>
    <p class="hero-desc">
        Create professional InVideo-grade videos from any script. Scenario-based stock matching, 
        automatic 60% video / 40% photo mix, dynamic speech-paced durations, and OpenAI DALL-E fallback generation.
    </p>
    <div class="hero-chips">
        <span class="hero-chip">🎯 Scenario-Wise Context Search</span>
        <span class="hero-chip">🎥 60% Video / 40% Image Mix</span>
        <span class="hero-chip">⏱️ Dynamic Content-Dependent Pacing</span>
        <span class="hero-chip">✨ OpenAI DALL-E Image Fallback</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Determine current pipeline stage for visual stepper
current_stage = 1
if st.session_state.get("merged_video"):
    current_stage = 5
elif st.session_state.get("scene_assets"):
    current_stage = 3
elif st.session_state.get("parsed_scenes"):
    current_stage = 2

render_pipeline_stepper(current_stage)

# Voice Model Selection Modal Dialog
if hasattr(st, "dialog"):
    @st.dialog("🎙️ Choose Script Speech Model & Voice Narrator")
    def open_voice_selection_dialog():
        st.markdown("""
        <div style="font-size:0.86rem; color:#475569; margin-bottom:14px; line-height:1.4;">
            Select an AI voice narrator model for your script. Listen to a live sample before confirming!
        </div>
        """, unsafe_allow_html=True)

        lang_tab1, lang_tab2 = st.tabs(["🇮🇳 Hindi / Indian Voices", "🇺🇸 English Voices"])

        with lang_tab1:
            hindi_voices = {k: v for k, v in VOICE_CATALOG.items() if "hi-IN" in k}
            curr_v = st.session_state.get("selected_voice", DEFAULT_VOICE)
            h_idx = list(hindi_voices.keys()).index(curr_v) if curr_v in hindi_voices else 0
            h_choice = st.radio(
                "Select Hindi Voice Model:",
                options=list(hindi_voices.keys()),
                format_func=lambda k: hindi_voices[k],
                index=h_idx,
                key="dialog_hindi_voice"
            )
            col_dh1, col_dh2 = st.columns(2)
            with col_dh1:
                if st.button("🎧 Listen Hindi Sample", key="dialog_btn_h_sample", use_container_width=True):
                    sample_p = DOWNLOADS_DIR / f"sample_{h_choice}.mp3"
                    with st.spinner("Synthesizing Hindi sample..."):
                        dur = generate_human_voiceover("Namaste dosto. Yeh voiceover aapke YouTube video ke liye ready hai.", sample_p, voice=h_choice)
                        if sample_p.exists():
                            st.audio(str(sample_p), format="audio/mp3")
            with col_dh2:
                if st.button("✅ Apply Hindi Voice", type="primary", key="btn_apply_hindi", use_container_width=True):
                    st.session_state.selected_voice = h_choice
                    st.success(f"Selected: {VOICE_CATALOG.get(h_choice, h_choice)}!")
                    st.rerun()

        with lang_tab2:
            eng_voices = {k: v for k, v in VOICE_CATALOG.items() if "en-" in k}
            curr_v = st.session_state.get("selected_voice", DEFAULT_VOICE)
            e_idx = list(eng_voices.keys()).index(curr_v) if curr_v in eng_voices else 0
            e_choice = st.radio(
                "Select English Voice Model:",
                options=list(eng_voices.keys()),
                format_func=lambda k: eng_voices[k],
                index=e_idx,
                key="dialog_eng_voice"
            )
            col_de1, col_de2 = st.columns(2)
            with col_de1:
                if st.button("🎧 Listen English Sample", key="dialog_btn_e_sample", use_container_width=True):
                    sample_p = DOWNLOADS_DIR / f"sample_{e_choice}.mp3"
                    with st.spinner("Synthesizing English sample..."):
                        dur = generate_human_voiceover("Hello creator. This realistic human voiceover is ready for your YouTube video.", sample_p, voice=e_choice)
                        if sample_p.exists():
                            st.audio(str(sample_p), format="audio/mp3")
            with col_de2:
                if st.button("✅ Apply English Voice", type="primary", key="btn_apply_eng", use_container_width=True):
                    st.session_state.selected_voice = e_choice
                    st.success(f"Selected: {VOICE_CATALOG.get(e_choice, e_choice)}!")
                    st.rerun()
else:
    def open_voice_selection_dialog():
        st.info("Please use the Voice dropdown directly in Step 1.")

def run_full_auto_video_pipeline(
    script_text: str,
    main_topic: str,
    media_pref: str,
    speed_mult: float,
    tts_rate: str,
    voice_name: str,
    do_voice: bool,
    pb_key: str,
    ai_key: str,
    tw: int,
    th: int,
    orient: str,
    fit_m: str,
    kb_style: str,
    b_badge: bool,
    b_style: str,
    b_pos: str,
    b_subs: bool,
    sub_style: str,
    p_buffer: float,
    bgm_k: str,
    custom_bgm,
    bgm_vol: float,
    niche_k: str,
    status_container,
    render_bar,
    existing_scenes=None,
    existing_scene_assets=None,
    existing_selected_assets=None
):
    """
    Automates complete end-to-end video production in background:
    1. Parses script to scenes (or uses existing)
    2. Parallel search for unique 1080p clips & AI visual fallback
    3. Multi-worker pre-fetch for downloads, voiceover & subtitle overlays
    4. Multi-core scene rendering
    5. Final video merge & BGM ducking
    6. Numbered assets ZIP & Dynamic YouTube SEO Kit
    """
    cleanup_storage_cache()
    job_timestamp = time.strftime('%Y%m%d_%H%M%S')
    job_dir = DOWNLOADS_DIR / f"job_{job_timestamp}"
    job_dir.mkdir(parents=True, exist_ok=True)

    # 1. SCENES
    if existing_scenes:
        scenes = existing_scenes
    else:
        status_container.info("📝 [1/4] Analyzing script into story scenes...")
        render_bar.progress(0.05)
        scenes = parse_script_to_scenes(
            script_text,
            default_duration=3.5,
            default_media=media_pref,
            speed=speed_mult,
            main_topic=main_topic
        )
    if not scenes:
        status_container.error("❌ Failed to parse script into scenes.")
        return None

    # 2. ASSET SEARCH & SELECTION (100% in Background)
    if existing_scene_assets and existing_selected_assets:
        scene_assets_dict = existing_scene_assets
        selected_assets_dict = existing_selected_assets
    else:
        status_container.info(f"🔍 [2/4] Finding unique 1080p clips & AI visuals for {len(scenes)} scenes in parallel...")
        render_bar.progress(0.15)

        def _search_worker(item):
            idx, sc_item = item
            m_type_to_search = sc_item.get('media_pref', 'both')
            res = safe_search_assets(
                query=sc_item['keyword'],
                key=pb_key,
                media_type=m_type_to_search,
                orientation=orient,
                per_page=10,
                sentence=sc_item['text'],
                openai_key=ai_key,
                dalle_prompt=sc_item.get('dalle_prompt', '')
            )
            if not res and m_type_to_search != "both":
                res = safe_search_assets(
                    query=sc_item['keyword'],
                    key=pb_key,
                    media_type="both",
                    orientation=orient,
                    per_page=10,
                    sentence=sc_item['text'],
                    openai_key=ai_key,
                    dalle_prompt=sc_item.get('dalle_prompt', '')
                )
            if not res:
                ai_asset = generate_ai_image(
                    prompt=sc_item.get('dalle_prompt') or sc_item['text'],
                    openai_key=ai_key
                )
                if ai_asset:
                    res = [ai_asset]
            return idx, sc_item, (res or [])

        search_items = list(enumerate(scenes))
        total_s = len(search_items)
        completed_results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(_search_worker, item): item[0] for item in search_items}
            done_count = 0
            for fut in as_completed(futures):
                try:
                    completed_results.append(fut.result())
                except Exception:
                    orig_idx = futures[fut]
                    completed_results.append((orig_idx, scenes[orig_idx], []))
                done_count += 1
                render_bar.progress(0.15 + (done_count / total_s) * 0.15)

        completed_results.sort(key=lambda x: x[0])
        scene_assets_dict = {}
        selected_assets_dict = {}
        used_asset_ids = set()
        for idx, sc, results in completed_results:
            scene_assets_dict[sc['no']] = results
            pick_idx, chosen_asset = pick_unique_candidate(results, used_asset_ids)
            if chosen_asset:
                used_asset_ids.add(chosen_asset.get('id'))
                sc['duration'] = round(float(sc.get('duration', estimate_speech_duration(sc['text'], speed=speed_mult))), 1)
            selected_assets_dict[sc['no']] = max(0, pick_idx)

    total_scenes = len(scenes)

    # 3. PHASE 1: PRE-FETCH (Media + Voiceover + Overlays)
    status_container.info("🎙️ [3/4] Synthesizing human voice narration & downloading visuals...")
    render_bar.progress(0.35)

    def _prep_single_scene(idx_scene):
        i, sc = idx_scene
        sc_no = sc['no']
        assets = scene_assets_dict.get(sc_no, [])
        candidate_queue = []
        sel_idx = selected_assets_dict.get(sc_no, 0)
        if assets:
            primary_asset = assets[min(sel_idx, len(assets) - 1)]
            candidate_queue.append(primary_asset)
            for a_idx, a in enumerate(assets):
                if a_idx != min(sel_idx, len(assets) - 1):
                    candidate_queue.append(a)

        raw_path = None
        chosen_asset = None
        for c_idx, cand in enumerate(candidate_queue):
            ext = ".jpg" if cand.get('type') == 'image' else ".mp4"
            safe_slug = slugify(sc.get('keyword', 'asset'))
            try_filename = f"raw_{sc_no}_{c_idx}_{safe_slug}{ext}"
            try_path = job_dir / try_filename
            dl_url = cand.get('download', '')
            if dl_url and download_file(dl_url, try_path) and try_path.exists() and try_path.stat().st_size > 1000:
                raw_path = try_path
                chosen_asset = cand
                break

        # Fallback Tier 1: AI visual
        if not raw_path or not raw_path.exists():
            ai_path = job_dir / f"raw_{sc_no}_ai_fallback.jpg"
            prompt = sc.get('dalle_prompt') or f"{sc.get('keyword', '')} {sc.get('scenario', '')} {sc.get('text', '')}".strip()
            ai_res = generate_ai_image(prompt=prompt, openai_key=ai_key, dest_path=ai_path)
            if ai_path.exists() and ai_path.stat().st_size > 500:
                raw_path = ai_path
                chosen_asset = ai_res or {
                    "type": "image",
                    "source": "AI Image Engine",
                    "download": str(ai_path),
                    "id": f"ai_gen_{sc_no}"
                }

        # Fallback Tier 2: Slide card
        if not raw_path or not raw_path.exists():
            card_path = job_dir / f"raw_{sc_no}_card.jpg"
            create_fallback_slide(
                output_path=card_path,
                width=tw,
                height=th,
                title=f"Scene {sc_no}: {sc.get('keyword', '').title()}",
                text=sc.get('text', '')
            )
            raw_path = card_path
            chosen_asset = {
                "type": "image",
                "source": "Studio Graphic Slide",
                "download": str(card_path),
                "id": f"slide_{sc_no}"
            }

        is_img = (chosen_asset.get('type') == 'image')

        # Synthesize natural human speech voiceover audio
        audio_path = None
        if do_voice and sc.get('text', '').strip():
            voice_file = job_dir / f"voice_{sc_no}.mp3"
            voice_dur = generate_human_voiceover(sc['text'], voice_file, voice=voice_name, rate=tts_rate)
            if not (voice_dur and voice_file.exists() and voice_file.stat().st_size > 500):
                backup_voice = "hi-IN-MadhurNeural" if "hi-IN" not in voice_name else "en-US-ChristopherNeural"
                voice_dur = generate_human_voiceover(sc['text'], voice_file, voice=backup_voice, rate=tts_rate)

            if voice_dur and voice_file.exists() and voice_file.stat().st_size > 500:
                audio_path = voice_file
                scene_dur = round(max(1.8, voice_dur + p_buffer), 2)
            else:
                scene_dur = round(float(sc.get('duration', estimate_speech_duration(sc['text'], speed=speed_mult))), 2)
        else:
            scene_dur = round(float(sc.get('duration', estimate_speech_duration(sc['text'], speed=speed_mult))), 2)

        # Generate visual overlay image
        overlay_path = None
        if b_badge or b_subs:
            overlay_path = job_dir / f"overlay_{sc_no}.png"
            create_overlay_image(
                width=tw,
                height=th,
                scene_no=sc_no,
                output_png=overlay_path,
                scene_text=sc['text'] if b_subs else None,
                show_badge=b_badge,
                badge_style=b_style,
                badge_position=b_pos,
                show_subtitle=b_subs,
                subtitle_style=sub_style
            )

        return {
            "index": i,
            "sc": sc,
            "sc_no": sc_no,
            "raw_path": raw_path,
            "is_img": is_img,
            "audio_path": audio_path,
            "scene_dur": scene_dur,
            "overlay_path": overlay_path
        }

    prep_results = []
    numbered_assets_for_zip = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures_prep = {executor.submit(_prep_single_scene, (i, sc)): i for i, sc in enumerate(scenes)}
        done_prep = 0
        for fut in as_completed(futures_prep):
            try:
                res_p = fut.result()
                prep_results.append(res_p)
            except Exception as prep_err:
                print(f"Pre-fetch error for scene: {prep_err}")
            done_prep += 1
            render_bar.progress(0.35 + (done_prep / total_scenes) * 0.25)

    prep_results.sort(key=lambda x: x["index"])
    for pr in prep_results:
        if pr.get("raw_path"):
            numbered_assets_for_zip.append(pr["raw_path"])
        if pr.get("audio_path"):
            numbered_assets_for_zip.append(pr["audio_path"])

    # 4. PHASE 2: VIDEO ENCODING
    status_container.info("🎬 [4/4] Multi-core video rendering & merging final video...")
    render_bar.progress(0.60)

    def _encode_single_scene(prep_data):
        i = prep_data["index"]
        sc = prep_data["sc"]
        sc_no = prep_data["sc_no"]
        raw_path = prep_data["raw_path"]
        is_img = prep_data["is_img"]
        audio_path = prep_data["audio_path"]
        scene_dur = prep_data["scene_dur"]
        overlay_path = prep_data["overlay_path"]
        clip_path = job_dir / f"{sc_no}_scene.mp4"

        ok = safe_process_scene_clip(
            media_path=raw_path,
            output_path=clip_path,
            target_w=tw,
            target_h=th,
            duration=scene_dur,
            is_image=is_img,
            overlay_path=overlay_path,
            audio_path=audio_path,
            fit_mode=fit_m,
            ken_burns_style=kb_style,
            scene_index=i
        )

        if not ok or not clip_path.exists() or clip_path.stat().st_size == 0:
            fb_slide = job_dir / f"raw_{sc_no}_enc_fallback.jpg"
            create_fallback_slide(
                output_path=fb_slide,
                width=tw,
                height=th,
                title=f"Scene {sc_no}: {sc.get('keyword', '').title()}",
                text=sc.get('text', '')
            )
            ok = safe_process_scene_clip(
                media_path=fb_slide,
                output_path=clip_path,
                target_w=tw,
                target_h=th,
                duration=scene_dur,
                is_image=True,
                overlay_path=overlay_path,
                audio_path=audio_path,
                fit_mode=fit_m,
                ken_burns_style=kb_style,
                scene_index=i
            )

        return i, clip_path, ok

    encoded_clips = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures_enc = {executor.submit(_encode_single_scene, pd): pd["index"] for pd in prep_results}
        done_enc = 0
        for fut in as_completed(futures_enc):
            try:
                i_res, cp_res, ok_res = fut.result()
                encoded_clips.append((i_res, cp_res, ok_res))
            except Exception as enc_err:
                print(f"Encoding error: {enc_err}")
            done_enc += 1
            render_bar.progress(0.60 + (done_enc / total_scenes) * 0.30)

    encoded_clips.sort(key=lambda x: x[0])
    processed_clips = [cp for i_idx, cp, ok_val in encoded_clips if ok_val and cp.exists() and cp.stat().st_size > 0]
    if not processed_clips or len(processed_clips) != len(prep_results):
        status_container.error("❌ Error during scene encoding.")
        return None

    # Merge
    status_container.info("🎬 Merging scene clips with seamless cuts...")
    raw_merged_file = job_dir / f"scenes_merged_{job_timestamp}.mp4"
    merge_clips_to_final_video(processed_clips, raw_merged_file)
    render_bar.progress(0.92)

    final_merged_file = DOWNLOADS_DIR / f"merged_video_{job_timestamp}.mp4"

    active_bgm_path = None
    if bgm_k == "custom_upload" and custom_bgm:
        custom_p = job_dir / f"custom_bgm_{custom_bgm.name}"
        with open(custom_p, "wb") as bf:
            bf.write(custom_bgm.getbuffer())
        active_bgm_path = custom_p
    elif bgm_k != "none" and bgm_k in BGM_CATALOG:
        cand_bgm = BGM_DIR / BGM_CATALOG[bgm_k]["filename"]
        if cand_bgm.exists():
            active_bgm_path = cand_bgm

    if active_bgm_path and active_bgm_path.exists():
        bgm_label = BGM_CATALOG.get(bgm_k, {}).get("name", "Suspense Track")
        status_container.info(f"🎵 Mixing background music ({bgm_label}) under narration...")
        bgm_ok = add_background_music_to_video(
            video_path=raw_merged_file,
            bgm_path=active_bgm_path,
            output_path=final_merged_file,
            bgm_volume=bgm_vol,
            fade_out_duration=2.0
        )
        if not bgm_ok or not final_merged_file.exists():
            shutil.copy2(raw_merged_file, final_merged_file)
    else:
        shutil.copy2(raw_merged_file, final_merged_file)

    # ZIP
    status_container.info("📦 Packaging assets into numbered ZIP archive...")
    zip_file = DOWNLOADS_DIR / f"assets_{job_timestamp}.zip"
    make_numbered_zip(processed_clips + numbered_assets_for_zip, zip_file)
    render_bar.progress(0.96)

    # SEO Kit
    status_container.info("🚀 Generating Dynamic YouTube Upload Kit & SEO...")
    active_top = main_topic or (scenes[0].get('keyword') if scenes else "YouTube Video")
    seo_kit = generate_youtube_seo_kit(
        topic=active_top,
        script_text=script_text,
        scenes=scenes,
        niche_key=niche_k
    )

    render_bar.progress(1.0)
    status_container.success("🎉 Video generation complete!")

    return {
        "merged_video": str(final_merged_file),
        "assets_zip": str(zip_file),
        "youtube_seo_kit": seo_kit,
        "parsed_scenes": scenes,
        "scene_assets": scene_assets_dict,
        "selected_assets": selected_assets_dict
    }

# Main Studio Tabs
tab1, tab2 = st.tabs(["📝 Script to Merged Video Studio", "📊 CSV Batch Asset Finder"])

# =====================================================================
# TAB 1: SCRIPT TO MERGED VIDEO STUDIO
# =====================================================================
with tab1:
    # STEP 1: Input Script & Storyboard
    st.markdown("""
    <div class="section-title">
        <span>Step 1: Input Script & Storyboard</span>
        <span class="section-badge">Script Engine</span>
    </div>
    """, unsafe_allow_html=True)

    # AI Creator Viral Script & Shorts Generator Tool
    with st.expander("🔥 AI Top Creator Viral Script & Shorts Generator (Instant Hooks)", expanded=False):
        st.markdown("""
        <div style="font-size:0.86rem; color:#475569; margin-bottom:12px; line-height:1.4;">
            Type any video topic or niche. The AI will create a <strong>high-retention Long Script with a psychological hook</strong>, 
            plus <strong>4 distinct YouTube Shorts scripts</strong> with extreme swipe-stopping hooks!
        </div>
        """, unsafe_allow_html=True)
        col_gen1, col_gen2 = st.columns([3, 1])
        with col_gen1:
            creator_topic_input = st.text_input(
                "Enter Video Topic / Idea:",
                value=st.session_state.get("current_topic", ""),
                placeholder="e.g., Dark Secrets of the Pyramids, Why 99% Fail at AI, Psychology of Money, Lost City of Atlantis",
                key="input_creator_topic"
            )
        with col_gen2:
            creator_lang = st.selectbox("Language / Style:", ["🇮🇳 Hinglish / Hindi (Viral)", "🇺🇸 English (Creator Documentary)"], index=0)

        if st.button("🚀 Generate Viral Script + 4 Triggering Shorts Hooks", type="primary", use_container_width=True, key="btn_gen_creator_script"):
            if not creator_topic_input.strip():
                st.warning("Please type a topic first.")
            else:
                with st.spinner("⚡ Crafting high-retention Creator script & 4 Shorts hooks..."):
                    lang_str = "Hinglish" if "Hinglish" in creator_lang else "English"
                    gen_res = generate_creator_scripts_and_shorts(creator_topic_input, language=lang_str, openai_key=openai_key)
                    st.session_state.generated_creator_pack = gen_res
                    st.session_state.current_topic = gen_res["topic"]
                    st.session_state.active_script_content = gen_res["long_script"]
                    st.session_state.creator_shorts_drafts = gen_res["shorts"]
                    st.success(f"🎉 Generated Viral Long Script + 4 Triggering Shorts Hooks for '{creator_topic_input}'!")
                    st.rerun()

        if st.session_state.get("generated_creator_pack"):
            pack = st.session_state.generated_creator_pack
            st.markdown(f"**🎯 Active Topic:** `{pack.get('topic', '')}` · <span class='chip chip-match'>✅ Script Loaded into Editor Below</span>", unsafe_allow_html=True)
            st.markdown("##### 📱 4 Generated YouTube Shorts Hooks (Ready to Render):")
            sh_cols = st.columns(4)
            for s_idx, sh in enumerate(pack.get("shorts", [])[:4]):
                with sh_cols[s_idx]:
                    st.markdown(f"""
                    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px; font-size:0.78rem; height:100%;">
                        <div style="font-weight:700; color:#2563EB; margin-bottom:3px;">{sh.get('title', f'Short #{s_idx+1}')}</div>
                        <div style="font-size:0.72rem; color:#059669; font-weight:600; margin-bottom:5px;">{sh.get('hook_type', 'Hook')}</div>
                        <div style="color:#475569; font-style:italic; line-height:1.3;">"{sh.get('script', '')[:105]}..."</div>
                    </div>
                    """, unsafe_allow_html=True)

    # -------------------------------------------------------------
    # 🎛️ MASTER FACELESS CHANNEL NICHE ENGINE
    # -------------------------------------------------------------
    niche_keys = list(NICHE_CATALOG.keys())
    cur_niche_k = st.session_state.get("selected_niche", "history")
    cur_niche_idx = niche_keys.index(cur_niche_k) if cur_niche_k in niche_keys else 0

    col_niche_sel, col_niche_badge = st.columns([3, 2])
    with col_niche_sel:
        selected_niche_name = st.selectbox(
            "🎛️ Master YouTube Faceless Niche Mode:",
            options=[NICHE_CATALOG[k]["name"] for k in niche_keys],
            index=cur_niche_idx,
            help="Switches visual search bias, cinematic BGM, voice speed, and presets to this exact YouTube niche!"
        )
        for k, v in NICHE_CATALOG.items():
            if v["name"] == selected_niche_name:
                active_niche_k = k
                break
        else:
            active_niche_k = "history"

        if st.session_state.get("selected_niche") != active_niche_k:
            st.session_state.selected_niche = active_niche_k
            st.rerun()

    active_niche_data = NICHE_CATALOG.get(active_niche_k, NICHE_CATALOG["history"])

    with col_niche_badge:
        st.markdown(f"""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:8px 14px; margin-top:2px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:2px;">
                <span style="font-size:0.75rem; font-weight:700; color:#64748B;">ACTIVE ENGINE:</span>
                <span style="font-size:0.72rem; font-weight:800; background:{active_niche_data.get('accent_color', '#F59E0B')}20; color:{active_niche_data.get('badge_color', '#D97706')}; padding:2px 8px; border-radius:6px; border:1px solid {active_niche_data.get('accent_color', '#F59E0B')}50;">
                    {active_niche_data.get('badge', 'MASTER')}
                </span>
            </div>
            <div style="font-size:0.74rem; color:#334155;">
                🎵 <strong>BGM:</strong> {active_niche_data.get('default_bgm', 'Stormfront')} · ⚡ <strong>Pace:</strong> {active_niche_data.get('speed_mode', '1.25x').split(' ')[0]}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Studio Controls Toolbar: Topic Anchor, Story Presets, Reset
    col_top1, col_top2, col_top3 = st.columns([2.2, 2.2, 1.2])
    with col_top1:
        main_topic_input = st.text_input(
            "🎯 Main Video Topic (Hook Focus):",
            value=st.session_state.get("custom_main_topic", ""),
            placeholder=f"e.g., {active_niche_data['thumbnail_hooks'][0].title()}...",
            help="Anchor Scene 1 opening visual strictly to this topic so it showcases a high-impact Hero visual!"
        )
        st.session_state.custom_main_topic = main_topic_input

    niche_presets_dict = active_niche_data.get("presets", {})
    all_preset_options = ["(Custom Script)", *list(niche_presets_dict.keys()), *list(SAMPLE_PRESETS.keys())]

    with col_top2:
        preset_choice = st.selectbox(
            "💡 Load Story Preset / Template:",
            all_preset_options,
            help="Choose an inspirational story preset or compose your own script below."
        )

    with col_top3:
        st.write("")
        if st.button("🔄 Reset", use_container_width=True, help="Clear script and restart"):
            for k in ["parsed_scenes", "scene_assets", "selected_assets", "merged_video", "assets_zip", "active_script_content", "creator_shorts_drafts", "generated_shorts_list", "generated_creator_pack", "custom_main_topic", "youtube_seo_kit", "youtube_thumbnail"]:
                st.session_state.pop(k, None)
            st.rerun()

    if preset_choice != "(Custom Script)":
        if preset_choice in niche_presets_dict:
            initial_script = niche_presets_dict[preset_choice]
        else:
            initial_script = SAMPLE_PRESETS.get(preset_choice, "")
    else:
        initial_script = st.session_state.get("active_script_content", "")

    # Live calculate script stats
    curr_script_preview = initial_script or ""
    line_count = len([line.strip() for line in curr_script_preview.split('\n') if line.strip()])
    word_count = len(curr_script_preview.split())
    est_dur = round(word_count / 2.3, 1) if word_count > 0 else 0.0

    stat_badge_text = f"📊 {line_count} Scenes · {word_count} Words · ~{est_dur}s Est. Runtime" if line_count > 0 else "⚡ 1 Line = 1 Numbered Scene"

    # Studio Script Editor Card
    st.markdown(f"""
    <div class="script-editor-card">
        <div class="script-editor-header">
            <div class="script-editor-title">
                <span class="script-editor-icon">📝</span>
                <div>
                    <div class="script-editor-heading">Studio Script & Storyboard Composer</div>
                    <div class="script-editor-subheading">Type or paste your narrative. Every sentence or line becomes an AI scene with matched footage & voiceover.</div>
                </div>
            </div>
            <div class="script-live-stats">
                <span class="script-stat-chip active">{stat_badge_text}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    script_input = st.text_area(
        "Script Content",
        value=initial_script,
        height=260,
        placeholder="Enter your script here line by line... Example:\nThousands of years ago, majestic stone pyramids rose against the golden Egyptian desert.\nSkilled craftsmen and workers carved colossal limestone blocks under the blazing sun.\nMysterious hieroglyphs decorated the inner chambers of ancient pharaoh tombs.\nToday, these ancient monuments still hold untold secrets waiting to be uncovered.",
        label_visibility="collapsed"
    )

    st.markdown("""
        <div class="script-editor-footer">
            <div>💡 <strong>Pro Creator Tip:</strong> Press Enter between lines to split scenes. Each line gets custom 1080p footage, automatic Ken Burns photo motion, and synced human voiceover.</div>
            <div>🔒 <strong>Topic Anchor:</strong> Scene 1 strictly locked to your main topic.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 🎙️ Voice & Speech Narrator (Main Page Studio Controls)
    curr_voice_key = st.session_state.get("selected_voice", DEFAULT_VOICE)
    curr_voice_label = VOICE_CATALOG.get(curr_voice_key, curr_voice_key)

    st.markdown(f"""
    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:16px 20px; margin-top:14px; margin-bottom:14px; box-shadow:0 1px 4px rgba(0,0,0,0.03);">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; flex-wrap:wrap; gap:8px;">
            <div style="font-size:0.95rem; font-weight:700; color:#0F172A; display:flex; align-items:center; gap:8px;">
                <span>🎙️ Script Speech Engine & Voice Model</span>
                <span style="font-size:0.72rem; font-weight:600; background:#E0F2FE; color:#0284C7; padding:2px 8px; border-radius:999px;">AI Voice Studio</span>
                <span style="font-size:0.72rem; font-weight:700; background:#FEF3C7; color:#B45309; padding:2px 8px; border-radius:999px;">⚡ {speed_mode.split(' ')[0]} Speed</span>
            </div>
            <div style="font-size:0.8rem; font-weight:700; color:#047857; background:#ECFDF5; padding:3px 12px; border-radius:999px; border:1px solid #A7F3D0;">
                🟢 Active Model: {curr_voice_label.split('(')[0].strip()}
            </div>
        </div>
        <div style="font-size:0.78rem; color:#64748B;">
            Each line in your script will be naturally spoken out loud using this AI voice model at {speed_mode.split(' ')[0]} speed, with footage timed directly to speech length.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_v1, col_v2 = st.columns([1, 2.2])
    with col_v1:
        enable_vo_main = st.checkbox(
            "🎙️ Voice Narration",
            value=st.session_state.get("enable_voiceover", True),
            key="main_enable_voiceover",
            help="Speaks your script out loud with natural human AI narration."
        )
        st.session_state.enable_voiceover = enable_vo_main
        enable_voiceover = enable_vo_main

    with col_v2:
        voice_keys = list(VOICE_CATALOG.keys())
        curr_v = st.session_state.get("selected_voice", DEFAULT_VOICE)
        idx_v = voice_keys.index(curr_v) if curr_v in voice_keys else 0
        sel_v_main = st.selectbox(
            "Speech Model / Voice Artist",
            options=voice_keys,
            format_func=lambda k: VOICE_CATALOG.get(k, k),
            index=idx_v,
            key="main_selected_voice",
            disabled=not enable_voiceover,
            help="Choose Hindi (Madhur / Swara) or English (Christopher / Jenny / Guy / Aria / Ryan)."
        )
        st.session_state.selected_voice = sel_v_main
        selected_voice = sel_v_main

    col_v3, col_v4 = st.columns(2)
    with col_v3:
        if st.button("🎧 Test Voice Sample", key="btn_sample_voice", use_container_width=True, disabled=not enable_voiceover):
            sample_audio_file = DOWNLOADS_DIR / f"sample_{selected_voice}.mp3"
            test_phrase = "Namaste dosto. Yeh voiceover aapke YouTube video ke liye ready hai." if "hi-IN" in selected_voice else "Hello creator. This realistic human voiceover is ready for your YouTube video."
            with st.spinner("Synthesizing audio sample..."):
                dur = generate_human_voiceover(test_phrase, sample_audio_file, voice=selected_voice, rate=tts_rate_str)
                if sample_audio_file.exists():
                    st.audio(str(sample_audio_file), format="audio/mp3")

    with col_v4:
        if st.button("🪟 Open Voice Library", key="btn_open_voice_modal", use_container_width=True, help="Open full Voice Narrator modal dialog"):
            open_voice_selection_dialog()

    col_media_type, col_blank = st.columns([2, 2])
    with col_media_type:
        global_media_pref = st.selectbox(
            "Visual Media Distribution Mix",
            ["invideo_mix", "both", "video", "image"],
            format_func=lambda x: {
                "invideo_mix": "🎯 Smart InVideo Mix (60% Videos, 40% Photos)",
                "both": "🎬 Best Available (Both Videos & Images)",
                "video": "🎥 Videos Only",
                "image": "📸 Images / Photos Only"
            }.get(x, x),
            help="60% Videos / 40% Images follows high-retention InVideo AI documentary standards."
        )

    # 🚀 PRIMARY STUDIO ACTION CONTROLS
    st.write("")
    col_btn_gen, col_btn_parse = st.columns([3, 2])
    with col_btn_gen:
        trigger_1click = st.button(
            "🚀 1-Click Generate & Download Video",
            type="primary",
            use_container_width=True,
            help="Finds best 1080p clips automatically in background, synthesizes voiceover, renders, and produces final video immediately!"
        )
    with col_btn_parse:
        trigger_parse = st.button(
            "📝 Parse Storyboard Only (Manual Edit)",
            type="secondary",
            use_container_width=True,
            help="Review & edit individual scene keywords or timings before rendering."
        )

    if trigger_1click:
        if not script_input.strip():
            st.warning("Please enter or select a script first.")
        elif not pixabay_key:
            st.error("Please ensure the Pixabay API key is set in the sidebar.")
        else:
            status_container = st.empty()
            render_bar = st.progress(0.0)
            pipeline_res = run_full_auto_video_pipeline(
                script_text=script_input,
                main_topic=main_topic_input,
                media_pref=global_media_pref,
                speed_mult=speed_multiplier,
                tts_rate=tts_rate_str,
                voice_name=selected_voice,
                do_voice=enable_voiceover,
                pb_key=pixabay_key,
                ai_key=openai_key,
                tw=target_w,
                th=target_h,
                orient=orientation,
                fit_m=fit_mode,
                kb_style=ken_burns_style,
                b_badge=burn_badge,
                b_style=badge_style,
                b_pos=badge_position,
                b_subs=burn_subtitles,
                sub_style=subtitle_style_choice,
                p_buffer=pause_buffer,
                bgm_k=selected_bgm_key,
                custom_bgm=custom_bgm_file,
                bgm_vol=bgm_volume,
                niche_k=active_niche_k,
                status_container=status_container,
                render_bar=render_bar
            )
            if pipeline_res:
                st.session_state.merged_video = pipeline_res["merged_video"]
                st.session_state.assets_zip = pipeline_res["assets_zip"]
                st.session_state.youtube_seo_kit = pipeline_res["youtube_seo_kit"]
                st.session_state.parsed_scenes = pipeline_res["parsed_scenes"]
                st.session_state.scene_assets = pipeline_res["scene_assets"]
                st.session_state.selected_assets = pipeline_res["selected_assets"]
                st.session_state.active_script_content = script_input
                st.session_state.custom_main_topic = main_topic_input
                st.rerun()

    if trigger_parse:
        if not script_input.strip():
            st.warning("Please enter or select a script first.")
        else:
            scenes = parse_script_to_scenes(
                script_input,
                default_duration=default_duration,
                default_media=global_media_pref,
                speed=speed_multiplier,
                main_topic=main_topic_input
            )
            st.session_state.parsed_scenes = scenes
            st.session_state.scene_assets = {}
            st.session_state.selected_assets = {}
            st.session_state.pop("merged_video", None)
            st.session_state.pop("assets_zip", None)
            st.success(f"🎉 Generated {len(scenes)} scenes with scenario keywords and {speed_mode.split(' ')[0]} dynamic durations!")
            st.rerun()

    # =====================================================================
    # STEP 5: VIDEO PLAYER & DOWNLOADS (SHOWN PROMINENTLY ONCE GENERATED)
    # =====================================================================
    has_merged = bool(st.session_state.get("merged_video"))
    if has_merged:
        merged_path = Path(st.session_state.merged_video)
        if merged_path.exists():
            st.markdown("""
            <div style="margin-top: 28px;"></div>
            <div class="section-title">
                <span>Step 2: Preview & Download Final Video</span>
                <span class="section-badge" style="background:#ECFDF5; color:#059669; border-color:#A7F3D0;">🎉 100% Production Ready</span>
            </div>
            """, unsafe_allow_html=True)

            # Embedded Video Player
            st.video(str(merged_path))

            # Video Info Metrics
            file_mb = round(merged_path.stat().st_size / (1024 * 1024), 2)
            scenes_count = len(st.session_state.get("parsed_scenes", []))
            actual_dur = get_audio_duration(merged_path)

            st.write("")
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""
                <div class="metric-card-box">
                    <div class="metric-card-label">🎬 Total Scenes</div>
                    <div class="metric-card-val">{scenes_count}</div>
                </div>
                """, unsafe_allow_html=True)
            with m2:
                st.markdown(f"""
                <div class="metric-card-box">
                    <div class="metric-card-label">⏱️ Total Runtime</div>
                    <div class="metric-card-val">{actual_dur:.1f}s</div>
                </div>
                """, unsafe_allow_html=True)

            with m3:
                st.markdown(f"""
                <div class="metric-card-box">
                    <div class="metric-card-label">📐 Resolution</div>
                    <div class="metric-card-val" style="font-size:1.35rem;">{target_w}x{target_h}</div>
                </div>
                """, unsafe_allow_html=True)
            with m4:
                st.markdown(f"""
                <div class="metric-card-box">
                    <div class="metric-card-label">💾 File Size</div>
                    <div class="metric-card-val">{file_mb} MB</div>
                </div>
                """, unsafe_allow_html=True)

            active_topic_raw = st.session_state.get("custom_main_topic") or ""
            if not active_topic_raw and st.session_state.get("youtube_seo_kit"):
                titles_list = st.session_state["youtube_seo_kit"].get("titles", [])
                if titles_list:
                    active_topic_raw = titles_list[0]
            if not active_topic_raw:
                cur_scenes = st.session_state.get("parsed_scenes", [])
                active_topic_raw = st.session_state.get("current_topic") or (cur_scenes[0].get('keyword') if cur_scenes else "YouTube_Video")

            topic_slug = slugify(active_topic_raw)

            # Download & Action Buttons
            st.write("")
            dl_col1, dl_col2, dl_col3 = st.columns([3, 2, 2])
            with dl_col1:
                with open(merged_path, "rb") as vf:
                    st.download_button(
                        label=f"⬇️ Download Video ({topic_slug}_Video.mp4)",
                        data=vf,
                        file_name=f"{topic_slug}_Video.mp4",
                        mime="video/mp4",
                        type="primary",
                        use_container_width=True
                    )
            with dl_col2:
                if st.session_state.get("assets_zip"):
                    zip_p = Path(st.session_state.assets_zip)
                    if zip_p.exists():
                        with open(zip_p, "rb") as zf:
                            st.download_button(
                                label=f"📦 Download Archive ZIP",
                                data=zf,
                                file_name=f"{topic_slug}_Clips_and_Audio.zip",
                                mime="application/zip",
                                use_container_width=True
                            )
            with dl_col3:
                if st.button("✨ Create Another Video", use_container_width=True, help="Clear and start a fresh script"):
                    for k in ["merged_video", "assets_zip", "parsed_scenes", "scene_assets", "selected_assets", "youtube_seo_kit"]:
                        st.session_state.pop(k, None)
                    st.rerun()

            # -------------------------------------------------------------
            # 🚀 YOUTUBE STUDIO UPLOAD & GROWTH KIT
            # -------------------------------------------------------------
            st.markdown("""
            <div style="margin-top: 36px;"></div>
            <div class="section-title">
                <span>🚀 YouTube Studio Upload & Growth Kit</span>
                <span class="section-badge">1-Click Channel Automation</span>
            </div>
            """, unsafe_allow_html=True)

            active_niche_k = st.session_state.get("selected_niche", "history")
            active_top = st.session_state.get("custom_main_topic") or (st.session_state.get("parsed_scenes", [{}])[0].get('keyword') if st.session_state.get("parsed_scenes") else "Ancient Mysteries")

            if not st.session_state.get("youtube_seo_kit"):
                st.session_state.youtube_seo_kit = generate_youtube_seo_kit(
                    topic=active_top,
                    script_text=st.session_state.get("active_script_content", script_input),
                    scenes=st.session_state.get("parsed_scenes", []),
                    niche_key=active_niche_k
                )

            seo_kit = st.session_state.get("youtube_seo_kit", {})

            col_titles_box, col_tags_box = st.columns([1, 1])
            with col_titles_box:
                st.markdown("##### 🎯 3 High-CTR Curiosity Titles")
                for t_idx, t_str in enumerate(seo_kit.get("titles", []), start=1):
                    st.markdown(f"""
                    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:3px solid #2563EB; border-radius:8px; padding:8px 12px; margin-bottom:8px; font-size:0.86rem; font-weight:700; color:#0F172A;">
                        <span style="color:#2563EB; font-weight:800;">#{t_idx}</span> {t_str}
                    </div>
                    """, unsafe_allow_html=True)

            with col_tags_box:
                st.markdown("##### 🏷️ 28-30 Viral Ranking Tags (Click to Copy)")
                st.code(seo_kit.get("tags", ""), language="text")
                st.caption("📋 Click the copy icon in top-right of box to paste directly into YouTube Studio Tag Box!")

            st.write("")
            with st.expander("📝 Full YouTube Description with Auto Timestamps & Chapters", expanded=True):
                st.code(seo_kit.get("description", ""), language="markdown")
                st.caption("📋 Generated dynamically from your video script. Paste directly into your YouTube video description.")

            seo_txt_content = f"""======================================================================
YOUTUBE STUDIO UPLOAD KIT: {active_topic_raw}
======================================================================

🎯 CLICKBAIT TITLES (CHOOSE ONE):
1. {seo_kit.get('titles', [''])[0] if seo_kit.get('titles') else ''}
2. {seo_kit.get('titles', ['', ''])[1] if len(seo_kit.get('titles', [])) > 1 else ''}
3. {seo_kit.get('titles', ['', '', ''])[2] if len(seo_kit.get('titles', [])) > 2 else ''}

======================================================================
📝 FULL DESCRIPTION (COPY-PASTE WITH TIMESTAMPS / CHAPTERS):
======================================================================
{seo_kit.get('description', '')}

======================================================================
🏷️ VIRAL TAGS (PASTE INTO YOUTUBE STUDIO TAG BOX):
======================================================================
{seo_kit.get('tags', '')}

======================================================================
💬 VIRAL PINNED COMMENT:
======================================================================
{seo_kit.get('pinned_comment', '')}
======================================================================
"""
            st.download_button(
                label=f"📄 Download Complete YouTube SEO Kit ({topic_slug}_YouTube_SEO.txt)",
                data=seo_txt_content,
                file_name=f"{topic_slug}_YouTube_SEO.txt",
                mime="text/plain",
                use_container_width=True
            )

            st.markdown(f"""
            <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px; padding:10px 14px; margin-top:8px; margin-bottom:18px;">
                <div style="font-size:0.75rem; font-weight:700; color:#166534; text-transform:uppercase;">💬 Viral Pinned Comment Prompt (Ask Audience):</div>
                <div style="font-size:0.86rem; font-weight:600; color:#0F172A; margin-top:2px;">{seo_kit.get('pinned_comment', '')}</div>
            </div>
            """, unsafe_allow_html=True)

    # =====================================================================
    # ADVANCED EXPANDER: REVIEW STORYBOARD & SCENE CLIPS (OPTIONAL / COLLAPSED BY DEFAULT)
    # =====================================================================
    has_parsed = bool(st.session_state.get("parsed_scenes"))
    if has_parsed:
        with st.expander("🛠️ Advanced: Review Storyboard & Scene Clips (Optional)", expanded=(has_parsed and not has_merged)):
            scenes = st.session_state.parsed_scenes
            total_est_dur = sum([float(s.get('duration', default_duration)) for s in scenes])

            st.markdown(f"""
            <div class="section-title" style="margin-top:10px;">
                <span>InVideo AI Multi-Track Timeline & Storyboard ({len(scenes)} Scenes)</span>
                <span class="section-badge">Total Runtime: {total_est_dur:.1f}s</span>
            </div>
            """, unsafe_allow_html=True)

            video_count = sum(1 for s in scenes if s.get('media_pref') == 'video')
            image_count = len(scenes) - video_count

            timeline_html = [
                '<div class="timeline-container">',
                f'<div class="timeline-header"><div class="timeline-title">🎬 Multi-Track Project Timeline</div>'
                f'<div style="font-size:0.78rem; font-weight:600; color:#475569;">'
                f'Mix: <strong style="color:#1D4ED8;">{video_count} Videos ({int(video_count/len(scenes)*100)}%)</strong> · '
                f'<strong style="color:#7E22CE;">{image_count} Photos ({int(image_count/len(scenes)*100)}%)</strong> · '
                f'Total: <strong style="color:#059669;">{total_est_dur:.1f}s</strong>'
                f'</div></div>',
                '<div class="timeline-track-title">🎞️ Visual Footage Track</div>',
                '<div class="timeline-track">'
            ]
            curr_offset = 0.0
            for sc in scenes:
                d = float(sc.get('duration', default_duration))
                m_icon = "🎥" if sc.get('media_pref') == 'video' else "📸"
                timeline_html.append(
                    f'<div class="timeline-clip">'
                    f'<div class="timeline-clip-top">'
                    f'<span class="timeline-clip-label">{m_icon} Scene {sc["no"]}</span>'
                    f'<span class="timeline-clip-dur">{d:.1f}s</span>'
                    f'</div>'
                    f'<div class="timeline-clip-text" title="{sc["text"]}">{sc["text"]}</div>'
                    f'<div style="font-size:0.68rem; color:#94A3B8;">[{curr_offset:.1f}s - {curr_offset+d:.1f}s]</div>'
                    f'</div>'
                )
                curr_offset += d
            timeline_html.append('</div></div>')
            st.markdown("".join(timeline_html), unsafe_allow_html=True)

            for idx, sc in enumerate(scenes):
                m_label = "🎥 Video Scene (60% Mix)" if sc.get('media_pref') == 'video' else "📸 Photo Scene (40% Mix)"
                is_hook = sc.get('is_hook', False) or (idx == 0)
                hook_prefix = "🔥 OPENING HOOK (TOPIC ANCHOR) · " if is_hook else ""
                with st.expander(f"{hook_prefix}🎬 Scene {sc['no']} · {m_label} · \"{sc['text'][:60]}...\" · ⏱️ {sc.get('duration', default_duration)}s", expanded=(idx == 0)):
                    if is_hook:
                        st.info(f"🎯 **Hook Topic Anchor Active:** Scene 1 is strictly locked to your main topic: **{sc.get('hook_topic', sc.get('keyword'))}** (Hero Footage)")
                    else:
                        st.caption(f"💡 **Detected Scenario:** {sc.get('scenario', 'Cinematic scene')}")
                    sc['text'] = st.text_area("Script Line (Subtitles)", value=sc['text'], key=f"txt_{idx}", height=75)
                    c_kw, c_dur = st.columns([2, 1])
                    with c_kw:
                        sc['keyword'] = st.text_input("Scenario Stock Keyword", value=sc['keyword'], key=f"kw_{idx}", help="Scenario-based search query sent to stock libraries.")
                    with c_dur:
                        curr_val = float(sc.get('duration', estimate_speech_duration(sc['text'])))
                        curr_val = max(1.5, min(curr_val, 60.0))
                        sc['duration'] = st.number_input(
                            "Duration (s) [Audio Paced]",
                            min_value=1.5,
                            max_value=60.0,
                            value=round(curr_val, 1),
                            step=0.5,
                            key=f"dur_{idx}",
                            help="Audio-driven: Visual clip timing matches voice narration length (+ natural pause buffer)."
                        )

            # Search Assets Button inside expander
            st.write("")
            if st.button("🔍 Find Matching Assets & AI Visuals", type="primary", use_container_width=True, key="btn_adv_find_assets"):
                if not pixabay_key:
                    st.error("Please ensure the Pixabay API key is set in the sidebar.")
                else:
                    st.session_state.scene_assets = {}
                    st.session_state.selected_assets = {}
                    bar_adv = st.progress(0.0)
                    txt_adv = st.empty()

                    def _search_worker_adv(item):
                        idx, sc_item = item
                        m_type = sc_item.get('media_pref', 'both')
                        res = safe_search_assets(
                            query=sc_item['keyword'],
                            key=pixabay_key,
                            media_type=m_type,
                            orientation=orientation,
                            per_page=10,
                            sentence=sc_item['text'],
                            openai_key=openai_key,
                            dalle_prompt=sc_item.get('dalle_prompt', '')
                        )
                        if not res and m_type != "both":
                            res = safe_search_assets(
                                query=sc_item['keyword'],
                                key=pixabay_key,
                                media_type="both",
                                orientation=orientation,
                                per_page=10,
                                sentence=sc_item['text'],
                                openai_key=openai_key,
                                dalle_prompt=sc_item.get('dalle_prompt', '')
                            )
                        if not res:
                            ai_asset = generate_ai_image(
                                prompt=sc_item.get('dalle_prompt') or sc_item['text'],
                                openai_key=openai_key
                            )
                            if ai_asset:
                                res = [ai_asset]
                        return idx, sc_item, (res or [])

                    search_items = list(enumerate(scenes))
                    total_s = len(search_items)
                    comp_res = []
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        futs = {executor.submit(_search_worker_adv, it): it[0] for it in search_items}
                        d_cnt = 0
                        for f in as_completed(futs):
                            try:
                                comp_res.append(f.result())
                            except Exception:
                                o_idx = futs[f]
                                comp_res.append((o_idx, scenes[o_idx], []))
                            d_cnt += 1
                            bar_adv.progress(d_cnt / total_s)
                            txt_adv.info(f"⚡ Finding visuals ({d_cnt}/{total_s})...")

                    comp_res.sort(key=lambda x: x[0])
                    used_ids = set()
                    for idx, sc, results in comp_res:
                        st.session_state.scene_assets[sc['no']] = results
                        pick_idx, chosen_asset = pick_unique_candidate(results, used_ids)
                        if chosen_asset:
                            used_ids.add(chosen_asset['id'])
                            sc['duration'] = round(float(sc.get('duration', estimate_speech_duration(sc['text']))), 1)
                        st.session_state.selected_assets[sc['no']] = max(0, pick_idx)

                    txt_adv.empty()
                    bar_adv.empty()
                    st.success("✅ Visuals found!")
                    st.rerun()

            # If scene assets exist, render candidate cards & render button inside expander
            if st.session_state.get("scene_assets"):
                st.markdown("---")
                st.markdown("##### 🎯 Selected Scene Visual Cards (Swap or Change):")
                scene_assets = st.session_state.scene_assets
                for idx, sc in enumerate(scenes):
                    sc_no = sc['no']
                    assets = scene_assets.get(sc_no, [])
                    if not assets:
                        continue
                    curr_selected = st.session_state.selected_assets.get(sc_no, 0)
                    best_asset = assets[min(curr_selected, len(assets) - 1)]

                    st.markdown('<div class="asset-card-wrapper asset-card-selected" style="margin-bottom:12px;">', unsafe_allow_html=True)
                    c_p, c_d, c_s = st.columns([2, 5, 2])
                    with c_p:
                        if best_asset.get('preview'):
                            st.image(best_asset['preview'], use_container_width=True)
                        else:
                            st.caption("No preview")
                    with c_d:
                        if best_asset.get('type') == 'video':
                            st.markdown(f"**Scene {sc_no} (🎥 Video):** `{sc.get('keyword', '')}`")
                        else:
                            st.markdown(f"**Scene {sc_no} (📸 Photo):** `{sc.get('keyword', '')}`")
                        st.caption(f"👤 {best_asset.get('author', 'Creator')} · ID: `{best_asset.get('id', '')}`")
                    with c_s:
                        if len(assets) > 1:
                            next_idx = (curr_selected + 1) % len(assets)
                            if st.button(f"🔄 Swap ({next_idx+1}/{len(assets)})", key=f"adv_swap_{sc_no}", use_container_width=True):
                                st.session_state.selected_assets[sc_no] = next_idx
                                st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                st.write("")
                if st.button("🚀 Render & Merge Video from Storyboard", type="primary", use_container_width=True, key="btn_adv_render"):
                    status_c = st.empty()
                    r_bar = st.progress(0.0)
                    pipeline_res = run_full_auto_video_pipeline(
                        script_text=st.session_state.get("active_script_content", script_input),
                        main_topic=st.session_state.get("custom_main_topic", main_topic_input),
                        media_pref=global_media_pref,
                        speed_mult=speed_multiplier,
                        tts_rate=tts_rate_str,
                        voice_name=selected_voice,
                        do_voice=enable_voiceover,
                        pb_key=pixabay_key,
                        ai_key=openai_key,
                        tw=target_w,
                        th=target_h,
                        orient=orientation,
                        fit_m=fit_mode,
                        kb_style=ken_burns_style,
                        b_badge=burn_badge,
                        b_style=badge_style,
                        b_pos=badge_position,
                        b_subs=burn_subtitles,
                        sub_style=subtitle_style_choice,
                        p_buffer=pause_buffer,
                        bgm_k=selected_bgm_key,
                        custom_bgm=custom_bgm_file,
                        bgm_vol=bgm_volume,
                        niche_k=active_niche_k,
                        status_container=status_c,
                        render_bar=r_bar,
                        existing_scenes=scenes,
                        existing_scene_assets=st.session_state.scene_assets,
                        existing_selected_assets=st.session_state.selected_assets
                    )
                    if pipeline_res:
                        st.session_state.merged_video = pipeline_res["merged_video"]
                        st.session_state.assets_zip = pipeline_res["assets_zip"]
                        st.session_state.youtube_seo_kit = pipeline_res["youtube_seo_kit"]
                        st.session_state.parsed_scenes = pipeline_res["parsed_scenes"]
                        st.session_state.scene_assets = pipeline_res["scene_assets"]
                        st.session_state.selected_assets = pipeline_res["selected_assets"]
                        st.success("🎉 Video rendered and merged successfully!")
                        st.rerun()




# =====================================================================
# TAB 2: CSV BATCH ASSET FINDER
# =====================================================================
with tab2:
    st.markdown("""
    <div class="section-title">
        <span>Batch Search from CSV</span>
        <span class="section-badge">Batch Pipeline</span>
    </div>
    <div style="color:#64748B; font-size:0.92rem; margin-bottom:16px;">
        Upload a structured CSV with columns: <code style="color:#2563EB; font-family:'JetBrains Mono';">No, Description, Type, Duration, Orientation</code>
    </div>
    """, unsafe_allow_html=True)

    sample_csv = "No,Description,Type,Duration,Orientation\n01,Ancient pyramid exterior,video,5,landscape\n02,Workers building pyramid,video,5,landscape\n03,Egyptian hieroglyphs,image,4,landscape\n04,Inside pharaoh tomb,video,5,landscape\n"
    
    col_csv_dl, col_csv_info = st.columns([2, 3])
    with col_csv_dl:
        st.download_button("⬇️ Download Sample CSV Template", sample_csv, "sample_assets.csv", "text/csv", use_container_width=True)

    uploaded_csv = st.file_uploader("Upload CSV File", type=["csv"], key="csv_uploader")
    if uploaded_csv:
        csv_rows = list(csv.DictReader(io.StringIO(uploaded_csv.getvalue().decode('utf-8-sig'))))
        st.dataframe(csv_rows, use_container_width=True)

        st.write("")
        if st.button("🔎 Search Assets for CSV Rows", type="primary", key="btn_csv_search", use_container_width=True):
            st.session_state.csv_results = {}
            bar = st.progress(0.0)
            for i, r in enumerate(csv_rows):
                no = str(r.get('No') or i + 1).zfill(2)
                q = r.get('Description', '')
                media_t = 'image' if str(r.get('Type') or '').lower().strip() in ['image', 'photo', 'picture'] else 'video'
                orient = (r.get('Orientation') or 'landscape').lower()
                o_val = 'horizontal' if orient == 'landscape' else ('vertical' if orient == 'portrait' else 'all')
                
                res = safe_search_assets(q, key=pixabay_key, media_type=media_t, orientation=o_val, per_page=10, openai_key=openai_key)
                st.session_state.csv_results[no] = {'row': r, 'results': res}
                bar.progress((i + 1) / len(csv_rows))
            bar.empty()
            st.success("✅ CSV Asset Search Complete!")
            st.rerun()

    if st.session_state.get("csv_results"):
        st.markdown("""
        <div style="margin-top: 24px;"></div>
        <div class="section-title">
            <span>Select CSV Assets & Download / Merge</span>
            <span class="section-badge">Batch Selection</span>
        </div>
        """, unsafe_allow_html=True)
        
        csv_res = st.session_state.csv_results
        csv_picks = {}

        for no, item in csv_res.items():
            r = item['row']
            res_list = item['results']
            
            st.markdown(f"""
            <div class="scene-header-bar">
                <div style="display:flex; align-items:center; gap:12px;">
                    <span class="scene-badge-num">#{no}</span>
                    <span class="scene-quote">{r.get('Description', '')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if not res_list:
                st.warning("No asset found. Try refining the description in your CSV.")
                continue

            labels = [f"Option {i+1}: {x['source']} · {x.get('author','')} ({x['type'].upper()})" for i, x in enumerate(res_list[:5])]
            sel = st.radio(f"Select asset for #{no}", range(len(labels)), format_func=lambda i: labels[i], key=f"csv_pick_{no}")
            csv_picks[no] = res_list[sel]
            if res_list[sel].get('preview'):
                st.image(res_list[sel]['preview'], width=280)

        st.write("")
        c_dl, c_merge = st.columns(2)
        with c_dl:
            if csv_picks and st.button("📦 Download Selected Assets as ZIP", type="primary", use_container_width=True):
                job_ts = time.strftime('%Y%m%d_%H%M%S')
                c_dir = DOWNLOADS_DIR / f"csv_job_{job_ts}"
                c_dir.mkdir(parents=True, exist_ok=True)
                downloaded_paths = []
                for no, asset in csv_picks.items():
                    ext = ".jpg" if asset['type'] == 'image' else ".mp4"
                    dest = c_dir / f"{no}_{slugify(csv_res[no]['row'].get('Description', 'asset'))}{ext}"
                    if download_file(asset['download'], dest):
                        downloaded_paths.append(dest)
                z_dest = DOWNLOADS_DIR / f"csv_assets_{job_ts}.zip"
                make_numbered_zip(downloaded_paths, z_dest)
                st.session_state.csv_zip = str(z_dest)
                st.success("🎉 ZIP Archive Ready!")
                st.rerun()

        with c_merge:
            if csv_picks and st.button("🎬 Merge CSV Assets into Video", type="secondary", use_container_width=True):
                job_ts = time.strftime('%Y%m%d_%H%M%S')
                c_dir = DOWNLOADS_DIR / f"csv_job_{job_ts}"
                c_dir.mkdir(parents=True, exist_ok=True)
                clips = []
                for no, asset in csv_picks.items():
                    ext = ".jpg" if asset['type'] == 'image' else ".mp4"
                    dest = c_dir / f"raw_{no}{ext}"
                    is_image = (asset['type'] == 'image')
                    if not (download_file(asset['download'], dest) and dest.exists() and dest.stat().st_size > 1000):
                        dest = c_dir / f"raw_{no}_fallback.jpg"
                        create_fallback_slide(dest, target_w, target_h, title=f"Scene {no}", text=csv_res[no]['row'].get('Description', ''))
                        is_image = True

                    overlay_p = c_dir / f"overlay_{no}.png"
                    create_overlay_image(target_w, target_h, no, overlay_p, scene_text=csv_res[no]['row'].get('Description'), show_badge=burn_badge, show_subtitle=burn_subtitles)
                    clip_p = c_dir / f"{no}_clip.mp4"
                    if safe_process_scene_clip(media_path=dest, output_path=clip_p, target_w=target_w, target_h=target_h, duration=default_duration, is_image=is_image, overlay_path=overlay_p):
                        clips.append(clip_p)
                if clips:
                    m_dest = DOWNLOADS_DIR / f"csv_merged_{job_ts}.mp4"
                    if merge_clips_to_final_video(clips, m_dest):
                        st.session_state.csv_merged = str(m_dest)
                        st.success("🎉 CSV Video Merged!")
                        st.rerun()

        if st.session_state.get("csv_zip"):
            zp = Path(st.session_state.csv_zip)
            if zp.exists():
                with open(zp, "rb") as f:
                    st.download_button("⬇️ Download CSV Assets ZIP", f.read(), zp.name, "application/zip", use_container_width=True)

        if st.session_state.get("csv_merged"):
            mp = Path(st.session_state.csv_merged)
            if mp.exists():
                st.video(str(mp))
                with open(mp, "rb") as f:
                    st.download_button("⬇️ Download CSV Merged Video (.mp4)", f.read(), mp.name, "video/mp4", use_container_width=True)
