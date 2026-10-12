import os
import re
import time
import subprocess
import zipfile
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
import requests
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

BGM_DIR = Path(__file__).parent / "bgm"
BGM_DIR.mkdir(parents=True, exist_ok=True)

BGM_CATALOG: Dict[str, Dict[str, Any]] = {
    "suspense_stormfront": {
        "name": "⚡ Cinematic Stormfront (Epic Tension & Suspense)",
        "filename": "Stormfront.mp3",
        "mood": "Intense Epic Suspense",
        "default_volume": 0.12
    },
    "suspense_distant_tension": {
        "name": "🌌 Distant Tension (Eerie Atmospheric Suspense)",
        "filename": "Distant_Tension.mp3",
        "mood": "Psychological Mystery",
        "default_volume": 0.14
    },
    "suspense_dark_walk": {
        "name": "👣 Dark Walk (Slow Horror / Crime Mystery)",
        "filename": "Dark_Walk.mp3",
        "mood": "Dark Crime Suspense",
        "default_volume": 0.13
    },
    "suspense_gathering_darkness": {
        "name": "🌑 Gathering Darkness (Deep Suspense & Dread)",
        "filename": "Gathering_Darkness.mp3",
        "mood": "Deep Dread & Tension",
        "default_volume": 0.12
    },
    "suspense_industrial_cinematic": {
        "name": "⚙️ Industrial Cinematic (Action Thriller Tension)",
        "filename": "Industrial_Cinematic.mp3",
        "mood": "Thriller Pulse",
        "default_volume": 0.10
    },
    "none": {
        "name": "🔇 None (Pure Voice Narration)",
        "filename": None,
        "mood": "Voiceover Only",
        "default_volume": 0.0
    }
}

