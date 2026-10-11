"""
niche_engine.py - Master Niche Engine & YouTube Growth Suite
Provides 1-click presets, visual/audio strategies, YouTube SEO Kit generation,
and 1280x720 HD Thumbnail generation specifically optimized for:
  - 🏛️ Ancient History & Lost Civilizations
  - 🕵️ Dark Mystery & Unsolved Secrets
  - 🌌 Space, Universe & Cosmic Mysteries
  - 💡 General Viral / Tech / Psychology
"""

import os
import re
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import imageio_ffmpeg

# =====================================================================
# 1. MASTER NICHE DEFINITIONS & CATALOG
# =====================================================================
NICHE_CATALOG: Dict[str, Dict[str, Any]] = {
    "history": {
        "name": "🏛️ Ancient History & Lost Civilizations",
        "short_name": "Ancient History",
        "badge": "ANCIENT SECRET",
        "badge_color": "#D97706",
        "accent_color": "#F59E0B",
        "default_voice": "hi-IN-MadhurNeural",
        "default_voice_en": "en-US-ChristopherNeural",
        "default_bgm": "suspense_stormfront",
        "speed_mode": "1.15x Energetic YouTube Pace",
        "speed_multiplier": 1.15,
        "tts_rate_str": "+15%",
        "subtitle_style": "🔥 Creator Viral (Yellow/White Accent + Stroke)",
        "stock_bias": "ancient egypt temple ruins archaeology monument desert artifacts stone statue historical",
        "thumbnail_hooks": [
            "THEY HID THIS!",
            "BEFORE HISTORY!",
            "NOT HUMAN BUILT?",
            "LOST FOR 12,000 YEARS",
            "THE SACRED TRUTH"
        ],
        "presets": {
            "🏛️ Pyramids Energy Grid (Ancient Mystery)": (
                "Wait, what if everything you were taught in school about the Pyramids is a complete lie?\n"
                "Modern engineers admit moving 2-million-ton limestone blocks across the desert is mathematically impossible with primitive bronze chisels.\n"
                "Even stranger, deep inside the Great Pyramid, scientists discovered zero mummies, zero hieroglyphs, and mysterious conductive granite chambers.\n"
                "Could an ancient advanced civilization have built these colossal monuments as a planetary wireless power grid?\n"
                "The deeper archeologists dig, the more terrifying human history becomes."
            ),
            "🏛️ Submerged Secrets of Atlantis & Dwarka": (
                "Deep beneath the ocean waves, marine explorers have uncovered colossal stone roads and submerged megaliths that should not exist.\n"
                "From the sunken city of Dwarka off the Indian coast to the mysterious underwater pyramids of Yonaguni, the evidence is undeniable.\n"
                "Over twelve thousand years ago, a catastrophic global cataclysm wiped out an entire epoch of advanced human civilization.\n"
                "Ancient Vedic texts described acoustic levitation and advanced flying craft long before modern science began.\n"
                "We are not the first advanced civilization on Earth; we are just the ones who survived."
            ),
            "🏛️ The Forbidden Sumerian Kings List": (
                "In 1906, archaeologists unearthed ancient Sumerian clay tablets containing a list of rulers that shocked the scientific world.\n"
                "The tablets state that before the Great Flood, eight god-like kings ruled Mesopotamia for over two hundred thousand years.\n"
                "Mainstream historians dismiss it as mythology, yet the astronomical alignments recorded by the Sumerians match modern NASA data with pinpoint accuracy.\n"
                "Who were these extraordinary rulers, and where did their astronomical knowledge come from?\n"
                "Some classified ancient texts suggest human origins are far older than modern science admits."
            )
        }
    },
    "mystery": {
        "name": "🕵️ Dark Mystery & Unsolved Secrets",
        "short_name": "Dark Mystery",
        "badge": "CLASSIFIED FILE",
        "badge_color": "#DC2626",
        "accent_color": "#EF4444",
        "default_voice": "hi-IN-MadhurNeural",
        "default_voice_en": "en-US-ChristopherNeural",
        "default_bgm": "suspense_dark_walk",
        "speed_mode": "1.25x Top Creator Fast (Punchy & Viral)",
        "speed_multiplier": 1.25,
        "tts_rate_str": "+25%",
        "subtitle_style": "🎬 Studio Box (Translucent Dark Banner)",
        "stock_bias": "mystery dark fog night investigation silhouette document crime eerie classified",
        "thumbnail_hooks": [
            "THEY DISAPPEARED!",
            "TOP SECRET LEAK",
            "NEVER GO HERE!",
            "WHAT DID THEY SEE?",
            "UNEXPLAINED HORROR"
        ],
        "presets": {
            "🕵️ The Dyatlov Pass Nightmare": (
                "In February 1959, nine experienced hikers ventured into the freezing Ural Mountains and were never seen alive again.\n"
                "Rescue teams discovered their tent sliced open from the inside, as if the hikers fled in blind panic without shoes in sub-zero snow.\n"
                "Their bodies were found miles away with catastrophic internal trauma, missing tongues, and inexplicable traces of high radiation.\n"
                "Soviet authorities abruptly sealed the investigation and classified all files for decades under an unknown compelling force.\n"
                "To this day, forensic investigators cannot explain what stalked those nine hikers on that cursed mountain."
            ),
            "🕵️ The Unsolved Cipher of Voynich Manuscript": (
                "In the high-security vault of Yale University sits a 600-year-old manuscript written in a cipher that no human or supercomputer can break.\n"
                "The Voynich Manuscript contains intricate illustrations of unknown biological organs, impossible astrological wheels, and plants that do not exist on Earth.\n"
                "During World War Two, elite codebreakers who cracked the Nazi Enigma spent years trying to break this book and failed completely.\n"
                "Is it an encrypted grimoire of lost alchemy, or a terrifying message from another dimension?\n"
                "Every linguist who attempts to decode it ends up questioning their own sanity."
            ),
            "🕵️ The Bermuda Triangle Magnetic Anomaly": (
                "Between Florida, Puerto Rico, and Bermuda lies a patch of ocean where entire military squadrons have vanished without leaving a single trace.\n"
                "In 1945, Flight 19 vanished into thin air after the lead pilot reported his compasses spinning wildly and the ocean looking completely white.\n"
                "The rescue aircraft sent to save them vanished twenty minutes later, leaving zero oil slicks, zero debris, and zero survivors.\n"
                "Modern oceanographers have detected massive methane gas eruptions, hexagonal death-clouds, and anomalous magnetic deviations beneath the seabed.\n"
                "Whatever lies at the bottom of the Devil's Triangle, it has been consuming human ships for centuries."
            )
        }
    },
    "space": {
        "name": "🌌 Space, Universe & Cosmic Mysteries",
        "short_name": "Space & Cosmos",
        "badge": "COSMIC DISCOVERY",
        "badge_color": "#0284C7",
        "accent_color": "#06B6D4",
        "default_voice": "hi-IN-MadhurNeural",
        "default_voice_en": "en-US-ChristopherNeural",
        "default_bgm": "suspense_industrial_cinematic",
        "speed_mode": "1.25x Top Creator Fast (Punchy & Viral)",
        "speed_multiplier": 1.25,
        "tts_rate_str": "+25%",
        "subtitle_style": "✨ Minimal Clean (Drop Shadow)",
        "stock_bias": "space deep cosmos black hole galaxy nebula astronomy planet astronaut stars universe",
        "thumbnail_hooks": [
            "WHAT'S INSIDE?",
            "UNIVERSE IS BROKEN!",
            "SCIENTISTS TERRIFIED",
            "WE FOUND IT!",
            "EDGE OF REALITY"
        ],
        "presets": {
            "🌌 What Exists Inside a Black Hole?": (
                "If you fell past the event horizon of a supermassive black hole, the laws of physics as you know them would completely collapse.\n"
                "As you cross the threshold, space and time literally swap roles, meaning the singularity is no longer a location, but an inevitable future moment.\n"
                "Looking back toward the outside universe, you would watch billions of years of cosmic history speed up in a blinding flash of light.\n"
                "At the central singularity, gravitational forces become infinitely dense, tearing atoms into pure quantum information.\n"
                "Some theoretical physicists believe the bottom of every black hole opens up into a newborn universe on the other side."
            ),
            "🌌 The Terrifying Solution to the Fermi Paradox": (
                "There are over two trillion galaxies in the observable universe, containing more habitable planets than every grain of sand on Earth.\n"
                "So why has humanity heard nothing but eerie, deafening silence across the cosmos for sixty years?\n"
                "The most terrifying hypothesis is known as the Dark Forest Theory: the universe is a dark forest filled with predatory civilizations.\n"
                "Every advanced civilization stays completely silent and hidden, knowing that broadcasting their location is a guarantee of immediate destruction.\n"
                "Humanity has been screaming radio signals into deep space for a century, and we might have just alerted the predators."
            ),
            "🌌 James Webb Just Found Something Impossible": (
                "Astronomers using the James Webb Space Telescope recently pointed their infrared mirrors at the absolute edge of time and space.\n"
                "What they discovered has sent shockwaves through astrophysics: massive, fully-formed spiral galaxies existing just three hundred million years after the Big Bang.\n"
                "According to established cosmological models, these gigantic galaxies should have taken billions of years to coalesce from primordial gas clouds.\n"
                "Either our understanding of gravity and cosmic inflation is fundamentally wrong, or the universe is twice as old as science believed.\n"
                "The deeper we gaze into the cosmic void, the less we understand about our own existence."
            )
        }
    },
    "general": {
        "name": "💡 General Viral / Tech / Psychology",
        "short_name": "General Viral",
        "badge": "VIRAL CREATOR",
        "badge_color": "#2563EB",
        "accent_color": "#3B82F6",
        "default_voice": "hi-IN-MadhurNeural",
        "default_voice_en": "en-US-ChristopherNeural",
        "default_bgm": "suspense_stormfront",
        "speed_mode": "1.25x Top Creator Fast (Punchy & Viral)",
        "speed_multiplier": 1.25,
        "tts_rate_str": "+25%",
        "subtitle_style": "🔥 Creator Viral (Yellow/White Accent + Stroke)",
        "stock_bias": "cinematic commercial stock documentary modern",
        "thumbnail_hooks": [
            "DON'T IGNORE THIS!",
            "WHY 99% FAIL",
            "THE SECRET SYSTEM",
            "STOP SCROLLING!"
        ],
        "presets": {
            "💡 AI Revolution & Urgent Reality Check": (
                "Stop scrolling, because this single AI breakthrough is about to erase millions of white-collar jobs overnight.\n"
                "Autonomous AI agents are now generating complete software, business empires, and cinematic movies in seconds.\n"
                "Most people think they have five years to prepare, but tech giants are quietly replacing entire teams right now.\n"
                "If you do not master AI tools today, you will be permanently replaced by someone who does."
            ),
            "💡 The Dark Psychology of Human Influence": (
                "There is a dangerous psychological trick that 99% of people fall for without ever realizing it.\n"
                "Master manipulators use strategic pauses and subtle body language to make you agree to almost anything.\n"
                "Once you understand how the human brain craves approval, you can spot the trap instantly.\n"
                "Pay close attention next time someone asks you a loaded question."
            )
        }
    }
}

