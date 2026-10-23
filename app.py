import subprocess
import io
import csv
import re
import time
import zipfile
from pathlib import Path
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from job_manager import BackgroundRenderManager
from studio_brain import StudioBrain

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
        "hi-IN-MadhurNeural": "🇮🇳 Madhur (Hindi Male - Deep & Cinematic Storyteller)",
        "hi-IN-SwaraNeural": "🇮🇳 Swara (Hindi Female - Expressive & Clear Narration)",
        "en-IN-PrabhatNeural": "🇮🇳 Prabhat (Hinglish Male - Modern YouTube Creator)",
        "en-IN-NeerjaExpressiveNeural": "🇮🇳 Neerja (Hinglish Female - Ultra Expressive)",
        "mr-IN-ManoharNeural": "🚩 Manohar (Marathi Male - Deep & Realistic Storyteller)",
        "mr-IN-AarohiNeural": "🚩 Aarohi (Marathi Female - Natural & Clear Narration)",
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

def cleanup_storage_cache(max_age_hours: float = 48.0, max_folder_mb: float = 35000.0):
    """
    Automatic Storage Manager (Optimized for Local Creator Desktop & Long 20-60+ min Videos):
    1. Keeps rendered videos safe for at least 48 hours.
    2. Protects active rendering jobs for at least 6 hours (21600s), fully supporting 20-60+ min videos.
    3. NEVER deletes the currently loaded session video, recent merged_video_*.mp4 files, or assets_*.zip.
    4. Only cleans up intermediate job folders when disk space limit (35 GB) is reached.
    """
    try:
        if not DOWNLOADS_DIR.exists():
            return

        now = time.time()
        max_age_sec = max_age_hours * 3600  # 48 hours
        protect_window_sec = 21600  # 6 hours protection window for long 20-60+ min videos

        # Gather explicitly protected paths (session files and recent final videos)
        protected_names = set()
        try:
            if hasattr(st, "session_state"):
                if st.session_state.get("merged_video"):
                    protected_names.add(Path(st.session_state.merged_video).name)
                if st.session_state.get("assets_zip"):
                    protected_names.add(Path(st.session_state.assets_zip).name)
                if st.session_state.get("csv_merged"):
                    protected_names.add(Path(st.session_state.csv_merged).name)
                if st.session_state.get("csv_zip"):
                    protected_names.add(Path(st.session_state.csv_zip).name)
        except Exception:
            pass

        # Protect 5 most recent merged_video_*.mp4 files unconditionally
        recent_finals = sorted(DOWNLOADS_DIR.glob("merged_video_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        for rf in recent_finals[:5]:
            protected_names.add(rf.name)

        recent_zips = sorted(DOWNLOADS_DIR.glob("assets_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        for rz in recent_zips[:5]:
            protected_names.add(rz.name)

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

        # Rule 1: Delete temporary job folders older than max_age_hours (48h) and outside protection window (6h)
        remaining_items = []
        for item, mtime, sz in items:
            if item.name in protected_names:
                remaining_items.append((item, mtime, sz))
                continue

            age = now - mtime
            # Only delete intermediate job folders or non-final files older than 48 hours
            if age > max_age_sec and age > protect_window_sec:
                # Never delete final output files in Rule 1
                if item.name.startswith("merged_video_"):
                    remaining_items.append((item, mtime, sz))
                    continue
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

        # Rule 2: If total folder size exceeds max_folder_mb (35GB), purge ONLY oldest temporary scene folders
        max_bytes = max_folder_mb * 1024 * 1024
        if total_bytes > max_bytes:
            remaining_items.sort(key=lambda x: x[1])
            for item, mtime, sz in remaining_items:
                if item.name in protected_names or (now - mtime) < protect_window_sec:
                    continue  # NEVER delete protected files or active renders
                # NEVER purge final merged videos in Rule 2
                if item.name.startswith("merged_video_"):
                    continue
                if total_bytes <= (max_bytes * 0.7):
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

# Custom Modern Minimalist Creator Studio CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* Global Typography & Light Canvas */
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-color: #F8FAFC !important;
        color: #0F172A !important;
    }

    /* Ambient Clean Light Background */
    .stApp {
        background: radial-gradient(ellipse 80% 50% at 50% -10%, rgba(37, 99, 235, 0.03) 0%, transparent 60%), #F8FAFC !important;
    }

    /* Minimalist Light Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #F1F5F9 !important;
        margin: 1rem 0 !important;
    }

    /* Minimalist Brand Card */
    .sidebar-brand-card {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 14px;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        margin-bottom: 14px;
    }
    .sidebar-brand-icon {
        font-size: 1.35rem;
    }
    .sidebar-brand-title {
        font-size: 0.96rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: #0F172A;
        line-height: 1.2;
    }
    .sidebar-brand-subtitle {
        font-size: 0.68rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    /* Clean Card Surfaces */
    .studio-card {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 18px 20px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
    }

    /* Section Headings */
    .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .section-badge {
        font-size: 0.7rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 999px;
        background: #EFF6FF;
        color: #2563EB;
        border: 1px solid #DBEAFE;
    }

    /* Modern VideoCraft Studio Buttons */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        font-size: 1.02rem !important;
        letter-spacing: 0.01em !important;
        padding: 0.72rem 1.8rem !important;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35) !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    div.stButton > button[kind="primary"]:hover {
        opacity: 0.96 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(79, 70, 229, 0.45) !important;
    }
    div.stButton > button[kind="secondary"] {
        background: #FFFFFF !important;
        color: #334155 !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        padding: 0.72rem 1.4rem !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.15s ease !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background: #F8FAFC !important;
        border-color: #94A3B8 !important;
        color: #0F172A !important;
    }

    /* Studio Form Inputs & Textarea */
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
        background-color: #FFFFFF !important;
        border-radius: 10px !important;
        border: 1px solid #E2E8F0 !important;
        color: #0F172A !important;
        font-size: 0.92rem !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
        transition: all 0.15s ease !important;
    }
    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12) !important;
    }

    /* Studio Main Card Surrounding Script Form */
    div[class*="st-key-main_studio_card"], .videocraft-studio-card {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 16px !important;
        padding: 24px 26px !important;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.04) !important;
        margin-top: 10px !important;
        margin-bottom: 24px !important;
    }

    /* Popover text links */
    div[data-testid="stPopover"] > button {
        background: transparent !important;
        border: none !important;
        color: #4F46E5 !important;
        font-size: 0.82rem !important;
        font-weight: 700 !important;
        padding: 2px 6px !important;
        box-shadow: none !important;
    }
    div[data-testid="stPopover"] > button:hover {
        background: #EEF2FF !important;
        color: #4338CA !important;
        border-radius: 6px !important;
    }

    /* Feature Pills */
    .feat-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 600;
        color: #475569;
    }
    .feat-tag-hd {
        background: #4F46E5;
        color: #FFFFFF;
        font-size: 0.62rem;
        font-weight: 800;
        padding: 1px 5px;
        border-radius: 4px;
        letter-spacing: 0.04em;
    }

    /* Minimalist Expanders */
    div[data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        margin-bottom: 10px !important;
        box-shadow: none !important;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        color: #1E293B !important;
    }

    /* Streamlit Underline Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom: 1.5px solid #E2E8F0 !important;
        padding: 0 !important;
        gap: 24px !important;
        margin-bottom: 14px !important;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border: none !important;
        border-bottom: 2.5px solid transparent !important;
        padding: 10px 4px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        color: #64748B !important;
        transition: all 0.15s ease !important;
    }
    .stTabs [aria-selected="true"] {
        color: #4F46E5 !important;
        border-bottom: 2.5px solid #4F46E5 !important;
        font-weight: 700 !important;
    }

    /* Progress Bar */
    div[data-testid="stProgress"] > div > div > div > div {
        background: linear-gradient(90deg, #4F46E5, #10B981) !important;
        border-radius: 6px !important;
    }

    /* Video Frame */
    div[data-testid="stVideo"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
    }

    /* Chips */
    .chip {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 5px;
        font-size: 0.72rem;
        font-weight: 700;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .chip-match {
        background: #ECFDF5;
        color: #047857;
        border: 1px solid #A7F3D0;
    }
    .chip-conflict {
        background: #FFFBEB;
        color: #B45309;
        border: 1px solid #FCD34D;
    }

    /* Timeline & Storyboard (Clean & Uncluttered) */
    .timeline-container {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 16px;
    }
    .timeline-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
    }
    .timeline-title {
        font-size: 0.82rem;
        font-weight: 700;
        color: #1E293B;
    }
    .timeline-track-title {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748B;
        margin-bottom: 6px;
    }
    .timeline-track {
        display: flex;
        gap: 6px;
        overflow-x: auto;
        padding-bottom: 4px;
    }
    .timeline-clip {
        flex: 1;
        min-width: 140px;
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 6px 8px;
        display: flex;
        flex-direction: column;
        gap: 3px;
    }
    .timeline-clip-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .timeline-clip-label {
        font-size: 0.72rem;
        font-weight: 700;
        color: #0F172A;
    }
    .timeline-clip-dur {
        font-size: 0.68rem;
        font-weight: 700;
        color: #2563EB;
        background: #EFF6FF;
        padding: 1px 5px;
        border-radius: 4px;
    }
    .timeline-clip-text {
        font-size: 0.7rem;
        color: #64748B;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .asset-card-wrapper {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 8px;
        margin-bottom: 10px;
    }
    .asset-card-selected {
        border: 1.5px solid #2563EB !important;
        background: #F8FAFC !important;
    }

    /* Stepper */
    .stepper-container {
        display: flex;
        align-items: center;
        gap: 6px;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 8px 14px;
        margin-bottom: 18px;
        overflow-x: auto;
    }
    .step-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        color: #64748B;
        padding: 4px 10px;
        border-radius: 6px;
        white-space: nowrap;
    }
    .step-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #F1F5F9;
        color: #64748B;
        font-size: 0.72rem;
        font-weight: 700;
    }
    .step-item.active {
        color: #2563EB;
        background: #EFF6FF;
    }
    .step-item.active .step-num {
        background: #2563EB;
        color: #FFFFFF;
    }
    .step-item.completed {
        color: #059669;
        background: #ECFDF5;
    }
    .step-item.completed .step-num {
        background: #10B981;
        color: #FFFFFF;
    }
    .step-arrow {
        color: #CBD5E1;
        font-size: 0.72rem;
    }

    /* Responsive Mobile Adjustments */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }
        div.stButton > button {
            min-height: 42px !important;
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

# -------------------------------------------------------------
# 🔒 STUDIO SECURITY & PIN ACCESS CONTROL
# -------------------------------------------------------------
STUDIO_ACCESS_PIN = os.environ.get("STUDIO_PIN", "Harshad")

if "studio_authenticated" not in st.session_state:
    st.session_state.studio_authenticated = False

def render_pin_lock_screen():
    st.write("")
    st.write("")
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        st.markdown("""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 28px 24px 20px 24px; text-align: center; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div style="font-size: 2rem; margin-bottom: 8px;">🔒</div>
            <div style="font-size: 1.25rem; font-weight: 800; color: #0F172A; letter-spacing: -0.02em;">VideoCraft Studio</div>
            <div style="font-size: 0.78rem; color: #64748B; margin-top: 2px;">Enter 4-digit PIN to access the studio</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("studio_pin_form", clear_on_submit=False):
            pin_val = st.text_input(
                "Security PIN",
                type="password",
                placeholder="Enter PIN (e.g. 0808)...",
                max_chars=12,
                key="studio_pin_box",
                label_visibility="collapsed"
            )
            unlock_clicked = st.form_submit_button("🔓 Unlock Studio", type="primary", use_container_width=True)
            if unlock_clicked:
                if pin_val.strip() == STUDIO_ACCESS_PIN:
                    st.session_state.studio_authenticated = True
                    st.session_state.pin_error = False
                    st.rerun()
                else:
                    st.session_state.pin_error = True

        if st.session_state.get("pin_error"):
            st.error("❌ Incorrect PIN. Access Denied.")

if not st.session_state.studio_authenticated:
    render_pin_lock_screen()
    st.stop()

# Video Ratio / Orientation Global Initialization
cur_ratio = st.session_state.get("select_video_ratio", "16:9 Landscape (YouTube)")
if "9:16" in cur_ratio:
    target_w, target_h = 1080, 1920
    orientation = "vertical"
elif "1:1" in cur_ratio:
    target_w, target_h = 1080, 1080
    orientation = "all"
else:
    target_w, target_h = 1920, 1080
    orientation = "horizontal"

# --- MINIMALIST SIDEBAR ---
with st.sidebar:
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="background: #1E1B4B; color: #FFFFFF; width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.15rem; box-shadow: 0 2px 6px rgba(30,27,75,0.18);">🎬</div>
            <div>
                <div style="font-size: 1.02rem; font-weight: 800; color: #0F172A; line-height: 1.2; letter-spacing: -0.02em;">VideoCraft</div>
                <div style="font-size: 0.65rem; color: #6366F1; font-weight: 700; letter-spacing: 0.05em;">STUDIO PRO</div>
            </div>
        </div>
        <span style="font-size: 0.68rem; color: #059669; background: #ECFDF5; border: 1px solid #A7F3D0; padding: 2px 8px; border-radius: 999px; font-weight: 700;">● Active</span>
    </div>
    <div style="font-size: 0.72rem; font-weight: 800; color: #94A3B8; letter-spacing: 0.08em; text-transform: uppercase; margin: 4px 0 8px 0;">AUDIO SETTINGS</div>
    """, unsafe_allow_html=True)

    # Background Music
    bgm_options = list(BGM_CATALOG.keys()) + ["custom_upload"]
    selected_bgm_key = st.selectbox(
        "🎵 Background Music",
        options=bgm_options,
        format_func=lambda k: "📁 Upload Custom (.mp3)" if k == "custom_upload" else BGM_CATALOG.get(k, {}).get("name", k),
        index=0
    )
    custom_bgm_file = None
    if selected_bgm_key == "custom_upload":
        custom_bgm_file = st.file_uploader("Upload MP3 Track", type=["mp3", "wav"])

    bgm_volume = st.slider(
        "Music Volume",
        min_value=0.02,
        max_value=0.40,
        value=BGM_CATALOG.get(selected_bgm_key, {}).get("default_volume", 0.12),
        step=0.01,
        format="%.2f",
        disabled=(selected_bgm_key == "none")
    )

    # Advanced Settings in Clean Collapsed Expanders
    with st.expander("⚡ Pacing & Speech Speed", expanded=False):
        speed_mode = st.selectbox(
            "Speech Pace",
            options=[
                "1.25x Fast & Punchy (Viral)",
                "1.00x Normal Speech",
                "1.15x Energetic YouTube Pace",
                "1.35x Hyper Fast Pacing"
            ],
            index=0
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

        pause_buffer = st.slider(
            "Pause Buffer (s)",
            min_value=0.10,
            max_value=0.60,
            value=0.20,
            step=0.05
        )
        pacing_mode = "audio_driven"
        default_duration = 3.5
        enable_voiceover = True

    with st.expander("🎨 Subtitles, Badges & Framing", expanded=False):
        burn_subtitles = st.checkbox("Burn Subtitles on Video", value=True)
        subtitle_style_choice = st.selectbox(
            "Subtitle Style",
            [
                "🔥 Creator Viral (Yellow/White Accent + Stroke)",
                "🎬 Studio Box (Translucent Dark Banner)",
                "✨ Minimal Clean (Drop Shadow)"
            ],
            index=0
        )
        burn_badge = st.checkbox("Burn Scene Number Badge", value=True)
        badge_style = st.selectbox("Badge Style", ["Pill (#01)", "Scene Name (Scene 01)", "Minimal (01)"])
        badge_position = st.selectbox("Badge Position", ["Top Left", "Top Right", "Bottom Left", "Bottom Right"])
        ken_burns_style = st.selectbox(
            "Photo Motion Effect",
            [
                "Dynamic Auto (Rotate Zoom & Pan)",
                "Smooth Zoom In (Center Push)",
                "Smooth Zoom Out (Reveal)",
                "Cinematic Pan (Left to Right)",
                "Cinematic Pan (Right to Left)"
            ],
            index=0
        )
        fit_mode = st.radio(
            "Framing Mode",
            options=["cover", "fit"],
            format_func=lambda x: "Crop & Fill (No black bars)" if x == "cover" else "Fit & Pad",
            index=0
        )

    with st.expander("🔑 API Credentials", expanded=False):
        pixabay_key = st.text_input(
            "Pixabay API Key",
            value=DEFAULT_PIXABAY_KEY,
            type="password"
        )
        openai_key = st.text_input(
            "OpenAI API Key (DALL-E Visual Fallback)",
            value=DEFAULT_OPENAI_KEY,
            type="password"
        )

    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 10px; margin-top: 14px; margin-bottom: 12px;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.15rem;">👑</span>
            <div>
                <div style="font-size: 0.84rem; font-weight: 800; color: #92400E;">Studio Pro</div>
                <div style="font-size: 0.68rem; color: #B45309; font-weight: 600;">All features unlocked</div>
            </div>
        </div>
        <span style="color: #92400E; font-size: 0.9rem; font-weight: 700;">›</span>
    </div>
    """, unsafe_allow_html=True)

    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        if st.button("🔒 Lock", help="Lock studio session", use_container_width=True, key="btn_sidebar_lock"):
            st.session_state.studio_authenticated = False
            st.rerun()
    with col_sb2:
        if st.button("🔄 Reset", help="Clear all studio state", use_container_width=True, key="btn_sidebar_reset"):
            for k in list(st.session_state.keys()):
                if k != "studio_authenticated":
                    st.session_state.pop(k, None)
            st.rerun()


# Voice Model Selection Modal Dialog
if hasattr(st, "dialog"):
    @st.dialog("🎙️ Choose Script Speech Model & Voice Narrator")
    def open_voice_selection_dialog():
        st.markdown("""
        <div style="font-size:0.86rem; color:#475569; margin-bottom:14px; line-height:1.4;">
            Select an AI voice narrator model for your script. Listen to a live sample before confirming!
        </div>
        """, unsafe_allow_html=True)

        lang_tab1, lang_tab2, lang_tab3 = st.tabs(["🇮🇳 Hindi & Hinglish", "🚩 Marathi (मराठी)", "🇺🇸 English Voices"])

        with lang_tab1:
            hindi_voices = {k: v for k, v in VOICE_CATALOG.items() if "hi-IN" in k or "en-IN" in k}
            curr_v = st.session_state.get("selected_voice", DEFAULT_VOICE)
            h_idx = list(hindi_voices.keys()).index(curr_v) if curr_v in hindi_voices else 0
            h_choice = st.radio(
                "Select Hindi / Hinglish Voice Model:",
                options=list(hindi_voices.keys()),
                format_func=lambda k: hindi_voices[k],
                index=h_idx,
                key="dialog_hindi_voice"
            )
            col_dh1, col_dh2 = st.columns(2)
            with col_dh1:
                if st.button("🎧 Listen Sample", key="dialog_btn_h_sample", use_container_width=True):
                    sample_p = DOWNLOADS_DIR / f"sample_{h_choice}.mp3"
                    with st.spinner("Synthesizing Hindi sample..."):
                        dur = generate_human_voiceover("Namaste dosto. Yeh human voiceover aapke YouTube video ke liye ready hai.", sample_p, voice=h_choice)
                        if sample_p.exists():
                            st.audio(str(sample_p), format="audio/mp3")
            with col_dh2:
                if st.button("✅ Apply Voice", type="primary", key="btn_apply_hindi", use_container_width=True):
                    st.session_state.selected_voice = h_choice
                    st.success(f"Selected: {VOICE_CATALOG.get(h_choice, h_choice)}!")
                    st.rerun()

        with lang_tab2:
            marathi_voices = {k: v for k, v in VOICE_CATALOG.items() if "mr-IN" in k}
            curr_v = st.session_state.get("selected_voice", DEFAULT_VOICE)
            m_idx = list(marathi_voices.keys()).index(curr_v) if curr_v in marathi_voices else 0
            m_choice = st.radio(
                "Select Marathi Voice Model (मराठी आवाज):",
                options=list(marathi_voices.keys()),
                format_func=lambda k: marathi_voices[k],
                index=m_idx,
                key="dialog_marathi_voice"
            )
            col_dm1, col_dm2 = st.columns(2)
            with col_dm1:
                if st.button("🎧 Listen Marathi Sample", key="dialog_btn_m_sample", use_container_width=True):
                    sample_p = DOWNLOADS_DIR / f"sample_{m_choice}.mp3"
                    with st.spinner("Synthesizing Marathi sample..."):
                        dur = generate_human_voiceover("नमस्कार मित्रांनो. हे व्हॉईसओव्हर तुमच्या युट्यूब व्हिडिओसाठी तयार आहे.", sample_p, voice=m_choice)
                        if sample_p.exists():
                            st.audio(str(sample_p), format="audio/mp3")
            with col_dm2:
                if st.button("✅ Apply Marathi Voice", type="primary", key="btn_apply_marathi", use_container_width=True):
                    st.session_state.selected_voice = m_choice
                    st.success(f"Selected: {VOICE_CATALOG.get(m_choice, m_choice)}!")
                    st.rerun()

        with lang_tab3:
            eng_voices = {k: v for k, v in VOICE_CATALOG.items() if "en-US" in k or "en-GB" in k}
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
    status_container=None,
    render_bar=None,
    existing_scenes=None,
    existing_scene_assets=None,
    existing_selected_assets=None,
    progress_callback=None,
    cancel_event=None
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
    def notify(pct, msg, state="info"):
        if progress_callback:
            try:
                progress_callback(pct, msg, state)
            except Exception:
                pass
        if status_container:
            try:
                if state == "error":
                    status_container.error(msg)
                elif state == "success":
                    status_container.success(msg)
                else:
                    status_container.info(msg)
            except Exception:
                pass
        if render_bar and pct is not None:
            try:
                render_bar.progress(min(1.0, max(0.0, float(pct))))
            except Exception:
                pass

    if cancel_event and cancel_event.is_set():
        notify(None, "⚠️ Video generation cancelled by user.", state="error")
        return None

    cleanup_storage_cache()
    job_timestamp = time.strftime('%Y%m%d_%H%M%S')
    job_dir = DOWNLOADS_DIR / f"job_{job_timestamp}"
    job_dir.mkdir(parents=True, exist_ok=True)

    # 1. SCENES
    if existing_scenes:
        scenes = existing_scenes
    else:
        notify(0.05, "📝 [1/4] Analyzing script into story scenes...")
        scenes = parse_script_to_scenes(
            script_text,
            default_duration=3.5,
            default_media=media_pref,
            speed=speed_mult,
            main_topic=main_topic
        )
    if not scenes:
        notify(None, "❌ Failed to parse script into scenes.", state="error")
        return None

    # 🧠 Studio Brain: Optimize Scene 1 Opening Hook for maximum retention
    if scenes:
        try:
            enhanced_hook_kw, hook_tip = StudioBrain.optimize_hook_scene(
                scene_text=scenes[0].get('text', ''),
                current_keyword=scenes[0].get('keyword', main_topic)
            )
            scenes[0]['keyword'] = enhanced_hook_kw
            scenes[0]['media_pref'] = 'video'  # Opening hook is always high-motion video
            if hook_tip:
                notify(None, hook_tip, state="info")
        except Exception as brain_err:
            print(f"Hook optimization notice: {brain_err}")

    if cancel_event and cancel_event.is_set():
        notify(None, "⚠️ Video generation cancelled by user.", state="error")
        return None

    # 2. ASSET SEARCH & SELECTION (100% in Background)
    if existing_scene_assets and existing_selected_assets:
        scene_assets_dict = existing_scene_assets
        selected_assets_dict = existing_selected_assets
    else:
        notify(0.15, f"🔍 [2/4] Finding unique 1080p clips & AI visuals for {len(scenes)} scenes in parallel...")

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
                if cancel_event and cancel_event.is_set():
                    notify(None, "⚠️ Video generation cancelled by user.", state="error")
                    return None
                try:
                    completed_results.append(fut.result())
                except Exception:
                    orig_idx = futures[fut]
                    completed_results.append((orig_idx, scenes[orig_idx], []))
                done_count += 1
                notify(0.15 + (done_count / total_s) * 0.15, f"🔍 Finding visual assets ({done_count}/{total_s})...")

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
    notify(0.35, "🎙️ [3/4] Synthesizing human voice narration & downloading visuals...")

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
            if cancel_event and cancel_event.is_set():
                notify(None, "⚠️ Video generation cancelled by user.", state="error")
                return None
            try:
                res_p = fut.result()
                prep_results.append(res_p)
            except Exception as prep_err:
                print(f"Pre-fetch error for scene: {prep_err}")
            done_prep += 1
            notify(0.35 + (done_prep / total_scenes) * 0.25, f"🎙️ Synthesizing voice & visuals ({done_prep}/{total_scenes})...")

    prep_results.sort(key=lambda x: x["index"])
    for pr in prep_results:
        # Collect voiceover narration audio, subtitle overlays, and AI visual cards
        # DO NOT bundle 40MB+ raw unedited stock videos into the ZIP (processed clips are already in the ZIP)
        if pr.get("audio_path"):
            numbered_assets_for_zip.append(pr["audio_path"])
        if pr.get("overlay_path"):
            numbered_assets_for_zip.append(pr["overlay_path"])
        if pr.get("raw_path") and (pr.get("is_img") or "fallback" in str(pr.get("raw_path")) or "card" in str(pr.get("raw_path"))):
            numbered_assets_for_zip.append(pr["raw_path"])

    # 4. PHASE 2: VIDEO ENCODING
    notify(0.60, "🎬 [4/4] Multi-core video rendering & merging final video...")

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
            if cancel_event and cancel_event.is_set():
                notify(None, "⚠️ Video generation cancelled by user.", state="error")
                return None
            try:
                i_res, cp_res, ok_res = fut.result()
                encoded_clips.append((i_res, cp_res, ok_res))
            except Exception as enc_err:
                print(f"Encoding error: {enc_err}")
            done_enc += 1
            notify(0.60 + (done_enc / total_scenes) * 0.30, f"🎬 Rendering scenes ({done_enc}/{total_scenes})...")

    encoded_clips.sort(key=lambda x: x[0])
    processed_clips = [cp for i_idx, cp, ok_val in encoded_clips if ok_val and cp.exists() and cp.stat().st_size > 0]
    if not processed_clips:
        notify(None, "❌ Error: None of the scene clips could be encoded.", state="error")
        return None

    if cancel_event and cancel_event.is_set():
        notify(None, "⚠️ Video generation cancelled by user.", state="error")
        return None

    # Merge
    notify(0.92, "🎬 Merging scene clips with seamless cuts...")
    raw_merged_file = job_dir / f"scenes_merged_{job_timestamp}.mp4"
    merge_ok = merge_clips_to_final_video(processed_clips, raw_merged_file)

    if not merge_ok or not raw_merged_file.exists() or raw_merged_file.stat().st_size == 0:
        notify(None, "❌ Error: Failed to merge scene clips into final video.", state="error")
        return None

    final_merged_file = DOWNLOADS_DIR / f"merged_video_{job_timestamp}.mp4"

    active_bgm_path = None
    if bgm_k == "custom_upload" and custom_bgm:
        if isinstance(custom_bgm, (str, Path)):
            cand_p = Path(custom_bgm)
            if cand_p.exists():
                active_bgm_path = cand_p
        elif hasattr(custom_bgm, "name") and hasattr(custom_bgm, "getbuffer"):
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
        notify(0.94, f"🎵 Mixing background music ({bgm_label}) under narration...")
        try:
            bgm_ok = add_background_music_to_video(
                video_path=raw_merged_file,
                bgm_path=active_bgm_path,
                output_path=final_merged_file,
                bgm_volume=bgm_vol,
                fade_out_duration=2.0
            )
            if not bgm_ok or not final_merged_file.exists() or final_merged_file.stat().st_size == 0:
                shutil.copy2(raw_merged_file, final_merged_file)
        except Exception as bgm_err:
            print(f"BGM mixing caught exception: {bgm_err}")
            shutil.copy2(raw_merged_file, final_merged_file)
    else:
        shutil.copy2(raw_merged_file, final_merged_file)

    try:
        os.utime(final_merged_file, None)
    except Exception:
        pass

    if not final_merged_file.exists() or final_merged_file.stat().st_size == 0:
        notify(None, "❌ Error: Final video file could not be verified.", state="error")
        return None

    # ZIP
    notify(0.96, "📦 Packaging assets into numbered ZIP archive...")
    zip_file = DOWNLOADS_DIR / f"assets_{job_timestamp}.zip"
    make_numbered_zip(processed_clips + numbered_assets_for_zip, zip_file)

    # SEO Kit
    notify(0.98, "🚀 Generating Dynamic YouTube Upload Kit & SEO...")
    active_top = main_topic or (scenes[0].get('keyword') if scenes else "YouTube Video")
    seo_kit = generate_youtube_seo_kit(
        topic=active_top,
        script_text=script_text,
        scenes=scenes,
        niche_key=niche_k
    )

    # 🧠 Studio Brain: Record completed video and learn from assets
    try:
        StudioBrain.record_video_completed(
            video_path=str(final_merged_file),
            scenes=scenes,
            selected_assets=selected_assets_dict
        )
    except Exception as learn_err:
        print(f"StudioBrain learning record notice: {learn_err}")

    notify(1.0, "🎉 Video generation complete!", state="success")

    return {
        "merged_video": str(final_merged_file),
        "assets_zip": str(zip_file),
        "youtube_seo_kit": seo_kit,
        "parsed_scenes": scenes,
        "scene_assets": scene_assets_dict,
        "selected_assets": selected_assets_dict
    }

# --- STUDIO HEADER ---
brain_stats = StudioBrain.get_stats()
st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; padding-bottom: 4px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <div style="background: #1E1B4B; color: #FFFFFF; width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.45rem; box-shadow: 0 4px 12px rgba(30, 27, 75, 0.2);">🎬</div>
        <div>
            <div style="font-size: 1.85rem; font-weight: 800; color: #0F172A; letter-spacing: -0.03em; line-height: 1.15;">
                VideoCraft <span style="color: #4F46E5;">Studio</span>
            </div>
            <div style="font-size: 0.88rem; color: #64748B; font-weight: 600; margin-top: 2px;">
                AI Script-to-Video Engine
            </div>
        </div>
    </div>
    <div style="text-align: right;">
        <span style="font-size: 0.75rem; font-weight: 700; background: #EEF2FF; color: #4338CA; padding: 4px 12px; border-radius: 999px; border: 1px solid #C7D2FE; display: inline-flex; align-items: center; gap: 6px;">
            🧠 <span>Self-Learning: <b>Level {brain_stats['level']}</b></span>
        </span>
        <div style="font-size: 0.76rem; color: #94A3B8; font-weight: 500; margin-top: 3px;">
            {brain_stats['total_learned_clips']} Memory Patterns Learned
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Main Studio Tabs
tab1, tab2 = st.tabs(["▶️ Script to Video", "📊 CSV Batch"])

with tab1:
    # -------------------------------------------------------------
    # 🔄 BACKGROUND RENDER JOB DISPATCHER & REAL-TIME PROGRESS
    # -------------------------------------------------------------
    bg_job = BackgroundRenderManager.get_job()
    if bg_job:
        bg_status = bg_job.get("status")
        if bg_status == "completed":
            res = bg_job.get("result")
            if res and isinstance(res, dict):
                st.session_state.merged_video = res.get("merged_video")
                st.session_state.assets_zip = res.get("assets_zip")
                st.session_state.youtube_seo_kit = res.get("youtube_seo_kit")
                st.session_state.parsed_scenes = res.get("parsed_scenes")
                st.session_state.scene_assets = res.get("scene_assets")
                st.session_state.selected_assets = res.get("selected_assets")
                if bg_job.get("topic"):
                    st.session_state.custom_main_topic = bg_job.get("topic")
            BackgroundRenderManager.clear_job()
            st.toast("🎉 Video rendered successfully in the background!", icon="🎬")
            st.rerun()

        elif bg_status in ("error", "failed"):
            err_msg = bg_job.get("error_message") or bg_job.get("error", "Unknown error occurred.")
            st.error(f"❌ Background Video Generation Error: {err_msg}")
            col_err1, _ = st.columns([2, 8])
            with col_err1:
                if st.button("🗑️ Dismiss Error", key="btn_dismiss_bg_error", use_container_width=True):
                    BackgroundRenderManager.clear_job()
                    st.rerun()

        elif bg_status == "cancelled":
            st.warning("⚠️ Background video generation was cancelled.")
            col_can1, _ = st.columns([2, 8])
            with col_can1:
                if st.button("🗑️ Dismiss", key="btn_dismiss_bg_cancel", use_container_width=True):
                    BackgroundRenderManager.clear_job()
                    st.rerun()

        elif bg_status == "running":
            if not BackgroundRenderManager.is_running():
                st.warning("⚠️ The previous background process seems to have stopped unexpectedly.")
                if st.button("🔄 Reset Status", key="btn_reset_stale_job"):
                    BackgroundRenderManager.clear_job()
                    st.rerun()
            else:
                pct = float(bg_job.get("progress", 0.05))
                status_txt = bg_job.get("status_text", "Processing video in background...")
                elapsed_sec = int(time.time() - bg_job.get("started_at", time.time()))
                e_mins, e_secs = divmod(elapsed_sec, 60)
                job_topic = bg_job.get("topic", "YouTube Video")

                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #0F172A 0%, #1E1B4B 100%); border: 2px solid #6366F1; border-radius: 16px; padding: 22px 24px; margin-bottom: 24px; box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.25);">
                    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom: 12px; flex-wrap:wrap; gap:10px;">
                        <div style="display:flex; align-items:center; gap:12px;">
                            <span style="font-size: 1.6rem;">⚡</span>
                            <div>
                                <div style="font-weight: 800; color: #FFFFFF; font-size: 1.12rem; letter-spacing: -0.01em;">
                                    Background Rendering Active: <span style="color:#A5B4FC;">{job_topic}</span>
                                </div>
                                <div style="font-size: 0.82rem; color: #94A3B8; margin-top:2px;">
                                    🛡️ <b>Phone Screen Off / Minimize Safe:</b> Running on Windows background OS thread with sleep prevention.
                                </div>
                            </div>
                        </div>
                        <div>
                            <span style="background: rgba(99, 102, 241, 0.25); border: 1px solid #818CF8; color: #C7D2FE; font-weight: 700; font-size: 0.85rem; padding: 4px 14px; border-radius: 999px;">
                                ⏱️ {e_mins:02d}:{e_secs:02d} elapsed
                            </span>
                        </div>
                    </div>
                    <div style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 12px 16px; color: #E0E7FF; font-size: 0.92rem; font-weight: 600; margin: 14px 0 12px 0;">
                        {status_txt}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.progress(pct)

                col_b_msg, col_b_btn = st.columns([3.5, 1.5])
                with col_b_msg:
                    st.caption("📱 <i>Tip: You can safely lock your phone, switch to other apps, or close this browser tab. Come back anytime to see your video!</i>", unsafe_allow_html=True)
                with col_b_btn:
                    if st.button("⏹️ Cancel Render", key="btn_bg_cancel_render", type="secondary", use_container_width=True):
                        BackgroundRenderManager.cancel_job()
                        st.toast("Cancellation requested...", icon="⏹️")
                        st.rerun()

                time.sleep(2.0)
                st.rerun()

    # Mobile Connection Auto-Recovery: Restore most recently generated video if session reset
    if not st.session_state.get("merged_video"):
        recent_vids = sorted(DOWNLOADS_DIR.glob("merged_video_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if recent_vids and (time.time() - recent_vids[0].stat().st_mtime) < 86400:
            st.session_state.merged_video = str(recent_vids[0])
            recent_zips = sorted(DOWNLOADS_DIR.glob("assets_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
            if recent_zips:
                st.session_state.assets_zip = str(recent_zips[0])

    has_merged = bool(st.session_state.get("merged_video"))

    # =====================================================================
    # 🎬 FINAL VIDEO EXPORT (CLEAN, PROMINENT AT TOP)
    # =====================================================================
    if has_merged:
        merged_path = Path(st.session_state.merged_video)
        if merged_path.exists():
            active_topic_raw = st.session_state.get("custom_main_topic") or ""
            if not active_topic_raw and st.session_state.get("youtube_seo_kit"):
                titles_list = st.session_state["youtube_seo_kit"].get("titles", [])
                if titles_list:
                    active_topic_raw = titles_list[0]
            if not active_topic_raw:
                cur_scenes = st.session_state.get("parsed_scenes", [])
                active_topic_raw = st.session_state.get("current_topic") or (cur_scenes[0].get('keyword') if cur_scenes else "YouTube_Video")

            topic_slug = slugify(active_topic_raw)
            file_mb = round(merged_path.stat().st_size / (1024 * 1024), 2)
            scenes_count = len(st.session_state.get("parsed_scenes", []))
            actual_dur = get_audio_duration(merged_path)

            mins_dur = actual_dur / 60.0
            st.markdown(f"""
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; padding:12px 18px; background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:1.1rem; font-weight:800; color:#0F172A;">🎬 Final Video Preview</span>
                    <span style="background:#ECFDF5; color:#059669; font-size:0.72rem; font-weight:700; padding:2px 8px; border-radius:999px; border:1px solid #A7F3D0;">● Ready</span>
                </div>
                <div style="font-size:0.8rem; color:#64748B; font-weight:600;">
                    {scenes_count} Scenes · {actual_dur:.1f}s ({mins_dur:.1f} min) · {target_w}x{target_h} · {file_mb} MB
                </div>
            </div>
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 14px; margin-bottom:12px; font-size:0.82rem; color:#475569; display:flex; align-items:center; justify-content:space-between;">
                <div>📁 <b>Saved File:</b> <code style="color:#2563EB;">{merged_path.name}</code> ({file_mb} MB)</div>
                <div style="font-size:0.75rem; color:#10B981; font-weight:600;">✅ Permanently preserved in downloads folder</div>
            </div>
            """, unsafe_allow_html=True)

            # Embedded Video Player
            st.video(str(merged_path))

            with st.expander("🔊 Audio Track & Voiceover Check (Optional)", expanded=False):
                st.caption("💡 Note: Video player above already plays full voiceover and music. Load this only if you want to test audio separately.")
                if st.checkbox("Load separate audio player widget", key="chk_load_audio_player"):
                    st.audio(str(merged_path), format="audio/mp4")

            # Action Buttons Row (Memory-safe streaming: 0 MB loaded on page render)
            st.write("")
            dl_col1, dl_col2, dl_col3, dl_col4 = st.columns([2.5, 2, 1.8, 1.2])
            with dl_col1:
                def _stream_final_video():
                    return open(merged_path, "rb")

                st.download_button(
                    label=f"⬇️ Download Video ({topic_slug}_Video.mp4)",
                    data=_stream_final_video,
                    file_name=f"{topic_slug}_Video.mp4",
                    mime="video/mp4",
                    type="primary",
                    key="btn_top_dl_vid",
                    use_container_width=True
                )
            with dl_col2:
                if st.session_state.get("assets_zip"):
                    zip_p = Path(st.session_state.assets_zip)
                    if zip_p.exists():
                        def _stream_assets_zip():
                            return open(zip_p, "rb")

                        st.download_button(
                            label="📦 Download Archive ZIP",
                            data=_stream_assets_zip,
                            file_name=f"{topic_slug}_Assets.zip",
                            mime="application/zip",
                            key="btn_top_dl_zip",
                            use_container_width=True
                        )
            with dl_col3:
                if st.button("📂 Open in Explorer", key="btn_top_open_loc", use_container_width=True, help="Directly opens and highlights the video file in Windows File Explorer"):
                    try:
                        subprocess.Popen(f'explorer.exe /select,"{str(merged_path.resolve())}"')
                    except Exception as exp_err:
                        st.info(f"File path: {str(merged_path.resolve())}")
            with dl_col4:
                if st.button("✨ New Video", use_container_width=True, help="Clear and create a fresh video"):
                    for k in ["merged_video", "assets_zip", "parsed_scenes", "scene_assets", "selected_assets", "youtube_seo_kit"]:
                        st.session_state.pop(k, None)
                    st.rerun()

            # 🧠 Self-Learning Feedback Loop & Quality Training Bar
            cur_brain = StudioBrain.get_stats()
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1E1B4B 0%, #0F172A 100%); border: 1.5px solid #6366F1; border-radius: 12px; padding: 14px 18px; margin: 16px 0 12px 0;">
                <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="font-size:1.35rem;">🧠</span>
                        <div>
                            <span style="font-weight:800; color:#FFFFFF; font-size:0.92rem;">Self-Learning Video Engine</span>
                            <span style="background:rgba(99,102,241,0.25); border:1px solid #818CF8; color:#C7D2FE; font-size:0.75rem; font-weight:700; padding:2px 8px; border-radius:999px; margin-left:6px;">{cur_brain['level_title']}</span>
                            <div style="font-size:0.75rem; color:#94A3B8; margin-top:2px;">
                                📈 <b>{cur_brain['total_learned_clips']}</b> visual memory patterns · <b>{cur_brain['total_videos']}</b> videos analyzed · Quality auto-tuner active
                            </div>
                        </div>
                    </div>
                    <div style="font-size:0.78rem; font-weight:700; color:#A5B4FC;">
                        Rate this video to train future video quality ➔
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            fb_col1, fb_col2, fb_col3 = st.columns(3)
            with fb_col1:
                if st.button("🔥 Viral Quality! (Boost Clips +5)", key="btn_fb_viral", use_container_width=True, help="Teaches AI to strongly prefer these styles & keywords in future videos"):
                    cur_assets = list(st.session_state.get("selected_assets", {}).values())
                    StudioBrain.apply_feedback("viral", cur_assets)
                    st.toast("🧠 Brain upgraded! High-retention clips reinforced.", icon="🔥")
                    st.rerun()
            with fb_col2:
                if st.button("👍 Good Visuals (+2 Score)", key="btn_fb_good", use_container_width=True):
                    cur_assets = list(st.session_state.get("selected_assets", {}).values())
                    StudioBrain.apply_feedback("good", cur_assets)
                    st.toast("🧠 Brain feedback saved (+2 quality points).", icon="👍")
                    st.rerun()
            with fb_col3:
                if st.button("👎 Poor Clips (Blacklist / -4)", key="btn_fb_bad", use_container_width=True, help="Down-ranks or blacklists clips so they never reappear"):
                    cur_assets = list(st.session_state.get("selected_assets", {}).values())
                    StudioBrain.apply_feedback("bad", cur_assets)
                    st.toast("🧠 Bad clips down-ranked and pruned from future videos.", icon="🛡️")
                    st.rerun()

            # YouTube SEO Kit in an unobtrusive expander
            active_niche_k = st.session_state.get("selected_niche", "history")
            active_top = st.session_state.get("custom_main_topic") or (st.session_state.get("parsed_scenes", [{}])[0].get('keyword') if st.session_state.get("parsed_scenes") else "Ancient Mysteries")
            if not st.session_state.get("youtube_seo_kit"):
                st.session_state.youtube_seo_kit = generate_youtube_seo_kit(
                    topic=active_top,
                    script_text=st.session_state.get("active_script_content", ""),
                    scenes=st.session_state.get("parsed_scenes", []),
                    niche_key=active_niche_k
                )
            seo_kit = st.session_state.get("youtube_seo_kit", {})

            with st.expander("🚀 YouTube SEO Kit (Titles, Tags & Description with Chapters)", expanded=False):
                col_titles_box, col_tags_box = st.columns(2)
                with col_titles_box:
                    st.markdown("##### 🎯 3 Clickbait Titles:")
                    for t_idx, t_str in enumerate(seo_kit.get("titles", []), start=1):
                        st.markdown(f"**#{t_idx}** {t_str}")
                with col_tags_box:
                    st.markdown("##### 🏷️ 28-30 Viral Tags:")
                    st.code(seo_kit.get("tags", ""), language="text")

                st.markdown("##### 📝 Full Description (Auto Timestamps & Chapters):")
                st.code(seo_kit.get("description", ""), language="markdown")

                seo_txt_content = f"""======================================================================
YOUTUBE STUDIO UPLOAD KIT: {active_topic_raw}
======================================================================

🎯 CLICKBAIT TITLES:
1. {seo_kit.get('titles', [''])[0] if seo_kit.get('titles') else ''}
2. {seo_kit.get('titles', ['', ''])[1] if len(seo_kit.get('titles', [])) > 1 else ''}
3. {seo_kit.get('titles', ['', '', ''])[2] if len(seo_kit.get('titles', [])) > 2 else ''}

======================================================================
📝 FULL DESCRIPTION:
======================================================================
{seo_kit.get('description', '')}

======================================================================
🏷️ VIRAL TAGS:
======================================================================
{seo_kit.get('tags', '')}

======================================================================
💬 PINNED COMMENT:
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

            st.markdown("<hr style='margin: 22px 0 18px 0; border: none; border-top: 1px solid #E2E8F0;'/>", unsafe_allow_html=True)

    # =====================================================================
    # 📝 VIDEOCRAFT STUDIO SCRIPT COMPOSER CARD
    # =====================================================================
    active_niche_k = st.session_state.get("selected_niche", "history")

    # Main Studio Form Card
    with st.container(border=True, key="main_studio_card"):
        # Script Input directly at top
        initial_script = st.session_state.get("active_script_content", "")

        col_tip_l, col_tip_r = st.columns([4, 1])
        with col_tip_l:
            st.markdown("""
            <div style="margin-top: 4px; margin-bottom: 4px;">
                <span style="font-size: 0.95rem; font-weight: 700; color: #0F172A;">✏️ Your script <span style="font-size: 0.8rem; font-weight: 500; color: #64748B;">(One line = one scene)</span></span>
            </div>
            """, unsafe_allow_html=True)
        with col_tip_r:
            with st.popover("💡 Tips"):
                st.markdown("""
                **Scriptwriting Tips:**
                - **1 Line = 1 Scene** (~3–5 seconds of video each).
                - Write engaging sentences describing clear visual action.
                - Avoid punctuation clutter or emojis for smoothest voice synthesis.
                """)

        script_input = st.text_area(
            "Your Script",
            value=initial_script,
            height=190,
            placeholder="Type or paste your script line by line...\nEach line automatically gets matched with 1080p footage, photo motion, and synced human voice narration.",
            label_visibility="collapsed"
        )

        curr_script_preview = script_input or ""
        line_count = len([line.strip() for line in curr_script_preview.split('\n') if line.strip()])
        char_count = len(curr_script_preview)

        # Auto-extract or keep main topic
        main_topic_input = st.session_state.get("custom_main_topic", "")
        if not main_topic_input and script_input.strip():
            first_lines = [l.strip() for l in script_input.split('\n') if l.strip()]
            if first_lines:
                main_topic_input = re.sub(r'^[0-9\.\-\:\#\*\s]+', '', first_lines[0])[:60].strip()
        if not main_topic_input:
            main_topic_input = st.session_state.get("current_topic", "YouTube_Video")

        col_inf_l, col_inf_r = st.columns([3, 1.5])
        with col_inf_l:
            st.markdown(f"""
            <div style="margin-top: 4px; margin-bottom: 10px;">
                <span style="font-size: 0.78rem; font-weight: 600; color: #64748B;">{line_count} lines • {char_count} characters</span>
            </div>
            """, unsafe_allow_html=True)
        with col_inf_r:
            with st.popover("📄 Example scripts"):
                st.markdown("**Load Sample Niche Script:**")
                for ex_name, ex_script in list(SAMPLE_PRESETS.items())[:3]:
                    if st.button(f"Load: {ex_name}", key=f"btn_load_ex_{slugify(ex_name)}", use_container_width=True):
                        st.session_state.active_script_content = ex_script
                        st.rerun()

        # Row 2: Voice narrator, Video ratio, Footage mix
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            voice_keys = list(VOICE_CATALOG.keys())
            curr_v = st.session_state.get("selected_voice", DEFAULT_VOICE)
            idx_v = voice_keys.index(curr_v) if curr_v in voice_keys else 0
            col_v_dd, col_v_btn = st.columns([4, 1])
            with col_v_dd:
                selected_voice = st.selectbox(
                    "🎙️ Voice narrator",
                    options=voice_keys,
                    format_func=lambda k: {
                        "hi-IN-MadhurNeural": "🇮🇳 Madhur (Hindi Male - Deep)",
                        "hi-IN-SwaraNeural": "🇮🇳 Swara (Hindi Female - Clear)",
                        "en-IN-PrabhatNeural": "🇮🇳 Prabhat (Hinglish Male)",
                        "en-IN-NeerjaExpressiveNeural": "🇮🇳 Neerja (Hinglish Female)",
                        "mr-IN-ManoharNeural": "🚩 Manohar (Marathi Male - Story)",
                        "mr-IN-AarohiNeural": "🚩 Aarohi (Marathi Female - Clear)",
                        "en-US-ChristopherNeural": "🇺🇸 Christopher (US Storyteller)",
                        "en-US-JennyNeural": "🇺🇸 Jenny (US Female)",
                        "en-US-GuyNeural": "🇺🇸 Guy (US Vlogger)",
                        "en-US-AriaNeural": "🇺🇸 Aria (US Professional)",
                        "en-GB-RyanNeural": "🇬🇧 Ryan (British Male)"
                    }.get(k, VOICE_CATALOG.get(k, k).split('(')[0].strip()),
                    index=idx_v
                )
                st.session_state.selected_voice = selected_voice
            with col_v_btn:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button("▶️", help="Preview sample voice", key="btn_quick_voice_play"):
                    sample_file = DOWNLOADS_DIR / f"sample_{selected_voice}.mp3"
                    if not sample_file.exists():
                        if "mr-IN" in selected_voice:
                            p_txt = "नमस्कार मित्रांनो. हे व्हॉईसओव्हर तुमच्या युट्यूब व्हिडिओसाठी तयार आहे."
                        elif "hi-IN" in selected_voice:
                            p_txt = "नमस्ते दोस्तों. यह वॉइसओवर आपके यूट्यूब वीडियो के लिए तैयार है."
                        elif "en-IN" in selected_voice:
                            p_txt = "Hello creators. This Hinglish voiceover is ready for your YouTube video."
                        else:
                            p_txt = "Welcome to VideoCraft Studio. Voice narration is ready."
                        generate_human_voiceover(p_txt, sample_file, voice=selected_voice)
                    if sample_file.exists():
                        st.audio(str(sample_file), format="audio/mp3", autoplay=True)

        with col_c2:
            idx_ratio = 0
            if "9:16" in cur_ratio:
                idx_ratio = 1
            elif "1:1" in cur_ratio:
                idx_ratio = 2
            format_choice = st.selectbox(
                "🖥️ Video ratio",
                options=[
                    "16:9 Landscape (YouTube)",
                    "9:16 Portrait (Shorts/Reels)",
                    "1:1 Square (Social)"
                ],
                index=idx_ratio,
                key="select_video_ratio"
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

        with col_c3:
            global_media_pref = st.selectbox(
                "🎞️ Footage mix",
                ["invideo_mix", "both", "video", "image"],
                format_func=lambda x: {
                    "invideo_mix": "🎯 Smart 60% Video / 40% Photo",
                    "both": "🎬 Best Available 1080p",
                    "video": "🎥 100% Videos Only",
                    "image": "📸 100% Photos Only"
                }.get(x, x)
            )

        # Row 4: Feature Badges
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 18px 0 20px 0;">
            <div class="feat-pill"><span class="feat-tag-hd">HD</span> 1080p output</div>
            <div class="feat-pill"><span>🖼️</span> Auto scene matching</div>
            <div class="feat-pill"><span>〰️</span> Voice sync</div>
            <div class="feat-pill"><span>🛡️</span> Royalty-free media</div>
        </div>
        """, unsafe_allow_html=True)

        # Row 5: Action Buttons
        col_act1, col_act2 = st.columns([3.5, 1.5])
        with col_act1:
            trigger_1click = st.button(
                "🪄 Generate video ➔",
                type="primary",
                use_container_width=True,
                help="Automatically finds best 1080p clips, adds voiceover & music, and builds complete video."
            )
        with col_act2:
            btn_save_draft = st.button(
                "🔖 Save draft",
                type="secondary",
                use_container_width=True
            )
            if btn_save_draft:
                st.session_state.active_script_content = script_input
                st.session_state.custom_main_topic = main_topic_input
                st.toast("✅ Draft saved successfully!", icon="🔖")

        st.markdown("""
        <div style="text-align: center; font-size: 0.78rem; font-weight: 600; color: #94A3B8; margin-top: 10px;">
            Turn your ideas into stunning videos with the power of AI
        </div>
        """, unsafe_allow_html=True)
    if trigger_1click:
        if not script_input.strip():
            st.warning("Please enter or select a script first.")
        elif not pixabay_key:
            st.error("Please ensure the Pixabay API key is set in the sidebar.")
        elif BackgroundRenderManager.is_running():
            st.warning("⚠️ A video generation job is already running in the background. Please wait or cancel it first.")
        else:
            # Prevent mobile phone screen from sleeping if browser kept active
            st.components.v1.html(
                """<script>
                if ('wakeLock' in navigator) {
                    navigator.wakeLock.request('screen').catch(function(){});
                }
                </script>""",
                height=0
            )
            # If custom BGM was uploaded, write to downloads folder for detached background thread
            custom_bgm_path = None
            if custom_bgm_file is not None:
                try:
                    c_bgm_dest = DOWNLOADS_DIR / f"upload_bgm_{int(time.time())}.mp3"
                    with open(c_bgm_dest, "wb") as f_bgm:
                        f_bgm.write(custom_bgm_file.getvalue())
                    custom_bgm_path = str(c_bgm_dest)
                except Exception as bgm_e:
                    print(f"Error saving custom BGM: {bgm_e}")

            job_params = {
                "script_text": script_input,
                "main_topic": main_topic_input,
                "media_pref": global_media_pref,
                "speed_mult": speed_multiplier,
                "tts_rate": tts_rate_str,
                "voice_name": selected_voice,
                "do_voice": enable_voiceover,
                "pb_key": pixabay_key,
                "ai_key": openai_key,
                "tw": target_w,
                "th": target_h,
                "orient": orientation,
                "fit_m": fit_mode,
                "kb_style": ken_burns_style,
                "b_badge": burn_badge,
                "b_style": badge_style,
                "b_pos": badge_position,
                "b_subs": burn_subtitles,
                "sub_style": subtitle_style_choice,
                "p_buffer": pause_buffer,
                "bgm_k": selected_bgm_key,
                "custom_bgm": custom_bgm_path,
                "bgm_vol": bgm_volume,
                "niche_k": active_niche_k,
            }
            st.session_state.active_script_content = script_input
            st.session_state.custom_main_topic = main_topic_input
            ok, j_id = BackgroundRenderManager.start_job(job_params, run_full_auto_video_pipeline)
            if ok:
                st.toast("🚀 Video render started in background!", icon="⚡")
                st.rerun()
            else:
                st.error(f"❌ Could not start background render: {j_id}")

    # Quick Download & Location Banner (Right under generate button so users never miss it)
    if st.session_state.get("merged_video"):
        bot_video_path = Path(st.session_state.merged_video)
        if bot_video_path.exists():
            active_topic_name = st.session_state.get("custom_main_topic") or "YouTube_Video"
            b_slug = slugify(active_topic_name)
            bot_mb = round(bot_video_path.stat().st_size / (1024 * 1024), 2)
            st.markdown(f"""
            <div style="background:#F0FDF4; border:1px solid #86EFAC; border-radius:12px; padding:12px 16px; margin: 14px 0 10px 0;">
                <div style="display:flex; align-items:center; justify-content:space-between;">
                    <span style="font-weight:800; color:#166534; font-size:0.95rem;">🎬 Video Ready ({bot_mb} MB)!</span>
                    <span style="font-size:0.75rem; font-weight:700; color:#15803D; background:#DCFCE7; padding:2px 8px; border-radius:999px;">● Ready</span>
                </div>
                <div style="font-size:0.8rem; color:#4B5563; margin-top:4px;">
                    Saved at: <code>downloads/{bot_video_path.name}</code>. Download or open below.
                </div>
            </div>
            """, unsafe_allow_html=True)
            col_bot_dl1, col_bot_dl2, col_bot_dl3 = st.columns([2, 1.5, 1.5])
            with col_bot_dl1:
                def _stream_bot_video():
                    return open(bot_video_path, "rb")

                st.download_button(
                    label=f"⬇️ Download Video ({b_slug}_Video.mp4)",
                    data=_stream_bot_video,
                    file_name=f"{b_slug}_Video.mp4",
                    mime="video/mp4",
                    type="primary",
                    key="btn_bottom_quick_dl_vid",
                    use_container_width=True
                )
            with col_bot_dl2:
                if st.session_state.get("assets_zip") and Path(st.session_state.assets_zip).exists():
                    bot_zip_path = Path(st.session_state.assets_zip)
                    def _stream_bot_zip():
                        return open(bot_zip_path, "rb")

                    st.download_button(
                        label="📦 Download ZIP",
                        data=_stream_bot_zip,
                        file_name=f"{b_slug}_Assets.zip",
                        mime="application/zip",
                        key="btn_bottom_quick_dl_zip",
                        use_container_width=True
                    )
            with col_bot_dl3:
                if st.button("📂 Open Folder", key="btn_bot_open_folder", use_container_width=True, help="Opens the folder containing your video in Windows File Explorer"):
                    try:
                        subprocess.Popen(f'explorer.exe /select,"{str(bot_video_path.resolve())}"')
                    except Exception as b_err:
                        st.info(f"File path: {str(bot_video_path.resolve())}")

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
                for idx, (no, asset) in enumerate(csv_picks.items()):
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
                    if safe_process_scene_clip(media_path=dest, output_path=clip_p, target_w=target_w, target_h=target_h, duration=default_duration, is_image=is_image, overlay_path=overlay_p, scene_index=idx):
                        clips.append(clip_p)
                if clips:
                    m_dest = DOWNLOADS_DIR / f"csv_merged_{job_ts}.mp4"
                    if merge_clips_to_final_video(clips, m_dest):
                        st.session_state.csv_merged = str(m_dest)
                        st.success("🎉 CSV Video Merged!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to merge CSV clips into final video.")

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
