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
    # 🚩 Marathi Voices (Ultra-Realistic Human Narrators)
    "mr-IN-ManoharNeural": "🚩 Manohar (Marathi Male - Deep & Realistic Storyteller)",
    "mr-IN-AarohiNeural": "🚩 Aarohi (Marathi Female - Natural & Clear Narration)",

    # 🇮🇳 Hindi & Hinglish Voices (Ultra-Realistic Human Narrators)
    "hi-IN-MadhurNeural": "🇮🇳 Madhur (Hindi Male - Deep & Cinematic Storyteller)",
    "hi-IN-SwaraNeural": "🇮🇳 Swara (Hindi Female - Expressive & Clear Narration)",
    "en-IN-PrabhatNeural": "🇮🇳 Prabhat (Hinglish Male - Modern YouTube Creator)",
    "en-IN-NeerjaExpressiveNeural": "🇮🇳 Neerja (Hinglish Female - Ultra Expressive)",

    # 🇺🇸 & 🇬🇧 English Global Voices
    "en-US-ChristopherNeural": "🇺🇸 Christopher (Storyteller Male - Documentary / Mystery)",
    "en-US-JennyNeural": "🇺🇸 Jenny (Natural Crisp Female - Clean Narration)",
    "en-US-GuyNeural": "🇺🇸 Guy (Casual Male - Modern Vlogger)",
    "en-US-AriaNeural": "🇺🇸 Aria (Studio Female - Professional)",
    "en-GB-RyanNeural": "🇬🇧 Ryan (British Accent Male - Sophisticated)",

    # 💎 Ultra-Realistic Human AI Studio (Zero Robotic Feel - Optional API Key)
    "elevenlabs_adam": "💎 ElevenLabs Adam (Deep Human Storyteller - Studio Grade)",
    "elevenlabs_rachel": "💎 ElevenLabs Rachel (Calm Narrative Female - Ultra Natural)",
    "openai_onyx": "💎 OpenAI Onyx (Deep Cinematic Male - 100% Human)",
    "openai_echo": "💎 OpenAI Echo (Warm Storyteller Male - Documentary)",
    "openai_nova": "💎 OpenAI Nova (Crisp Professional Female - Studio)"
}

DEFAULT_VOICE = "mr-IN-ManoharNeural"

DEFAULT_ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
DEFAULT_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

def format_speech_cadence(text: str) -> str:
    """
    Cleans text and adds natural punctuation pauses so speech has human rhythm
    and breathing intervals, completely avoiding breathless robotic delivery.
    """
    if not text:
        return ""
    t = text.strip()
    # Normalize dashes and colons to natural pause commas
    t = re.sub(r'[\s]*[–—:][\s]*', ', ', t)
    # Ensure commas have space after
    t = re.sub(r',([^\s])', r', \1', t)
    # Ensure ellipsis doesn't get jammed
    t = re.sub(r'\.{3,}', '... ', t)
    # Clean multiple spaces
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def estimate_speech_duration(text: str, speed: float = 1.0) -> float:
    """Estimates natural human speech duration based on word count with natural pacing (1.0x)."""
    if not text or not text.strip():
        return 2.5
    words = len(text.strip().split())
    eff_wps = 2.1 * max(0.5, speed)
    return round(max(1.8, (words / eff_wps) + (0.30 / speed)), 2)

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

async def _synthesize_edge_tts(text: str, voice: str, output_path: Path, rate: str = "+0%"):
    clean_pacing_text = format_speech_cadence(text)
    communicate = edge_tts.Communicate(text=clean_pacing_text, voice=voice, rate=rate)
    await communicate.save(str(output_path))