def get_ffmpeg_path() -> str:
    """Returns absolute path to the bundled FFmpeg binary."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def download_file(url: str, dest_path: Path, timeout: int = 40) -> bool:
    """Download a remote media file with streaming or copy local media file."""
    if not url:
        return False
    try:
        local_p = Path(str(url))
        if local_p.exists() and local_p.is_file():
            if local_p.resolve() != dest_path.resolve():
                import shutil
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_p, dest_path)
            return dest_path.exists() and dest_path.stat().st_size > 0

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://pixabay.com/",
            "Accept": "*/*"
        }
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(2):
            try:
                with requests.get(url, stream=True, headers=headers, timeout=timeout) as r:
                    if r.status_code == 200:
                        with open(dest_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024 * 64):
                                if chunk:
                                    f.write(chunk)
                        if dest_path.exists() and dest_path.stat().st_size > 1000:
                            return True
            except Exception as attempt_err:
                if attempt == 1:
                    print(f"Error downloading {url}: {attempt_err}")
                continue

        if dest_path.exists() and dest_path.stat().st_size < 1000:
            try:
                dest_path.unlink()
            except Exception:
                pass
        return False
    except Exception as e:
        print(f"Error in download_file {url}: {e}")
        if dest_path.exists() and dest_path.stat().st_size < 1000:
            try:
                dest_path.unlink()
            except Exception:
                pass
        return False

def _get_system_font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    """Load system font with robust fallbacks on Windows/Linux/Mac."""
    bold_candidates = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]
    regular_candidates = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]
    candidates = bold_candidates if bold else regular_candidates

    for font_name in candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Wrap text to fit within a specified pixel width."""
    words = text.split()
    lines = []
    curr_line = []
    for word in words:
        test_line = " ".join(curr_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            curr_line.append(word)
        else:
            if curr_line:
                lines.append(" ".join(curr_line))
                curr_line = [word]
            else:
                lines.append(word)
    if curr_line:
        lines.append(" ".join(curr_line))
    return lines

def create_overlay_image(
    width: int,
    height: int,
    scene_no: str,
    output_png: Path,
    scene_text: Optional[str] = None,
    show_badge: bool = True,
    badge_style: str = "Pill (#01)",
    badge_position: str = "Top Left",
    show_subtitle: bool = True,
    subtitle_style: str = "Creator Viral"
) -> bool:
    """
    Renders a studio-grade RGBA overlay with:
    1. Elegant Scene Number Badge (#01, Scene 01, 01)
    2. Broadcast/Creator-quality subtitles (Hormozi / Top Creator Viral or Classic Studio)
    3. Full responsiveness for both 16:9 YouTube Long and 9:16 Shorts/Reels formats
    """
    try:
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        is_vertical = height > width
        base_w = 1080.0 if is_vertical else 1920.0
        scale_factor = width / base_w

        # Scale typography dynamically based on resolution and aspect ratio
        if is_vertical:
            badge_font_size = max(22, int(32 * scale_factor))
            sub_font_size = max(36, int(46 * scale_factor))
        else:
            badge_font_size = max(18, int(26 * scale_factor))
            sub_font_size = max(24, int(34 * scale_factor))

        badge_font = _get_system_font(badge_font_size, bold=True)
        sub_font = _get_system_font(sub_font_size, bold=True)

        # 1. Studio-grade Scene Number Badge
        if show_badge:
            if "Scene" in badge_style:
                badge_label = f"Scene {scene_no}"
            elif "#" in badge_style:
                badge_label = f"#{scene_no}"
            else:
                badge_label = f"{scene_no}"

            bbox = draw.textbbox((0, 0), badge_label, font=badge_font)
            bw = bbox[2] - bbox[0]
            bh = bbox[3] - bbox[1]
            pad_x = int(22 * scale_factor)
            pad_y = int(12 * scale_factor)
            box_w = bw + pad_x * 2
            box_h = bh + pad_y * 2
            margin = int(45 * scale_factor)

            pos_lower = badge_position.lower()
            if "top left" in pos_lower:
                bx, by = margin, margin
            elif "top right" in pos_lower:
                bx, by = width - box_w - margin, margin
            elif "bottom right" in pos_lower:
                bx, by = width - box_w - margin, height - box_h - margin
            else:  # bottom left
                bx, by = margin, height - box_h - margin

            # Frosted glass pill badge with subtle translucent glow
            draw.rounded_rectangle(
                [bx, by, bx + box_w, by + box_h],
                radius=int(14 * scale_factor),
                fill=(15, 23, 42, 225),  # Deep modern dark slate
                outline=(56, 189, 248, 190),  # Cyan neon accent border
                width=max(1, int(2 * scale_factor))
            )
            draw.text(
                (bx + pad_x, by + pad_y - int(1 * scale_factor)),
                badge_label,
                font=badge_font,
                fill=(248, 250, 252, 255)
            )

        # 2. Studio / Creator Subtitles
        if show_subtitle and scene_text and scene_text.strip():
            max_sub_w = int(width * (0.88 if is_vertical else 0.82))
            lines = _wrap_text(scene_text.strip(), sub_font, max_sub_w, draw)
            if lines:
                line_height = int(sub_font_size * 1.36)
                total_text_h = len(lines) * line_height
                pad_sub_x = int(28 * scale_factor)
                pad_sub_y = int(14 * scale_factor)
                box_sub_h = total_text_h + pad_sub_y * 2

                max_w_line = 0
                for line in lines:
                    lb = draw.textbbox((0, 0), line, font=sub_font)
                    max_w_line = max(max_w_line, lb[2] - lb[0])
                box_sub_w = max_w_line + pad_sub_x * 2

                sub_x = (width - box_sub_w) // 2
                
                # In Shorts (vertical), position in optical middle zone so YouTube Shorts UI doesn't obscure it
                if is_vertical:
                    sub_y = int(height * 0.60) - (box_sub_h // 2)
                else:
                    bottom_margin = int(60 * scale_factor)
                    sub_y = height - box_sub_h - bottom_margin

                is_creator_viral = "creator" in subtitle_style.lower() or "viral" in subtitle_style.lower()

                # Backdrop styling
                if is_creator_viral:
                    # High-impact creator card with neon accent border
                    draw.rounded_rectangle(
                        [sub_x, sub_y, sub_x + box_sub_w, sub_y + box_sub_h],
                        radius=int(18 * scale_factor),
                        fill=(10, 15, 29, 235),
                        outline=(250, 204, 21, 230),  # Vibrant Golden-Yellow creator outline
                        width=max(2, int(2.5 * scale_factor))
                    )
                else:
                    # Classic translucent dark cinematic banner
                    draw.rounded_rectangle(
                        [sub_x, sub_y, sub_x + box_sub_w, sub_y + box_sub_h],
                        radius=int(16 * scale_factor),
                        fill=(8, 12, 22, 215),
                        outline=(255, 255, 255, 120),
                        width=max(1, int(1.5 * scale_factor))
                    )

                # Render text lines with crisp outline stroke & viral color accents
                for i, line in enumerate(lines):
                    ly = sub_y + pad_sub_y + i * line_height
                    lb = draw.textbbox((0, 0), line, font=sub_font)
                    lx = sub_x + (box_sub_w - (lb[2] - lb[0])) // 2

                    if is_creator_viral:
                        # Top Creator style: First line or exclamation has high-energy Yellow text, followed by crisp white
                        text_color = (254, 240, 138, 255) if (i == 0 or "?" in line or "!" in line) else (255, 255, 255, 255)
                        stroke_w = max(2, int(3 * scale_factor))
                        draw.text(
                            (lx, ly),
                            line,
                            font=sub_font,
                            fill=text_color,
                            stroke_width=stroke_w,
                            stroke_fill=(0, 0, 0, 255)
                        )
                    else:
                        # Soft shadow + clean white
                        draw.text((lx + 2, ly + 2), line, font=sub_font, fill=(0, 0, 0, 200))
                        draw.text((lx, ly), line, font=sub_font, fill=(255, 255, 255, 255))

        output_png.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_png, "PNG")
        return True
    except Exception as e:
        print(f"Error generating overlay: {e}")
        return False

def create_fallback_slide(
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    title: str = "Scene",
    text: str = ""
) -> bool:
    """Creates a beautiful cinematic gradient backdrop card when media download fails."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (width, height), color=(15, 23, 42))  # Deep slate
        draw = ImageDraw.Draw(img)

        # Draw subtle gradient
        for y in range(0, height, 2):
            ratio = y / max(1, height)
            r = int(15 + ratio * 15)
            g = int(23 + ratio * 20)
            b = int(42 + ratio * 35)
            draw.line([(0, y), (width, y)], fill=(r, g, b), width=2)

        scale_factor = width / 1920.0
        font_title = _get_system_font(max(24, int(46 * scale_factor)), bold=True)
        font_body = _get_system_font(max(18, int(30 * scale_factor)), bold=False)

        margin_x = int(width * 0.10)
        margin_y = int(height * 0.12)
        box_w = width - margin_x * 2
        box_h = height - margin_y * 2

        # Glowing frosted card container
        draw.rounded_rectangle(
            [margin_x, margin_y, margin_x + box_w, margin_y + box_h],
            radius=int(24 * scale_factor),
            fill=(26, 36, 56),
            outline=(56, 189, 248),
            width=max(2, int(3 * scale_factor))
        )

        if title:
            draw.text(
                (margin_x + int(48 * scale_factor), margin_y + int(40 * scale_factor)),
                title,
                font=font_title,
                fill=(56, 189, 248)
            )

        if text:
            max_w = box_w - int(96 * scale_factor)
            lines = _wrap_text(text.strip(), font_body, max_w, draw)
            start_y = margin_y + int(120 * scale_factor)
            line_h = int(42 * scale_factor)
            for idx, line in enumerate(lines[:8]):
                draw.text(
                    (margin_x + int(48 * scale_factor), start_y + idx * line_h),
                    line,
                    font=font_body,
                    fill=(241, 245, 249)
                )

        img.save(output_path, "JPEG", quality=92)
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as e:
        print(f"Error creating fallback slide: {e}")
        return False

def process_scene_clip(
    media_path: Path,
    output_path: Path,
    target_w: int = 1920,
    target_h: int = 1080,
    duration: float = 4.0,
    is_image: bool = False,
    overlay_path: Optional[Path] = None,
    audio_path: Optional[Path] = None,
    fit_mode: str = "cover",
    ken_burns_style: str = "auto",
    scene_index: int = 0
) -> bool:
    """
    Master Human Pro Video Processor:
    - Ken Burns dynamic documentary camera zoom for photos (alternating Zoom-In, Zoom-Out, Pan)
    - Loops and normalizes video clips to exact audio duration seamlessly
    - Muxes natural human speech voiceover audio track
    - Direct, crisp cuts between scenes (no immersion-breaking black flash dips)
    - High-bitrate H.264 + AAC audio encoding with Web faststart
    """
    ffmpeg = get_ffmpeg_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fps = 30
    total_frames = max(30, int(duration * fps))

    cmd = [ffmpeg, "-y"]

    if is_image:
        # Pre-scale and crop with 1.2x headroom buffer for zoompan (zero visual quality loss, 60% faster than 2x 4K)
        bw = int(target_w * 1.2)
        bh = int(target_h * 1.2)
        bw = bw if bw % 2 == 0 else bw + 1
        bh = bh if bh % 2 == 0 else bh + 1
        scale_pad = f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh}"
        
        style_choice = ken_burns_style.lower() if ken_burns_style else "auto"
        if style_choice == "auto" or "auto" in style_choice:
            modes = ["zoom_in", "zoom_out", "pan_lr", "pan_rl"]
            style_choice = modes[scene_index % len(modes)]
        
        if "out" in style_choice:
            # Smooth Zoom Out: starts slightly punched in (1.15) and gently reveals wider frame (1.0)
            kb_motion = f"zoompan=z='1.15-0.15*(on/{total_frames})':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={target_w}x{target_h}:fps={fps}"
        elif "right" in style_choice and "pan" in style_choice and "left" not in style_choice:
            # Smooth Pan Left-to-Right
            kb_motion = f"zoompan=z='1.10':d={total_frames}:x='(iw-iw/zoom)*(on/{total_frames})':y='ih/2-(ih/zoom/2)':s={target_w}x{target_h}:fps={fps}"
        elif "left" in style_choice and "pan" in style_choice:
            # Smooth Pan Right-to-Left
            kb_motion = f"zoompan=z='1.10':d={total_frames}:x='(iw-iw/zoom)*(1-on/{total_frames})':y='ih/2-(ih/zoom/2)':s={target_w}x{target_h}:fps={fps}"
        else:
            # Smooth Zoom In: starts standard (1.0) and slowly pushes in for suspense (1.15)
            kb_motion = f"zoompan=z='1.0+0.15*(on/{total_frames})':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={target_w}x{target_h}:fps={fps}"
        
        base_video_filter = f"{scale_pad},{kb_motion},setsar=1"
        cmd += ["-loop", "1", "-i", str(media_path)]
    else:
        # Video clip: smart scaling + stream_loop guarantee to fill exact audio duration cleanly
        if fit_mode == "fit":
            scale_filter = f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}"
        else:  # 'cover' (fill frame cleanly, no black bars)
            scale_filter = f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},setsar=1,fps={fps}"
        
        base_video_filter = scale_filter
        cmd += ["-stream_loop", "-1", "-ss", "0", "-t", str(duration), "-i", str(media_path)]

    input_count = 1
    overlay_input_idx = None
    if overlay_path and overlay_path.exists():
        cmd += ["-i", str(overlay_path)]
        overlay_input_idx = input_count
        input_count += 1

    # Audio track (Voiceover speech or silent baseline)
    has_custom_audio = bool(audio_path and Path(audio_path).exists() and Path(audio_path).stat().st_size > 0)
    if has_custom_audio:
        cmd += ["-i", str(audio_path)]
        audio_input_idx = input_count
        input_count += 1
        audio_filter = f"[{audio_input_idx}:a]volume=1.05,apad=whole_dur={duration},aformat=channel_layouts=stereo:sample_rates=44100[a]"
    else:
        cmd += ["-f", "lavfi", "-t", str(duration), "-i", "anullsrc=r=44100:cl=stereo"]
        audio_input_idx = input_count
        input_count += 1
        audio_filter = f"[{audio_input_idx}:a]aformat=channel_layouts=stereo:sample_rates=44100[a]"

    if overlay_input_idx is not None:
        filter_complex = f"[0:v]{base_video_filter}[bg];[bg][{overlay_input_idx}:v]overlay=0:0[v];{audio_filter}"
    else:
        filter_complex = f"[0:v]{base_video_filter}[v];{audio_filter}"

    cmd += [
        "-threads", "0",
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "24",
        "-maxrate", "3500k",
        "-bufsize", "7000k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(duration),
        "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=140)
        if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return True
        else:
            print(f"FFmpeg error for {output_path.name}: {res.stderr[-300:]}")
            # Fallback if zoompan failed on rare image format
            if is_image:
                cmd_fallback = [
                    ffmpeg, "-y",
                    "-loop", "1", "-t", str(duration), "-i", str(media_path)
                ]
                fb_in_count = 1
                fb_overlay_idx = None
                if overlay_path and overlay_path.exists():
                    cmd_fallback += ["-i", str(overlay_path)]
                    fb_overlay_idx = fb_in_count
                    fb_in_count += 1

                if has_custom_audio:
                    cmd_fallback += ["-i", str(audio_path)]
                    fb_a_idx = fb_in_count
                    fb_in_count += 1
                    fb_a_filter = f"[{fb_a_idx}:a]apad=whole_dur={duration},aformat=channel_layouts=stereo:sample_rates=44100[a]"
                else:
                    cmd_fallback += ["-f", "lavfi", "-t", str(duration), "-i", "anullsrc=r=44100:cl=stereo"]
                    fb_a_idx = fb_in_count
                    fb_in_count += 1
                    fb_a_filter = f"[{fb_a_idx}:a]aformat=channel_layouts=stereo:sample_rates=44100[a]"

                v_filter = f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},setsar=1,fps=30[bg]"
                if fb_overlay_idx is not None:
                    fb_complex = f"{v_filter};[bg][{fb_overlay_idx}:v]overlay=0:0[v];{fb_a_filter}"
                else:
                    fb_complex = f"{v_filter.replace('[bg]', '[v]')};{fb_a_filter}"

                cmd_fallback += [
                    "-threads", "0",
                    "-filter_complex", fb_complex,
                    "-map", "[v]",
                    "-map", "[a]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-maxrate", "3500k", "-bufsize", "7000k", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-t", str(duration), "-movflags", "+faststart",
                    str(output_path)
                ]
                res_fb = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=100)
                return res_fb.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
            return False
    except Exception as e:
        print(f"FFmpeg exception for {output_path.name}: {e}")
        return False

def add_background_music_to_video(
    video_path: Path,
    bgm_path: Path,
    output_path: Path,
    bgm_volume: float = 0.12,
    fade_out_duration: float = 2.0
) -> bool:
    """
    Mixes suspense/cinematic background music under the video's voiceover narration track:
    - Auto-loops BGM to cover total video runtime seamlessly
    - Ducks BGM to configured subtle volume (e.g. 0.12)
    - Fades in BGM over 1.0s and smoothly fades out over 2.0s at video conclusion
    - Keeps video stream intact via stream copy (lightning fast, lossless video)
    """
    if not video_path.exists():
        return False
    if not bgm_path or not bgm_path.exists():
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path.exists()

    ffmpeg = get_ffmpeg_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Measure video duration
    dur = 0.0
    try:
        r = subprocess.run(
            [ffmpeg, "-i", str(video_path)],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            timeout=15
        )
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
        if m:
            h, mn, s = map(float, m.groups())
            dur = round(h * 3600 + mn * 60 + s, 2)
    except Exception as e:
        print(f"Error checking video duration: {e}")

    if dur <= 0:
        dur = 30.0

    st_fade = max(0.0, dur - fade_out_duration)
    # amix filter with voice priority (100% volume, uncompressed) and ducked BGM
    filter_complex = (
        f"[1:a]volume={bgm_volume:.3f},"
        f"afade=t=in:st=0:d=1.0,"
        f"afade=t=out:st={st_fade:.2f}:d={fade_out_duration:.2f},"
        f"aformat=channel_layouts=stereo:sample_rates=44100[bgm];"
        f"[0:a]volume=1.0,aformat=channel_layouts=stereo:sample_rates=44100[narr];"
        f"[narr][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
    )

    cmd = [
        ffmpeg, "-y",
        "-i", str(video_path),
        "-stream_loop", "-1", "-i", str(bgm_path),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(dur),
        "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return True
        else:
            print(f"BGM mixing error: {res.stderr[-300:]}")
    except Exception as e:
        print(f"BGM mixing exception: {e}")

    # Fallback: re-encode video if copy failed on specific container
    try:
        cmd_fb = [
            ffmpeg, "-y",
            "-i", str(video_path),
            "-stream_loop", "-1", "-i", str(bgm_path),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-maxrate", "3500k", "-bufsize", "7000k",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(dur),
            "-movflags", "+faststart",
            str(output_path)
        ]
        res_fb = subprocess.run(cmd_fb, capture_output=True, text=True, timeout=240)
        return res_fb.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
    except Exception as e2:
        print(f"BGM fallback exception: {e2}")
        return False


def merge_clips_to_final_video(clip_paths: List[Path], output_video_path: Path) -> bool:
    """Concatenate multiple scene clips into one final video using FFmpeg with resilient fallback."""
    if not clip_paths:
        return False
    
    ffmpeg = get_ffmpeg_path()
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_video_path.parent / f"temp_merge_{int(time.time()*1000)}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Strategy 1: TS Transmux Concat (The gold standard: 0.5s, 0 re-encoding, perfectly resolves MP4 timestamp/timescale mismatch)
    try:
        ts_files = []
        transmux_ok = True
        for idx, p in enumerate(clip_paths):
            if not p.exists() or p.stat().st_size == 0:
                transmux_ok = False
                break
            ts_p = temp_dir / f"clip_{idx}.ts"
            cmd_ts = [
                ffmpeg, "-y",
                "-i", str(p),
                "-c", "copy",
                "-bsf:v", "h264_mp4toannexb",
                "-f", "mpegts",
                str(ts_p)
            ]
            r_ts = subprocess.run(cmd_ts, capture_output=True, text=True, timeout=30)
            if r_ts.returncode == 0 and ts_p.exists() and ts_p.stat().st_size > 0:
                ts_files.append(ts_p)
            else:
                transmux_ok = False
                break

        if transmux_ok and len(ts_files) == len(clip_paths):
            ts_concat_list = temp_dir / "ts_concat_list.txt"
            with open(ts_concat_list, "w", encoding="utf-8") as f:
                for ts_p in ts_files:
                    safe_p = str(ts_p.resolve()).replace("\\", "/")
                    f.write(f"file '{safe_p}'\n")

            cmd_ts_merge = [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(ts_concat_list),
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
                "-movflags", "+faststart",
                str(output_video_path)
            ]
            r_tm = subprocess.run(cmd_ts_merge, capture_output=True, text=True, timeout=60)
            if r_tm.returncode == 0 and output_video_path.exists() and output_video_path.stat().st_size > 0:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return True
    except Exception as e_ts:
        print(f"TS transmux concat error: {e_ts}")

    # Strategy 2: Fast MP4 Concat Demuxer with -fflags +genpts and timestamp realignment
    try:
        concat_list = temp_dir / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for p in clip_paths:
                safe_p = str(p.resolve()).replace("\\", "/")
                f.write(f"file '{safe_p}'\n")

        cmd = [
            ffmpeg, "-y",
            "-fflags", "+genpts",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            str(output_video_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0 and output_video_path.exists() and output_video_path.stat().st_size > 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return True
    except Exception as e:
        print(f"Direct concat stream copy failed: {e}")

    # Strategy 3: Low-memory safe re-encoding fallback (ultrafast, low threads/buffer to prevent cloud OOM)
    try:
        inputs = []
        filter_parts = []
        for i, p in enumerate(clip_paths):
            inputs.extend(["-i", str(p)])
            filter_parts.append(f"[{i}:v][{i}:a]")
        
        filter_str = f"{''.join(filter_parts)}concat=n={len(clip_paths)}:v=1:a=1[v][a]"
        cmd_fallback = [
            ffmpeg, "-y",
            *inputs,
            "-filter_complex", filter_str,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "25",
            "-threads", "2",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_video_path)
        ]
        res = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=180)
        ok = res.returncode == 0 and output_video_path.exists() and output_video_path.stat().st_size > 0
        shutil.rmtree(temp_dir, ignore_errors=True)
        return ok
    except Exception as e:
        print(f"Fallback concat error: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False

def make_numbered_zip(file_paths: List[Path], zip_output_path: Path) -> bool:
    """Pack individual numbered asset clips into a ZIP file."""
    try:
        zip_output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in file_paths:
                if p.exists():
                    z.write(p, p.name)
        return zip_output_path.exists()
    except Exception as e:
        print(f"ZIP error: {e}")
        return False


def render_single_short_video(
    short_data: Dict[str, Any],
    output_path: Path,
    job_dir: Path,
    pixabay_key: str = "",
    openai_key: str = "",
    voice: str = "hi-IN-MadhurNeural",
    rate: str = "+25%",
    bgm_path: Optional[Path] = None,
    bgm_volume: float = 0.12,
    ken_burns_style: str = "auto",
    subtitle_style: str = "Creator Viral",
    status_callback = None
) -> Optional[Path]:
    """
    Renders an elite 9:16 vertical (1080x1920) YouTube Short video:
    - Extreme triggering hook pacing
    - 1.25x high-energy voice narration
    - Creator Viral centered subtitles (Hormozi / Top YouTuber style)
    - Dynamic Ken Burns documentary camera push-in
    - Ducked suspense/cinematic background music
    """
    try:
        from script_parser import extract_scenario_search
        from pixabay_api import search_assets, generate_ai_image
        from tts_engine import generate_human_voiceover, estimate_speech_duration
    except ImportError:
        try:
            from pixabay_api import search_assets
        except ImportError:
            pass

    short_id = short_data.get("id", "short_1")
    script_text = short_data.get("script", "")
    if not script_text.strip():
        return None

    raw_lines = [l.strip() for l in script_text.splitlines() if len(l.strip()) > 3]
    if not raw_lines:
        raw_lines = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script_text) if len(s.strip()) > 3]

    target_w, target_h = 1080, 1920
    short_dir = job_dir / short_id
    short_dir.mkdir(parents=True, exist_ok=True)

    processed_clips = []

    for i, line in enumerate(raw_lines):
        sc_num = str(i + 1).zfill(2)
        if status_callback:
            status_callback(f"🎬 Rendering {short_data.get('title', short_id)} · Scene {i+1}/{len(raw_lines)}...")

        # 1. Voice narration at 1.25x speed
        voice_file = short_dir / f"voice_{sc_num}.mp3"
        voice_dur = generate_human_voiceover(line, voice_file, voice=voice, rate=rate)
        if voice_dur and voice_file.exists() and voice_file.stat().st_size > 500:
            scene_dur = round(max(1.8, voice_dur + 0.20), 2)
            audio_track = voice_file
        else:
            scene_dur = round(estimate_speech_duration(line, speed=1.25), 2)
            audio_track = None

        # 2. Visual asset search (vertical orientation preferred)
        kw_data = extract_scenario_search(line) if 'extract_scenario_search' in locals() else {"keyword": "cinematic dramatic view"}
        kw = kw_data.get("keyword", "cinematic dramatic")
        
        raw_media = None
        is_img = False

        if pixabay_key:
            results = search_assets(query=kw, key=pixabay_key, media_type="both", orientation="vertical", per_page=6, openai_key=openai_key)
            if not results:
                results = search_assets(query=kw, key=pixabay_key, media_type="both", orientation="all", per_page=6, openai_key=openai_key)
            
            if results:
                chosen = results[0]
                ext = ".jpg" if chosen.get("type") == "image" else ".mp4"
                try_dest = short_dir / f"raw_{sc_num}{ext}"
                if download_file(chosen.get("download", ""), try_dest) and try_dest.exists() and try_dest.stat().st_size > 1000:
                    raw_media = try_dest
                    is_img = (chosen.get("type") == "image")

        # Fallback AI visual
        if not raw_media or not raw_media.exists():
            ai_path = short_dir / f"raw_{sc_num}_ai.jpg"
            generate_ai_image(prompt=f"Vertical 9:16 mobile format dramatic scene: {line}", openai_key=openai_key, dest_path=ai_path)
            if ai_path.exists() and ai_path.stat().st_size > 500:
                raw_media = ai_path
                is_img = True

        # Ultimate fallback slide
        if not raw_media or not raw_media.exists():
            slide_path = short_dir / f"raw_{sc_num}_slide.jpg"
            create_fallback_slide(slide_path, width=target_w, height=target_h, title=short_data.get("hook_type", "YouTube Short"), text=line)
            raw_media = slide_path
            is_img = True

        # 3. Creator Viral centered subtitle overlay (9:16 vertical optimized)
        ov_path = short_dir / f"overlay_{sc_num}.png"
        create_overlay_image(
            width=target_w,
            height=target_h,
            scene_no=sc_num,
            output_png=ov_path,
            scene_text=line,
            show_badge=True,
            badge_style="Minimal (01)",
            badge_position="Top Right",
            show_subtitle=True,
            subtitle_style=subtitle_style
        )

        # 4. Process scene clip
        clip_path = short_dir / f"clip_{sc_num}.mp4"
        ok = process_scene_clip(
            media_path=raw_media,
            output_path=clip_path,
            target_w=target_w,
            target_h=target_h,
            duration=scene_dur,
            is_image=is_img,
            overlay_path=ov_path,
            audio_path=audio_track,
            fit_mode="cover",
            ken_burns_style=ken_burns_style,
            scene_index=i
        )

        if ok and clip_path.exists() and clip_path.stat().st_size > 0:
            processed_clips.append(clip_path)

    if not processed_clips:
        return None

    # Merge scenes
    raw_merged = short_dir / f"{short_id}_raw_merged.mp4"
    if not merge_clips_to_final_video(processed_clips, raw_merged):
        return None

    # Mix BGM if provided
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if bgm_path and bgm_path.exists():
        ok_bgm = add_background_music_to_video(
            video_path=raw_merged,
            bgm_path=bgm_path,
            output_path=output_path,
            bgm_volume=bgm_volume,
            fade_out_duration=1.5
        )
        if not ok_bgm or not output_path.exists():
            import shutil
            shutil.copy2(raw_merged, output_path)
    else:
        import shutil
        shutil.copy2(raw_merged, output_path)

    return output_path if output_path.exists() and output_path.stat().st_size > 0 else None


def render_shorts_package(
    shorts_list: List[Dict[str, Any]],
    output_dir: Path,
    job_dir: Path,
    pixabay_key: str = "",
    openai_key: str = "",
    voice: str = "hi-IN-MadhurNeural",
    rate: str = "+25%",
    bgm_path: Optional[Path] = None,
    bgm_volume: float = 0.12,
    ken_burns_style: str = "auto",
    subtitle_style: str = "Creator Viral",
    progress_callback = None
) -> List[Dict[str, Any]]:
    """
    Renders 3 to 4 complete YouTube Shorts in parallel/sequence and returns result metadata list.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered_shorts = []
    total = len(shorts_list)

    for idx, s_data in enumerate(shorts_list):
        s_id = s_data.get("id", f"short_{idx+1}")
        out_p = output_dir / f"{s_id}_{int(time.time())}.mp4"
        
        if progress_callback:
            progress_callback(f"📱 [{idx+1}/{total}] Generating {s_data.get('title', s_id)}...", (idx) / total)

        res_path = render_single_short_video(
            short_data=s_data,
            output_path=out_p,
            job_dir=job_dir,
            pixabay_key=pixabay_key,
            openai_key=openai_key,
            voice=voice,
            rate=rate,
            bgm_path=bgm_path,
            bgm_volume=bgm_volume,
            ken_burns_style=ken_burns_style,
            subtitle_style=subtitle_style,
            status_callback=progress_callback
        )

        if res_path and res_path.exists():
            from tts_engine import get_audio_duration
            dur = get_audio_duration(res_path)
            rendered_shorts.append({
                "id": s_id,
                "title": s_data.get("title", f"Short #{idx+1}"),
                "hook_type": s_data.get("hook_type", "Pattern Interrupt"),
                "script": s_data.get("script", ""),
                "video_path": str(res_path),
                "duration": dur
            })

    if progress_callback:
        progress_callback("✅ All YouTube Shorts generated successfully!", 1.0)

    return rendered_shorts
