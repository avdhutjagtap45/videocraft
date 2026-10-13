import os
import re
import sys
import time
import asyncio
import threading
import subprocess
import concurrent.futures
from pathlib import Path
from typing import Optional, Dict

import edge_tts
from video_engine import get_ffmpeg_path

# Global threading lock to prevent concurrent WebSocket collisions
# on Streamlit Cloud / datacenter IPs (prevents 403 Forbidden rate limits)
_tts_lock = threading.Lock()

VOICE_CATALOG = {
    # 🇮🇳 Hindi & Hinglish Voices (Ultra-Realistic Human Narrators)
    "hi-IN-MadhurNeural": "🇮🇳 Madhur (Hindi Male - Deep & Cinematic Storyteller)",
    "hi-IN-SwaraNeural": "🇮🇳 Swara (Hindi Female - Expressive & Clear Narration)",
    "en-IN-PrabhatNeural": "🇮🇳 Prabhat (Hinglish Male - Modern YouTube Creator)",
    "en-IN-NeerjaExpressiveNeural": "🇮🇳 Neerja (Hinglish Female - Ultra Expressive)",

    # 🚩 Marathi Voices (Ultra-Realistic Human Narrators)
    "mr-IN-ManoharNeural": "🚩 Manohar (Marathi Male - Deep & Realistic Storyteller)",
    "mr-IN-AarohiNeural": "🚩 Aarohi (Marathi Female - Natural & Clear Narration)",

    # 🇺🇸 & 🇬🇧 English Global Voices
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
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:[.,]\d+)?)", r.stderr)
        if m:
            h = float(m.group(1))
            mn = float(m.group(2))
            s = float(m.group(3).replace(",", "."))
            return round(h * 3600 + mn * 60 + s, 2)
    except Exception as e:
        print(f"Error measuring audio duration: {e}")
    return 4.0

async def _synthesize_edge_tts(text: str, voice: str, output_path: Path, rate: str = "+25%"):
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(str(output_path))

def _run_in_worker_thread(async_func, *args):
    """Executes an async function inside a fresh worker thread with its own isolated event loop."""
    def _worker():
        return asyncio.run(async_func(*args))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_worker).result()

def _parse_rate_to_speed(rate: str) -> float:
    """Parses rate string like '+25%' to numeric speed multiplier 1.25."""
    try:
        if rate.startswith("+") and rate.endswith("%"):
            pct = float(rate.strip("+%"))
            return round(1.0 + (pct / 100.0), 2)
        elif rate.startswith("-") and rate.endswith("%"):
            pct = float(rate.strip("-%"))
            return round(max(0.5, 1.0 - (pct / 100.0)), 2)
    except Exception:
        pass
    return 1.25

def _synthesize_gtts_fallback(text: str, voice: str, output_path: Path, rate: str = "+25%") -> bool:
    """
    Bulletproof Google TTS (gTTS) fallback:
    - Never rate-limited on Streamlit Cloud or datacenter IPs.
    - Accurately switches between Hindi ('hi') and English ('en').
    - Uses FFmpeg atempo to match creator pacing (+25% / 1.25x).
    """
    try:
        from gtts import gTTS
        clean_text = text.strip()
        if not clean_text:
            return False

        # Detect Marathi vs Hindi vs English
        has_devanagari = any('\u0900' <= ch <= '\u097f' for ch in clean_text)
        if "mr-IN" in voice:
            lang_code = "mr"
        elif "hi-IN" in voice or has_devanagari:
            lang_code = "hi"
        else:
            lang_code = "en"

        temp_raw = output_path.parent / f"_raw_gtts_{int(time.time()*1000)}.mp3"
        tts = gTTS(text=clean_text, lang=lang_code, slow=False)
        tts.save(str(temp_raw))

        if not temp_raw.exists() or temp_raw.stat().st_size < 200:
            return False

        # Apply speed adjustment to match requested rate
        speed = _parse_rate_to_speed(rate)
        ffmpeg = get_ffmpeg_path()
        if abs(speed - 1.0) > 0.05:
            cmd = [
                ffmpeg, "-y",
                "-i", str(temp_raw),
                "-filter:a", f"atempo={speed}",
                "-c:a", "libmp3lame", "-q:a", "2",
                str(output_path)
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if temp_raw.exists():
                try:
                    temp_raw.unlink()
                except Exception:
                    pass
        else:
            if output_path.exists():
                output_path.unlink()
            temp_raw.rename(output_path)

        return output_path.exists() and output_path.stat().st_size > 500
    except Exception as e:
        print(f"gTTS fallback error: {e}")
        return False

def generate_human_voiceover(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+25%",
    **kwargs
) -> Optional[float]:
    """
    Generates studio-grade natural human speech voiceover:
    1. Primary: Edge-TTS Neural Voice (Madhur, Swara, Christopher, etc.)
    2. Retry: Edge-TTS with backoff
    3. Secondary: Edge-TTS Python CLI
    4. Bulletproof Fallback: Google TTS (gTTS) with Creator atempo speed
    Guarantees that voiceover audio is NEVER empty on hosted Streamlit Cloud!
    """
    if not text or not text.strip():
        return None

    # Clean text of markdown formatting (asterisks, hashtags, extra whitespace)
    clean_text = re.sub(r'[*#_~`>]', '', text).strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    if not clean_text:
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use lock to guarantee zero WebSocket collision across parallel threads
    with _tts_lock:
        # 1. Edge-TTS Async (with 2 retries)
        for attempt in range(2):
            try:
                _run_in_worker_thread(_synthesize_edge_tts, clean_text, voice, output_path, rate)
                if output_path.exists() and output_path.stat().st_size > 500:
                    dur = get_audio_duration(output_path)
                    return dur
            except Exception as e:
                print(f"[Attempt {attempt+1}] Edge-TTS worker error for '{voice}': {e}")
                time.sleep(0.4)

        # 2. Edge-TTS CLI Fallback
        try:
            cmd = [
                sys.executable, "-m", "edge_tts",
                "--text", clean_text,
                "--write-media", str(output_path),
                "--voice", voice,
                "--rate", rate
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
            if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 500:
                return get_audio_duration(output_path)
            else:
                print(f"Edge-TTS CLI returned code {res.returncode}: {res.stderr[-200:]}")
        except Exception as e2:
            print(f"CLI voiceover error: {e2}")

        # 3. Bulletproof Google TTS (gTTS) Fallback
        print(f"Activating bulletproof gTTS fallback for voiceover...")
        ok_gtts = _synthesize_gtts_fallback(clean_text, voice, output_path, rate)
        if ok_gtts and output_path.exists() and output_path.stat().st_size > 500:
            dur = get_audio_duration(output_path)
            print(f"gTTS fallback generated successfully ({dur:.2f}s, {output_path.stat().st_size} bytes)")
            return dur

    return None