def _extract_script_insights(script_text: str, scenes: List[Dict[str, Any]], topic: str) -> Tuple[str, List[str]]:
    """
    Extracts the actual narrative opening hook and 3-5 core story points
    directly from the generated scenes and script content, avoiding static boilerplate.
    """
    raw_lines = []
    if scenes:
        for sc in scenes:
            txt = sc.get("text", "").strip()
            if txt:
                raw_lines.append(txt)
    
    if not raw_lines and script_text:
        for line in script_text.splitlines():
            cl = line.strip()
            if cl and not cl.startswith("#"):
                raw_lines.append(cl)
        if not raw_lines:
            raw_lines = [s.strip() for s in re.split(r'\.(?:\s+|$)', script_text) if s.strip()]

    if not raw_lines:
        hook = f"In this deep-dive visual investigation, we uncover the shocking reality behind {topic}."
        bullets = [
            f"The unexplained anomalies and evidence surrounding {topic}",
            f"Overlooked eyewitness and historical records that change everything",
            f"The ultimate revelation and what it means for the future"
        ]
        return hook, bullets

    # 1. Opening Hook: First sentence of the real script
    hook = raw_lines[0]
    used_indices = {0}
    if len(raw_lines) > 1 and len(hook) < 85:
        hook = f"{hook} {raw_lines[1]}"
        used_indices.add(1)

    # 2. Key Story Beat Bullets: derived from actual subsequent scene statements
    remaining_lines = [(idx, line) for idx, line in enumerate(raw_lines) if idx not in used_indices]
    
    bullets = []
    if not remaining_lines:
        bullets = [f"The untold facts and complete breakdown of {topic}"]
    elif len(remaining_lines) <= 3:
        bullets = [l for _, l in remaining_lines]
    else:
        # Sample up to 4 representative lines across remaining scenes
        n_rem = len(remaining_lines)
        step = max(1, n_rem // 3)
        sample_pick = []
        for i in range(0, n_rem, step):
            if i not in sample_pick:
                sample_pick.append(i)
        if (n_rem - 1) not in sample_pick:
            sample_pick.append(n_rem - 1)

        for pick_idx in sample_pick[:4]:
            item_text = remaining_lines[pick_idx][1]
            if len(item_text) > 150:
                item_text = item_text[:147].rstrip() + "..."
            bullets.append(item_text)

    return hook, bullets

def generate_youtube_seo_kit(
    topic: str,
    script_text: str,
    scenes: List[Dict[str, Any]],
    niche_key: str = "history"
) -> Dict[str, Any]:
    """
    Generates a complete YouTube Studio upload kit:
      - 3 High-CTR Titles tailored to niche
      - Full SEO Description with auto-calculated timestamps / chapters
      - 25-30 Viral Ranking Tags
      - Viral Hashtags
      - High-engagement Pinned Comment prompt
    """
    niche_data = NICHE_CATALOG.get(niche_key, NICHE_CATALOG["general"])
    clean_topic = topic.strip() if topic and topic.strip() else "Ancient Mysteries"
    
    # 1. High-CTR Curiosity Titles
    if niche_key == "history":
        titles = [
            f"The 4,000-Year-Old Secret Historians Refuse to Tell You ({clean_topic})",
            f"What They Found Inside {clean_topic} Changes Human History Forever",
            f"The Terrifying Truth About {clean_topic} Nobody Was Supposed to Know"
        ]
        base_tags = ["ancient history", "lost civilization", "pyramids", "archaeology", "ancient secrets", "history documentary", "forbidden history", "ancient technology", "ancient aliens theory", "hidden history", "megaliths", "unexplained history", "sacred truth", "historical mystery", "faceless channel"]
        hashtags = ["#AncientHistory", "#HistoryMystery", "#LostCivilization", "#Pyramids", "#Archaeology", "#Documentary", "#Shorts"]
        pinned_comment = f"💬 Do you think modern historians are hiding the real truth about {clean_topic}? Drop your honest theory below! 👇"

    elif niche_key == "mystery":
        titles = [
            f"The Disturbing Mystery of {clean_topic} That Science Cannot Explain",
            f"Why The Government Completely Classified The Files On {clean_topic}",
            f"What Really Happened At {clean_topic}? (The Dark Unsolved Truth)"
        ]
        base_tags = ["unsolved mystery", "dark mystery", "classified files", "true crime mystery", "terrifying discovery", "dyatlov pass", "bermuda triangle", "creepy mystery", "strange disappearances", "mystery documentary", "conspiracy", "chilling secrets", "unexplained phenomena", "mystery video", "faceless channel"]
        hashtags = ["#Mystery", "#UnsolvedMystery", "#Classified", "#DarkHistory", "#Creepy", "#HorrorMystery", "#Shorts"]
        pinned_comment = f"💬 If you were investigating {clean_topic}, what is the first clue you would inspect? Share your opinion below! 👇"

    elif niche_key == "space":
        titles = [
            f"What James Webb Just Discovered In {clean_topic} Terrifies Astronomers",
            f"What Actually Happens If You Enter {clean_topic}? (Mind-Bending)",
            f"The Dark Cosmic Secret of {clean_topic} That Breaks Physics"
        ]
        base_tags = ["space mystery", "universe secrets", "black hole", "james webb telescope", "astronomy documentary", "deep space", "fermi paradox", "alien life", "cosmic horror", "quantum physics", "multiverse", "nasa discovery", "space documentary", "universe timeline", "faceless channel"]
        hashtags = ["#Space", "#Astronomy", "#BlackHole", "#JamesWebb", "#Cosmos", "#Universe", "#Shorts"]
        pinned_comment = f"💬 Does the sheer scale of {clean_topic} make you feel fascinated or terrified? Let's discuss in the comments! 👇"

    else:
        titles = [
            f"Why 99% Of People Have No Idea This Exists ({clean_topic})",
            f"The Shocking Truth About {clean_topic} That Changes Everything",
            f"Before You Make Another Move, Watch This Breakdown On {clean_topic}"
        ]
        base_tags = ["viral video", "educational", "psychology", "technology", "artificial intelligence", "life lessons", "mindset", "success secrets", "facts that will blow your mind", "curiosity", "viral youtube", "faceless channel"]
        hashtags = ["#Facts", "#Viral", "#AI", "#Psychology", "#Knowledge", "#Shorts"]
        pinned_comment = f"💬 What was the most shocking part of this breakdown for you? Drop your thoughts below! 👇"

    # Add topic-specific tags
    topic_words = [w.lower() for w in re.sub(r'[^a-zA-Z0-9\s]', '', clean_topic).split() if len(w) > 2]
    all_tags = list(dict.fromkeys(topic_words + [clean_topic.lower()] + base_tags))[:28]
    formatted_tags = ", ".join(all_tags)

    # 2. Build Curated YouTube Chapters (6 to 10 meaningful timestamps covering full video)
    total_scenes = len(scenes)
    if total_scenes == 0:
        chapters_block = "⏱️ CHAPTERS & TIMESTAMPS:\n00:00 - The Untold Story"
    else:
        # Calculate cumulative start times for each scene
        start_times = []
        curr_t = 0.0
        for sc in scenes:
            start_times.append(curr_t)
            curr_t += float(sc.get('duration', 4.0))

        # Dynamically determine step size so total chapters is between 6 and 10 (max 12)
        if total_scenes <= 6:
            step = 1
        elif total_scenes <= 12:
            step = 2
        elif total_scenes <= 24:
            step = 3
        else:
            step = max(3, total_scenes // 9)

        chapter_indices = list(range(0, total_scenes, step))
        # Ensure the final scene/climax is included if there's enough duration gap (>10s)
        if (total_scenes - 1) not in chapter_indices:
            last_idx = chapter_indices[-1]
            if (curr_t - start_times[last_idx]) >= 10.0:
                if len(chapter_indices) >= 12:
                    chapter_indices[-1] = total_scenes - 1
                else:
                    chapter_indices.append(total_scenes - 1)

        # Niche-specific dramatic chapter title pools
        niche_titles_map = {
            "history": [
                "The Ancient Anomaly", "Megalithic Architecture", "The Forgotten Technology",
                "Hidden Evidence", "Archaeological Discovery", "The Lost Records",
                "Sacred Alignments", "The Great Cataclysm", "Forbidden Truths"
            ],
            "mystery": [
                "The First Warning", "Strange Disappearances", "The Chilling Clue",
                "Classified Investigation", "What Really Happened", "Unexplained Anomaly",
                "The Government Files", "Beyond Explanation", "The Lingering Darkness"
            ],
            "space": [
                "Edge of the Void", "Cosmic Collision", "Breaking Physics",
                "Deep Space Discovery", "What Lies Beyond", "The Event Horizon",
                "Astronomical Anomaly", "The Silent Universe", "Mind-Bending Reality"
            ],
            "general": [
                "The First Breakthrough", "The Hidden Pattern", "Critical Turning Point",
                "What Everyone Missed", "The Secret Mechanism", "Shocking Revelation"
            ]
        }
        title_pool = niche_titles_map.get(niche_key, niche_titles_map["general"])

        timestamps_lines = ["⏱️ CHAPTERS & TIMESTAMPS:"]
        total_ch = len(chapter_indices)
        for ch_idx, s_idx in enumerate(chapter_indices):
            t_sec = start_times[s_idx]
            mins = int(t_sec // 60)
            secs = int(t_sec % 60)
            ts_str = f"{mins:02d}:{secs:02d}"

            if ch_idx == 0:
                ch_name = f"The Hook ({clean_topic})"
            elif ch_idx == total_ch - 1:
                ch_name = "Final Revelation & Verdict"
            else:
                kw = scenes[s_idx].get("keyword", "").title()
                template = title_pool[(ch_idx - 1) % len(title_pool)]
                if kw and len(kw) <= 20 and kw.lower() not in clean_topic.lower():
                    ch_name = f"{template} ({kw})"
                else:
                    ch_name = template

            timestamps_lines.append(f"{ts_str} - {ch_name}")

        chapters_block = "\n".join(timestamps_lines)

    # 3. Dynamic SEO Description (Synthesized directly from generated video script)
    hook_intro, dynamic_bullets = _extract_script_insights(script_text, scenes, clean_topic)
    bullet_lines = "\n".join([f"• {b}" for b in dynamic_bullets])

    clean_pinned_prompt = pinned_comment.replace('💬', '').replace('👇', '').strip()

    description = f"""🔥 {titles[0]}

{hook_intro}

📌 In this video, we break down:
{bullet_lines}

{chapters_block}

🔔 Subscribe to the channel for more deep-dive {niche_data['short_name']} documentaries!
👍 If this video blew your mind, hit Like and Share with someone who loves this topic!
💬 {clean_pinned_prompt}

{' '.join(hashtags)}
"""

    return {
        "titles": titles,
        "description": description.strip(),
        "tags": formatted_tags,
        "hashtags": " ".join(hashtags),
        "pinned_comment": pinned_comment,
        "recommended_hook": niche_data["thumbnail_hooks"][0]
    }

# =====================================================================
# 3. AUTO 1280x720 HD YOUTUBE THUMBNAIL GENERATOR
# =====================================================================
def _get_font(size: int) -> ImageFont.ImageFont:
    """Loads a bold, high-impact font for YouTube thumbnail text."""
    candidates = ["impact.ttf", "arialbd.ttf", "segoeuib.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf"]
    for font_name in candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def generate_youtube_thumbnail(
    bg_image_path: Path,
    output_path: Path,
    hook_text: str = "THEY HID THIS!",
    niche_key: str = "history",
    custom_badge: Optional[str] = None
) -> bool:
    """
    Renders an ultra-high CTR 1280x720 YouTube Thumbnail:
      - 1280x720 HD standard ratio
      - High-contrast visual crop with subtle vignette darkening
      - Glowing niche badge (e.g., [🔴 CLASSIFIED] or [⚡ ANCIENT SECRET])
      - Bold, punchy 78px Impact hook text with black outline and drop shadow
    """
    try:
        target_w, target_h = 1280, 720
        niche_data = NICHE_CATALOG.get(niche_key, NICHE_CATALOG["general"])
        
        # Load or create base canvas
        if bg_image_path and Path(bg_image_path).exists():
            try:
                base_img = Image.open(bg_image_path).convert("RGBA")
            except Exception:
                base_img = Image.new("RGBA", (target_w, target_h), (15, 23, 42, 255))
        else:
            base_img = Image.new("RGBA", (target_w, target_h), (15, 23, 42, 255))

        # Center-Crop & Resize to 1280x720
        bw, bh = base_img.size
        scale = max(target_w / bw, target_h / bh)
        nw, nh = int(bw * scale), int(bh * scale)
        base_img = base_img.resize((nw, nh), Image.Resampling.LANCZOS)
        
        # Center crop
        left = (nw - target_w) // 2
        top = (nh - target_h) // 2
        base_img = base_img.crop((left, top, left + target_w, top + target_h))

        # Boost saturation and contrast slightly for eye-popping YouTube CTR
        enhancer = ImageEnhance.Color(base_img.convert("RGB"))
        base_img = enhancer.enhance(1.18).convert("RGBA")
        enhancer_c = ImageEnhance.Contrast(base_img.convert("RGB"))
        base_img = enhancer_c.enhance(1.15).convert("RGBA")

        # Create Dark Vignette Overlay for maximum text readability
        overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)
        
        # Bottom-left dark gradient for text backing
        for step in range(target_h):
            alpha = int(min(220, max(0, (step / target_h) * 230 - 30)))
            draw_ov.line([(0, step), (target_w, step)], fill=(0, 0, 0, alpha))
            
        # Left side dark gradient
        for step in range(int(target_w * 0.7)):
            factor = 1.0 - (step / (target_w * 0.7))
            alpha_left = int(factor * 160)
            draw_ov.line([(step, 0), (step, target_h)], fill=(0, 0, 0, alpha_left))

        base_img = Image.alpha_composite(base_img, overlay)

        # Draw on top
        draw = ImageDraw.Draw(base_img)

        # 1. Niche Pill Badge at Top-Left
        badge_text = custom_badge or niche_data.get("badge", "VIRAL FACT")
        badge_font = _get_font(28)
        
        bbox_b = draw.textbbox((0, 0), badge_text, font=badge_font)
        bw_b = bbox_b[2] - bbox_b[0]
        bh_b = bbox_b[3] - bbox_b[1]
        
        bx, by = 45, 45
        pad_x, pad_y = 16, 8
        draw.rounded_rectangle(
            [bx, by, bx + bw_b + pad_x * 2, by + bh_b + pad_y * 2],
            radius=8,
            fill=niche_data.get("badge_color", "#DC2626"),
            outline="#FFFFFF",
            width=2
        )
        draw.text((bx + pad_x, by + pad_y - 1), badge_text, font=badge_font, fill="#FFFFFF")

        # 2. High-CTR Hook Text at Bottom-Left
        clean_hook = (hook_text or niche_data["thumbnail_hooks"][0]).strip().upper()
        # Limit to 3-4 words for max impact
        words = clean_hook.split()
        if len(words) > 5:
            clean_hook = " ".join(words[:4])

        hook_font = _get_font(84)
        
        # Word wrap if text is long
        lines = []
        if len(words) >= 3:
            mid = len(words) // 2
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]
        else:
            lines = [clean_hook]

        text_y = target_h - (len(lines) * 95) - 50
        
        for line_idx, line_str in enumerate(lines):
            line_y = text_y + (line_idx * 95)
            line_x = 45

            # Accent color: Line 1 = White, Line 2 = Accent (Yellow/Cyan/Red)
            fill_color = "#FFFFFF" if line_idx == 0 else niche_data.get("accent_color", "#FACC15")
            
            # Thick black outline (6px) + Drop Shadow (4px)
            stroke_w = 6
            shadow_offset = 6
            
            # Drop shadow
            draw.text((line_x + shadow_offset, line_y + shadow_offset), line_str, font=hook_font, fill=(0, 0, 0, 240))
            # Black Stroke
            for ox in range(-stroke_w, stroke_w + 1):
                for oy in range(-stroke_w, stroke_w + 1):
                    if ox != 0 or oy != 0:
                        draw.text((line_x + ox, line_y + oy), line_str, font=hook_font, fill="#000000")
            # Text Fill
            draw.text((line_x, line_y), line_str, font=hook_font, fill=fill_color)

        # Save as high-quality JPG
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_rgb = base_img.convert("RGB")
        final_rgb.save(output_path, "JPEG", quality=92, optimize=True)
        return output_path.exists() and output_path.stat().st_size > 5000

    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return False