def _synthesize_elevenlabs(text: str, voice_key: str, output_path: Path, api_key: str = "") -> bool:
    """
    Synthesizes ultra-realistic human voiceover via ElevenLabs API.
    Zero robotic artifacts, realistic breathing, dynamic emotional inflections.
    """
    key = api_key.strip() or DEFAULT_ELEVENLABS_KEY
    if not key:
        return False
    try:
        import requests
        # Map preset keys to popular ElevenLabs voice IDs
        voice_id_map = {
            "elevenlabs_adam": "pNInz6obpgDQGcFmaJgB",     # Adam
            "elevenlabs_rachel": "21m00Tcm4TlvDq8ikWAM",   # Rachel
            "elevenlabs_antoni": "ErXwobaYiN019PkySvjV",   # Antoni
        }
        vid = voice_id_map.get(voice_key, "pNInz6obpgDQGcFmaJgB")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
        headers = {
            "xi-api-key": key,
            "Content-Type": "application/json"
        }
        body = {
            "text": format_speech_cadence(text),
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.50,
                "similarity_boost": 0.85,
                "style": 0.25,
                "use_speaker_boost": True
            }
        }
        r = requests.post(url, json=body, headers=headers, timeout=30)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(output_path, "wb") as f:
                f.write(r.content)
            return True
        else:
            print(f"ElevenLabs TTS returned code {r.status_code}: {r.text[:150]}")
    except Exception as e:
        print(f"ElevenLabs synthesis error: {e}")
    return False

def _synthesize_openai_tts(text: str, voice_key: str, output_path: Path, api_key: str = "") -> bool:
    """
    Synthesizes studio-quality speech using OpenAI TTS HD engine.
    """
    key = api_key.strip() or DEFAULT_OPENAI_KEY
    if not key or not key.startswith("sk-"):
        return False
    try:
        import requests
        v_name = voice_key.replace("openai_", "").strip() or "onyx"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": "tts-1-hd",
            "input": format_speech_cadence(text),
            "voice": v_name
        }
        r = requests.post("https://api.openai.com/v1/audio/speech", json=body, headers=headers, timeout=30)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(output_path, "wb") as f:
                f.write(r.content)
            return True
        else:
            print(f"OpenAI TTS returned code {r.status_code}: {r.text[:150]}")
    except Exception as e:
        print(f"OpenAI TTS synthesis error: {e}")
    return False

def _run_in_worker_thread(async_func, *args):
    """Executes an async function inside a fresh worker thread with its own isolated event loop."""
    def _worker():
        return asyncio.run(async_func(*args))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_worker).result()

def _parse_rate_to_speed(rate: str) -> float:
    """Parses rate string like '+0%' to numeric speed multiplier 1.0."""
    try:
        if rate.startswith("+") and rate.endswith("%"):
            pct = float(rate.strip("+%"))
            return round(1.0 + (pct / 100.0), 2)
        elif rate.startswith("-") and rate.endswith("%"):
            pct = float(rate.strip("-%"))
            return round(max(0.5, 1.0 - (pct / 100.0)), 2)
    except Exception:
        pass
    return 1.0

