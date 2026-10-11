import os
import re
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict

import edge_tts
from video_engine import get_ffmpeg_path

VOICE_CATALOG = {
    "hi-IN-MadhurNeural": "🇮🇳 Madhur (Hindi / Indian Accent Male - Deep & Cinematic)",
    "hi-IN-SwaraNeural": "🇮🇳 Swara (Hindi / Indian Accent Female - Expressive & Clear)",
    "en-US-ChristopherNeural": "🇺🇸 Christopher (Storyteller Male - Documentary / Mystery)",
    "en-US-JennyNeural": "🇺🇸 Jenny (Natural Crisp Female - Clean Narration)",
    "en-US-GuyNeural": "🇺🇸 Guy (Casual Male - Modern Vlogger)",
    "en-US-AriaNeural": "🇺🇸 Aria (Studio Female - Professional)",
    "en-GB-RyanNeural": "🇬🇧 Ryan (British Accent Male - Sophisticated)"
}

DEFAULT_VOICE = "hi-IN-MadhurNeural"

def estimate_speech_duration(text: str, speed: float = 1.25) -> float:
    """Estimates speech duration based on word count with speed scaling (default 1.25x Creator speed)."""
    if not text or not text.strip():
        return 2.5
    words = len(text.strip().split())
    eff_wps = 2.3 * max(0.5, speed)
    return round(max(1.8, (words / eff_wps) + (0.22 / speed)), 2)

def get_audio_duration(audio_path: Path) -> float:
    """Accurately calculates audio duration in seconds using FFmpeg probe."""
    try:
        ffmpeg = get_ffmpeg_path()
        r = subprocess.run(
            [ffmpeg, "-i", str(audio_path)],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            timeout=15
        )
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
        if m:
            h, mn, s = map(float, m.groups())
            return round(h * 3600 + mn * 60 + s, 2)
    except Exception as e:
        print(f"Error measuring audio duration: {e}")
    return 5.0

async def _synthesize_edge_tts(text: str, voice: str, output_path: Path, rate: str = "+25%"):
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(str(output_path))

import sys
import concurrent.futures

def _run_in_worker_thread(async_func, *args):
    """Executes an async function inside a fresh worker thread with its own isolated event loop."""
    def _worker():
        return asyncio.run(async_func(*args))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_worker).result()

def generate_human_voiceover(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+25%",
    **kwargs
) -> Optional[float]:
    """
    Generates studio-grade natural human speech using edge-tts.
    Defaults to +25% (1.25x speed) for punchy top creator pacing.
    Runs inside an isolated worker thread to guarantee 100% compatibility with Streamlit.
    Returns audio duration in seconds.
    """
    if not text or not text.strip():
        return None

    clean_text = text.strip()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        _run_in_worker_thread(_synthesize_edge_tts, clean_text, voice, output_path, rate)
        if output_path.exists() and output_path.stat().st_size > 0:
            dur = get_audio_duration(output_path)
            return dur
    except Exception as e:
        print(f"Direct edge-tts worker exception for voice '{voice}': {e}")


    # Robust CLI fallback using sys.executable (always finds installed edge-tts)
    try:
        cmd = [
            sys.executable, "-m", "edge_tts",
            "--text", clean_text,
            "--write-media", str(output_path),
            "--voice", voice,
            "--rate", rate
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return get_audio_duration(output_path)
        else:
            print(f"edge-tts CLI error: {res.stderr[-200:]}")
    except Exception as e2:
        print(f"CLI voiceover fallback error: {e2}")

    return None