def _synthesize_gtts_fallback(text: str, voice: str, output_path: Path, rate: str = "+0%") -> bool:
    """
    Bulletproof Google TTS (gTTS) fallback:
    - Never rate-limited on Streamlit Cloud or datacenter IPs.
    - Accurately switches between Marathi ('mr'), Hindi ('hi'), and English ('en').
    - Uses natural storytelling pace.
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

        # Apply speed adjustment if requested
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

def humanize_vocal_audio(audio_path: Path) -> bool:
    """
    Studio-Grade Vocal Humanizer & Broadcast Mastering Chain:
    Transforms raw synthetic/digital TTS audio into warm, organic human speech:
    - Highpass filter at 75Hz: cuts artificial sub-rumble and mic pops
    - Bass boost at 210Hz (+3.2dB): adds natural human chest resonance
    - Precision dip at 3400Hz (-2.4dB): removes the robotic synthetic digital buzz
    - High-shelf treble roll-off at 6600Hz (-1.5dB): eliminates harsh metallic sibilance
    - Dynamic broadcast vocal compressor: smooths syllable energy like a Shure SM7B studio mic
    """
    if not audio_path.exists() or audio_path.stat().st_size < 500:
        return False
    try:
        ffmpeg = get_ffmpeg_path()
        temp_human = audio_path.parent / f"_human_{audio_path.name}"
        filter_chain = (
            "highpass=f=75,"
            "bass=g=3.2:f=210,"
            "equalizer=f=3400:t=q:w=1.4:g=-2.4,"
            "treble=g=-1.5:f=6600,"
            "acompressor=threshold=-18dB:ratio=3:attack=8:release=60:makeup=2.2,"
            "volume=1.14"
        )
        cmd = [
            ffmpeg, "-y",
            "-i", str(audio_path),
            "-filter:a", filter_chain,
            "-c:a", "libmp3lame", "-q:a", "2",
            str(temp_human)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if r.returncode == 0 and temp_human.exists() and temp_human.stat().st_size > 500:
            temp_human.replace(audio_path)
            return True
    except Exception as e:
        print(f"Humanize audio error: {e}")
    return False

def generate_human_voiceover(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    elevenlabs_key: str = "",
    openai_key: str = "",
    **kwargs
) -> Optional[float]:
    """
    Generates studio-grade natural human speech voiceover:
    1. Ultra-Human Pro: ElevenLabs (Zero AI/robotic artifacts, real breathing & tone)
    2. Ultra-Human Pro: OpenAI TTS HD (Onyx, Echo, Nova)
    3. 100% Free Primary: Edge-TTS Neural Voice at natural 1.0x storytelling cadence
    4. Free Secondary: Edge-TTS CLI fallback
    5. Bulletproof Fallback: Google TTS (gTTS) with natural tempo
    6. Studio Vocal Humanizer & Broadcast Mastering Chain (SM7B warmth & compression)
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

    # 1. Check ElevenLabs Studio Voice if requested
    if voice.startswith("elevenlabs_"):
        ok_el = _synthesize_elevenlabs(clean_text, voice, output_path, api_key=elevenlabs_key)
        if ok_el and output_path.exists() and output_path.stat().st_size > 500:
            humanize_vocal_audio(output_path)
            return get_audio_duration(output_path)
        # Fall back to free edge-tts voice if no key or error
        voice = "mr-IN-ManoharNeural" if any('\u0900' <= ch <= '\u097f' for ch in clean_text) else "en-US-ChristopherNeural"

    # 2. Check OpenAI TTS HD if requested
    if voice.startswith("openai_"):
        ok_oa = _synthesize_openai_tts(clean_text, voice, output_path, api_key=openai_key)
        if ok_oa and output_path.exists() and output_path.stat().st_size > 500:
            humanize_vocal_audio(output_path)
            return get_audio_duration(output_path)
        # Fall back to free edge-tts voice if no key or error
        voice = "mr-IN-ManoharNeural" if any('\u0900' <= ch <= '\u097f' for ch in clean_text) else "en-US-ChristopherNeural"

    # Use lock to guarantee zero WebSocket collision across parallel threads
    with _tts_lock:
        # 3. Edge-TTS Async (with 2 retries)
        for attempt in range(2):
            try:
                _run_in_worker_thread(_synthesize_edge_tts, clean_text, voice, output_path, rate)
                if output_path.exists() and output_path.stat().st_size > 500:
                    humanize_vocal_audio(output_path)
                    dur = get_audio_duration(output_path)
                    return dur
            except Exception as e:
                print(f"[Attempt {attempt+1}] Edge-TTS worker error for '{voice}': {e}")
                time.sleep(0.4)

        # 4. Edge-TTS CLI Fallback
        try:
            cmd = [
                sys.executable, "-m", "edge_tts",
                "--text", format_speech_cadence(clean_text),
                "--write-media", str(output_path),
                "--voice", voice,
                "--rate", rate
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
            if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 500:
                humanize_vocal_audio(output_path)
                return get_audio_duration(output_path)
            else:
                print(f"Edge-TTS CLI returned code {res.returncode}: {res.stderr[-200:]}")
        except Exception as e2:
            print(f"CLI voiceover error: {e2}")

        # 5. Bulletproof Google TTS (gTTS) Fallback
        print(f"Activating bulletproof gTTS fallback for voiceover...")
        ok_gtts = _synthesize_gtts_fallback(clean_text, voice, output_path, rate)
        if ok_gtts and output_path.exists() and output_path.stat().st_size > 500:
            humanize_vocal_audio(output_path)
            dur = get_audio_duration(output_path)
            print(f"gTTS fallback generated successfully ({dur:.2f}s, {output_path.stat().st_size} bytes)")
            return dur

    return None
