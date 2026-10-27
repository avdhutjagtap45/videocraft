import re

STOPWORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'aren',
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by',
    'can', 'could', 'did', 'do', 'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from',
    'further', 'had', 'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself', 'him', 'himself',
    'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its', 'itself', 'just', 'me', 'more', 'most',
    'my', 'myself', 'no', 'nor', 'not', 'now', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'our',
    'ours', 'ourselves', 'out', 'over', 'own', 'same', 'she', 'should', 'so', 'some', 'such', 'than',
    'that', 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'these', 'they', 'this',
    'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when',
    'where', 'which', 'while', 'who', 'whom', 'why', 'will', 'with', 'would', 'you', 'your', 'yours',
    'thousands', 'years', 'ago', 'centuries', 'times', 'today', 'day', 'days', 'week', 'month', 'year',
    'time', 'many', 'much', 'lot', 'often', 'always', 'never', 'sometimes', 'suddenly', 'eventually',
    'next', 'first', 'second', 'last', 'finally', 'simply', 'truly', 'really', 'actually', 'already',
    'still', 'even', 'also', 'however', 'although', 'instead', 'meanwhile', 'whatever', 'whoever',
    'someone', 'everyone', 'anyone', 'nobody', 'something', 'everything', 'anything', 'nothing',
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'hundred', 'million',
    'began', 'started', 'became', 'become', 'says', 'said', 'told', 'tells', 'think', 'thought',
    'felt', 'feel', 'see', 'saw', 'know', 'knew', 'look', 'looked', 'seemed', 'seems', 'made', 'make',
    'making', 'went', 'go', 'going', 'come', 'came', 'coming', 'like', 'get', 'got', 'getting',
    'well', 'back', 'way', 'even', 'new', 'good', 'great', 'every'
}

SAMPLE_PRESETS = {
    "🔥 Viral Hook: Dark Secrets of the Pyramids (Creator Style)": (
        "Wait, what if everything you were taught in school about the Pyramids is a complete lie?\n"
        "Modern engineers admit moving 2-million-ton limestone blocks across the desert is mathematically impossible with primitive bronze chisels.\n"
        "Even stranger, deep inside the pharaoh's tombs, scientists discovered zero mummies and mysterious geometric energy alignments.\n"
        "Could an ancient lost civilization have built these cosmic monuments before human recorded history?\n"
        "The deeper you dig, the more terrifying the truth becomes."
    ),
    "🔥 Viral Hook: AI Is Taking Over (Urgent Reality Check)": (
        "Stop scrolling, because this single AI breakthrough is about to erase millions of white-collar jobs overnight.\n"
        "Autonomous AI agents are now generating complete software, business empires, and cinematic movies in seconds.\n"
        "Most people think they have 5 years to prepare, but tech giants are quietly replacing entire teams right now.\n"
        "If you do not master AI tools today, you will be permanently replaced by someone who does."
    ),
    "🔥 Viral Hook: Dark Psychology of Influence (Mind Game)": (
        "There is a dangerous psychological trick that 99% of people fall for without ever realizing it.\n"
        "Master manipulators use strategic pauses and subtle body language to make you agree to almost anything.\n"
        "Once you understand how the human brain craves approval, you can spot the trap instantly.\n"
        "Pay close attention next time someone asks you a loaded question."
    ),
    "Pyramids of Ancient Egypt": (
        "Thousands of years ago, majestic stone pyramids rose against the golden Egyptian desert.\n"
        "Skilled craftsmen and workers carved colossal limestone blocks under the blazing sun.\n"
        "Mysterious hieroglyphs decorated the inner chambers of ancient pharaoh tombs.\n"
        "Today, the Great Sphinx guards the secrets of an extraordinary ancient civilization."
    ),
    "Cyberpunk AI Metropolis": (
        "In a neon-lit futuristic city, flying autonomous vehicles glide between towering skyscrapers.\n"
        "Massive holographic billboards illuminate bustling rain-slicked city streets below.\n"
        "Advanced humanoids and artificial intelligence assistants interact with citizens seamlessly.\n"
        "The digital metropolis pulses with quantum computing networks that power the tomorrow."
    ),
    "Deep Ocean Secrets": (
        "Beneath the shimmering ocean waves lies a hidden world of vibrant turquoise coral reefs.\n"
        "Bioluminescent jellyfish drift gracefully through the deep darkness of the abyss.\n"
        "Schools of colorful tropical fish dance in synchronized harmony with the ocean currents.\n"
        "The mysterious depths of our planet hold beauty beyond human imagination."
    ),
    "Serene Mountain Sunrise": (
        "Crisp morning fog rolls gently across towering snow-covered mountain peaks.\n"
        "The first golden rays of sunlight pierce through a peaceful evergreen pine forest.\n"
        "A crystal clear alpine river flows over smooth pebbles and tranquil waterfalls.\n"
        "Nature awakens in serene quietude, welcoming the gift of a brand new day."
    )
}

def calculate_content_duration(text: str, is_image: bool = False, speed: float = 1.25) -> float:
    """
    Computes natural speech-paced scene duration:
    Average speaking pace is ~2.3 words/sec scaled by speed (default 1.25x for punchy creator pacing).
    Adds a subtle 0.20s natural pause buffer.
    """
    if not text or not text.strip():
        return 3.0
    words = [w for w in text.split() if w.strip()]
    eff_speed = max(0.5, speed)
    raw_speech_dur = (len(words) / (2.3 * eff_speed)) + (0.20 / eff_speed)
    return round(max(2.0, min(raw_speech_dur, 20.0)), 1)


THEMATIC_SCENARIOS = [
    {
        "triggers": ["egypt", "pyramid", "pharaoh", "desert", "tomb", "hieroglyph", "sphinx", "limestone"],
        "scenario": "Ancient Egyptian pyramids and monuments in golden desert landscape",
        "keyword": "ancient egypt pyramids desert",
        "dalle": "Cinematic wide-angle photorealistic view of majestic ancient Egyptian pyramids in the golden desert under dramatic sunlight, 8k resolution, National Geographic documentary style"
    },
    {
        "triggers": ["futuristic", "cyberpunk", "hologram", "ai", "neon", "robot", "humanoid", "metropolis", "flying", "autonomous"],
        "scenario": "Futuristic cyberpunk neon metropolis with high-tech skyline",
        "keyword": "cyberpunk futuristic city neon",
        "dalle": "Cinematic photorealistic view of a futuristic neon-lit cyberpunk city at night with towering skyscrapers and glowing holographic displays, 8k Unreal Engine rendering style"
    },
    {
        "triggers": ["ocean", "sea", "coral", "reef", "jellyfish", "fish", "marine", "underwater", "abyss", "aquatic"],
        "scenario": "Deep underwater ocean coral reef with colorful marine life",
        "keyword": "underwater ocean coral marine",
        "dalle": "Stunning photorealistic underwater view of a vibrant coral reef with tropical marine life swimming in crystal-clear turquoise waters, cinematic documentary 8k"
    },
    {
        "triggers": ["mountain", "peak", "alpine", "snow", "forest", "pine", "river", "sunrise", "fog", "waterfall"],
        "scenario": "Majestic mountain peak and pine forest landscape at golden sunrise",
        "keyword": "mountain sunrise nature landscape",
        "dalle": "Breathtaking photorealistic landscape of snow-draped mountain peaks with morning mist rising above an alpine evergreen forest at golden hour sunrise, 8k cinematic"
    },
    {
        "triggers": ["space", "star", "galaxy", "cosmos", "planet", "orbit", "universe", "nebula", "astronaut"],
        "scenario": "Deep space galaxy with glowing nebulae and cosmic starfields",
        "keyword": "space galaxy stars cosmos",
        "dalle": "Spectacular photorealistic cosmic view of deep space with swirling colorful nebulae, distant glittering stars and planets, high quality NASA cinematic visual"
    },
    {
        "triggers": ["city", "urban", "skyline", "traffic", "street", "downtown", "crowd", "building", "subway"],
        "scenario": "Modern bustling city skyline and vibrant downtown urban streets",
        "keyword": "modern city urban skyline street",
        "dalle": "Cinematic aerial view of modern city skyline with towering glass skyscrapers and bustling urban streets during golden hour, 8k commercial stock photography"
    },
    {
        "triggers": ["technology", "digital", "data", "code", "cyber", "network", "computer", "software", "screen"],
        "scenario": "High-tech digital network with glowing data streams and servers",
        "keyword": "technology digital data network",
        "dalle": "Sleek modern visual of technology infrastructure, glowing digital data streams, fiber optic networks, and high-tech computing server room, 8k"
    },
    {
        "triggers": ["history", "ancient", "castle", "knight", "empire", "statue", "ruins", "temple", "monument"],
        "scenario": "Historic stone castle ruins and ancient monument architectural landscape",
        "keyword": "ancient ruins historical monument",
        "dalle": "Cinematic photorealistic capture of ancient stone castle ruins on a dramatic hillside under soft overcast skies, 8k historical epic cinematography"
    }
]

HINDI_CONCEPT_MAP = {
    # Architecture & Monuments
    "इमारत": "monument architecture structure",
    "महल": "royal palace architecture",
    "किला": "ancient fortress castle",
    "मकबरा": "mausoleum tomb monument",
    "कब्र": "historic tomb monument",
    "मंदिर": "ancient temple architecture",
    "गुंबद": "architectural dome",
    "मीनार": "minaret tower landmark",
    "संगमरमर": "carved marble stone",
    "पत्थर": "carved stone sculpture",
    "नक्काशी": "intricate carving craftsmanship",
    "वास्तुकला": "ancient architecture design",
    "दरवाजा": "grand gateway entrance",
    "कमरा": "interior chamber room",
    "तहखाना": "underground secret chamber",
    "स्तंभ": "ancient pillar column",
    "खंभा": "ancient stone pillar",
    # History, Royalty & Figures
    "राजा": "ancient king royal monarch",
    "रानी": "queen royal empress",
    "बादशाह": "emperor ruler monarch",
    "योद्धा": "ancient warrior fighter",
    "सैनिक": "soldiers military army",
    "सेना": "army military soldiers",
    "युद्ध": "ancient battle warfare",
    "तलवार": "sword weapon warrior",
    "कारीगर": "artisan craftsman sculpture",
    "मजदूर": "construction workers builders",
    "इतिहास": "ancient history documentary",
    "प्राचीन": "ancient historical heritage",
    "सभ्यता": "ancient civilization history",
    # Nature, Cosmos & Environment
    "नदी": "river water landscape",
    "बगीचा": "lush garden flowers courtyard",
    "पानी": "water reflection fountain",
    "समुद्र": "ocean sea waves landscape",
    "पहाड़": "majestic mountains landscape",
    "जंगल": "dense forest nature trees",
    "रेगिस्तान": "desert sand dunes landscape",
    "आकाश": "dramatic sky clouds",
    "सूरज": "golden sun sunset sunrise",
    "चांद": "moon night stars",
    "अंतरिक्ष": "outer space galaxy stars",
    "ग्रह": "planet universe cosmos",
    # Mystery, Science & Exploration
    "रहस्य": "mysterious dramatic secrets",
    "खजाना": "ancient gold treasure wealth",
    "सच्चाई": "mystery reveal truth documentary",
    "खोज": "exploration archaeological discovery",
    "विज्ञान": "science futuristic technology",
    "तकनीक": "technology innovation digital",
}

TOPIC_ASPECT_ROTATION = [
    "cinematic wide angle",
    "detailed close up",
    "aerial drone perspective",
    "dramatic cinematic lighting",
    "sunset golden hour",
    "atmospheric 4k documentary",
    "panoramic landscape view",
    "intricate textural details",
    "night moonlit atmosphere",
    "epic visual composition"
]

def translate_to_english_fast(text: str) -> str:
    """
    Fast dynamic translation for Indic scripts (Marathi/Hindi) so search engines
    receive accurate keywords matching the exact script line. 100% free with no keys.
    """
    if not text or not text.strip():
        return ""
    has_devanagari = any('\u0900' <= ch <= '\u097f' for ch in text)
    if not has_devanagari:
        return text.strip()
    try:
        import requests
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": text[:350]},
            timeout=4,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            translated = "".join([item[0] for item in r.json()[0] if item and item[0]])
            if translated and len(translated) > 2:
                return translated.strip()
    except Exception:
        pass
    return text.strip()

def extract_scenario_search(sentence: str, topic: str = "", scene_idx: int = 1) -> dict:
    """
    100% Dynamic Script-Driven Entity & Keyword Extractor:
    Extracts visual subjects, actions, and entities DIRECTLY from the actual sentence text.
    Zero static hardcoded concept maps or preset rotations!
    """
    clean_topic = topic.strip() if topic else ""
    if not sentence or not sentence.strip():
        base = clean_topic or "cinematic scene"
        return {
            "scenario": f"{base.title()} cinematic scene",
            "keyword": f"{base}".strip(),
            "dalle_prompt": f"Cinematic 8k high-definition view of {base}"
        }

    # 1. Translate dynamically if sentence is in Marathi/Hindi
    translated = translate_to_english_fast(sentence)

    # 2. Extract substantive content words directly from the script line
    raw_tokens = re.findall(r'[a-zA-Z0-9\'-]{3,}', translated.lower())
    substantive_tokens = [w for w in raw_tokens if w not in STOPWORDS and not w.isdigit()]

    # Filter out words already in topic
    t_lower = clean_topic.lower()
    script_entities = [w for w in substantive_tokens if w not in t_lower][:3]

    if clean_topic:
        if script_entities:
            scenario_kw = f"{clean_topic} {' '.join(script_entities)}".strip()
        else:
            scenario_kw = clean_topic
    else:
        scenario_kw = " ".join(substantive_tokens[:4]) if substantive_tokens else sentence.strip()[:40]

    dalle_p = f"Cinematic 8k photorealistic documentary scene of {clean_topic + ': ' if clean_topic else ''}{sentence.strip()[:100]}, 35mm film photography, volumetric lighting, epic dramatic atmosphere, highly detailed"

    return {
        "scenario": f"Scene {scene_idx}: ({sentence.strip()[:60]}...)",
        "keyword": scenario_kw,
        "dalle_prompt": dalle_p
    }

def extract_keywords(sentence: str, max_words: int = 3, topic: str = "") -> str:
    """Legacy helper maintained for backward compatibility; calls dynamic scenario extractor."""
    return extract_scenario_search(sentence, topic=topic)["keyword"]

def generate_fallback_keywords(sentence: str, primary_kw: str, topic: str = "") -> list[str]:
    """
    Generates intelligent alternative queries derived 100% dynamically from the sentence text.
    Zero static aspect rotations!
    """
    fallbacks = []
    clean_topic = topic.strip() if topic else ""
    translated = translate_to_english_fast(sentence)
    tokens = [w for w in re.findall(r'[a-zA-Z0-9]{3,}', translated.lower()) if w not in STOPWORDS and not w.isdigit()]

    if clean_topic:
        for t in tokens[:4]:
            cand = f"{clean_topic} {t}"
            if cand.lower() != primary_kw.lower() and cand not in fallbacks:
                fallbacks.append(cand)
        if clean_topic.lower() != primary_kw.lower():
            fallbacks.append(clean_topic)
    else:
        for i in range(min(4, len(tokens) - 1)):
            pair = f"{tokens[i]} {tokens[i+1]}"
            if pair.lower() != primary_kw.lower() and pair not in fallbacks:
                fallbacks.append(pair)
        for t in tokens[:3]:
            if t not in fallbacks:
                fallbacks.append(t)

    return fallbacks

# Target distribution: ~60% video clips and ~40% still images across scenes
MEDIA_MIX_RATIO = ["video", "video", "image", "video", "image"]

GENERIC_PLACEHOLDERS = {
    "youtube_video", "youtube video", "untitled", "video", "asset", "project",
    "my_video", "new video", ""
}
generic_placeholders = GENERIC_PLACEHOLDERS

def detect_script_main_topic(script_text: str, custom_topic: str = "") -> str:
    """
    Identifies the core topic / subject of the entire video script.
    If custom_topic is provided, returns that cleaned topic.
    Otherwise, inspects all sentences across the entire script for dominant thematic triggers and subject nouns.
    """
    if custom_topic and custom_topic.strip() and custom_topic.strip().lower() not in GENERIC_PLACEHOLDERS:
        return custom_topic.strip()
    
    if not script_text or not script_text.strip():
        return "cinematic documentary"
    
    full_lower = script_text.lower()
    
    # 1. Match against known thematic scenarios across the ENTIRE script
    best_entry = None
    max_hits = 0
    for entry in THEMATIC_SCENARIOS:
        hits = sum(1 for t in entry["triggers"] if t in full_lower)
        if hits > max_hits:
            max_hits = hits
            best_entry = entry
            
    if best_entry and max_hits >= 1:
        return best_entry["keyword"]
        
    # 2. Extract most frequent meaningful subject words across the whole script
    words = [w for w in re.sub(r'https?://\S+|[^\w\s]', ' ', full_lower).split() if len(w) > 3 and w not in STOPWORDS]
    if words:
        from collections import Counter
        counts = Counter(words)
        top_words = [w for w, c in counts.most_common(3)]
        return " ".join(top_words)
        
    return "cinematic documentary"

def parse_script_to_scenes(
    script_text: str,
    default_duration: int = 4,
    default_media: str = "invideo_mix",
    speed: float = 1.25,
    main_topic: str = ""
) -> list[dict]:
    """
    Splits script text into numbered scenes with:
    1. Universal punctuation support (Hindi Danda '।', '॥', Urdu '۔', English '.!?')
    2. 100% TOPIC-ANCHORED SEARCH: Every single scene query is anchored to the main topic!
    3. Scenario-wise search query and DALL-E prompt
    4. Dynamic content-dependent scene duration (InVideo AI style with speed scaling)
    5. Balanced media distribution (~60% video, ~40% photo)
    """
    if not script_text or not script_text.strip():
        return []

    SENTENCE_SPLIT_REGEX = r'(?<=[.!?।॥۔\n])\s+'
    raw_lines = [line.strip() for line in script_text.splitlines() if line.strip()]
    raw_chunks = []
    
    for line in raw_lines:
        sentences = re.split(SENTENCE_SPLIT_REGEX, line)
        for s in sentences:
            s_clean = s.strip()
            if len(s_clean) > 3:
                raw_chunks.append(s_clean)

    if not raw_chunks:
        sentences = re.split(SENTENCE_SPLIT_REGEX, script_text.strip())
        raw_chunks = [s.strip() for s in sentences if len(s.strip()) > 3]

    detected_topic = detect_script_main_topic(script_text, custom_topic=main_topic)

    scenes = []
    cum_time = 0.0
    for idx, text in enumerate(raw_chunks, start=1):
        # Media assignment
        if default_media == "ai_flux":
            assigned_media = "ai_flux"
        elif default_media == "hybrid_ai":
            assigned_media = "video" if idx % 2 == 1 else "ai_flux"
        elif idx == 1:
            assigned_media = "video" if default_media in ["video", "invideo_mix", "both"] else default_media
        elif default_media in ["video", "image"]:
            assigned_media = default_media
        elif default_media == "both":
            assigned_media = "both"
        else:  # 'invideo_mix'
            assigned_media = MEDIA_MIX_RATIO[(idx - 1) % len(MEDIA_MIX_RATIO)]

        # Dynamic duration: speech-paced with speed scaling (default 1.0x natural human tempo)
        is_img = (assigned_media in ["image", "ai_flux"])
        dynamic_dur = calculate_content_duration(text, is_image=is_img, speed=speed)

        # 🎯 FIRST 3 MINUTES TOPIC LOCK:
        # All scenes whose cumulative start time is within the first 180 seconds (3 minutes)
        # MUST strictly depict the core video topic (no generic off-topic stock visuals allowed!)
        is_first_3_mins = (cum_time < 180.0)
        cum_time += dynamic_dur

        # In the first 3 minutes, allow both images & videos so authentic topic photos are fully utilized
        if is_first_3_mins and assigned_media not in ["ai_flux"]:
            assigned_media = "both"

        # SCENE 1 IS THE OPENING HOOK:
        # Strictly anchor to the Main Video Topic with dramatic, cinematic hero visual!
        if idx == 1:
            hook_kw = f"{detected_topic} cinematic dramatic reveal"
            hook_scenario = f"🔥 0-3m Hook Hero Visual: {detected_topic.title()}"
            hook_prompt = f"Breathtaking cinematic wide-angle opening hero movie still of {detected_topic}, epic dramatic lighting, volumetric atmosphere, 8k National Geographic documentary style, photorealistic masterpiece"
            scenes.append({
                "no": str(idx).zfill(2),
                "text": text,
                "keyword": hook_kw,
                "scenario": hook_scenario,
                "dalle_prompt": hook_prompt,
                "type": assigned_media,
                "media_pref": assigned_media,
                "duration": dynamic_dur,
                "content_duration": dynamic_dur,
                "custom_search": hook_kw,
                "is_hook": True,
                "is_first_3_mins": True,
                "strict_topic_lock": True,
                "hook_topic": detected_topic,
                "main_topic": detected_topic
            })
            continue

        # Scenario extraction for all subsequent scenes (ALWAYS topic anchored!)
        scenario_data = extract_scenario_search(text, topic=detected_topic, scene_idx=idx)
        sc_kw = scenario_data["keyword"]
        for ph in ["YouTube_Video", "youtube_video", "YouTube Video", "youtube video"]:
            sc_kw = sc_kw.replace(ph, "").strip()
        if is_first_3_mins and detected_topic and detected_topic.lower() not in GENERIC_PLACEHOLDERS:
            # Enforce topic-first keywords for the entire first 3 minutes
            sc_kw = f"{detected_topic} {sc_kw.replace(detected_topic, '').strip()}".strip()

        sc_prompt = scenario_data["dalle_prompt"]
        if is_first_3_mins:
            sc_prompt = f"Cinematic 8k photorealistic documentary scene of {detected_topic}: {text}, 35mm film still, national geographic cinematography, highly detailed, photorealistic masterpiece"

        scenes.append({
            "no": str(idx).zfill(2),
            "text": text,
            "keyword": sc_kw,
            "scenario": f"🎯 [0-3m Topic-Lock] {scenario_data['scenario']}" if is_first_3_mins else scenario_data["scenario"],
            "dalle_prompt": sc_prompt,
            "type": assigned_media,
            "media_pref": assigned_media,
            "duration": dynamic_dur,
            "content_duration": dynamic_dur,
            "custom_search": sc_kw,
            "is_hook": False,
            "is_first_3_mins": is_first_3_mins,
            "strict_topic_lock": is_first_3_mins,
            "hook_topic": detected_topic,
            "main_topic": detected_topic
        })

    return scenes


def generate_creator_scripts_and_shorts(
    topic: str,
    language: str = "Hinglish",
    openai_key: str = ""
) -> dict:
    """
    Generates an elite YouTube Creator Long Video Script with an irresistible triggering hook,
    plus 4 distinct standalone YouTube Shorts (15-25s each) with intense swipe-stopping hooks.
    Uses OpenAI if available, with a powerful offline psychological creator template engine fallback.
    """
    clean_topic = topic.strip() if topic else "Ancient Mysteries"
    clean_lang = language.strip() or "Hinglish"
    
    # 1. Attempt OpenAI GPT Generation if key is provided
    if openai_key and openai_key.startswith("sk-"):
        try:
            import requests, json
            sys_msg = (
                "You are an elite YouTube creator and video editor (like MrBeast, Ali Abdaal, Dhruv Rathee). "
                "Generate 1 punchy long video script (4-6 sentences, with an irresistible first 3-second hook) "
                "AND 4 distinct YouTube Shorts scripts (each 2-3 sentences, with extreme swipe-stopping hooks) for the given topic. "
                "Respond ONLY with valid JSON with keys 'long_script' (string with newlines) and 'shorts' (list of 4 objects each with 'title', 'hook_type', 'script')."
            )
            user_msg = f"Topic: {clean_topic}\nLanguage Style: {clean_lang} (natural creator speech, conversational, emotional, NO boring intros)"
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key.strip()}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": user_msg}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.85
                },
                timeout=25
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                if "long_script" in parsed and "shorts" in parsed and len(parsed["shorts"]) >= 3:
                    return {
                        "topic": clean_topic,
                        "long_script": parsed["long_script"].strip(),
                        "shorts": parsed["shorts"][:4]
                    }
        except Exception as e:
            print(f"OpenAI script generator notice (using fallback): {e}")

    # 2. Resilient Top Creator Algorithmic Generator (Guarantees instant, high-converting scripts)
    is_hindi = "hindi" in clean_lang.lower() or "hinglish" in clean_lang.lower()
    t_clean = clean_topic.replace('"', '').strip()
    
    if is_hindi:
        long_script = (
            f"रुकिए, क्या आपको पता है कि {t_clean} के बारे में जो बात 99% लोग सच मानते हैं, वो असल में एक बहुत बड़ा झूठ है?\n"
            f"रिसर्चर्स और टॉप एक्सपर्ट्स ने जब इसकी गहराई में पड़ताल की, तो उन्हें ऐसे सबूत मिले जिन्होंने सबको हैरान कर दिया।\n"
            f"कैमरे और सैटेलाइट्स ने इस रहस्य के पीछे छुपे उन पैटर्न्स को रिकॉर्ड किया है जिन्हें सालों तक छुपाया गया था।\n"
            f"अगर आप इसे ध्यान से समझें, तो आपकी सोचने की पूरी दिशा हमेशा के लिए बदल जाएगी।\n"
            f"तो सवाल यह है—क्या आप इस छिपे हुए सच का सामना करने के लिए तैयार हैं?"
        )
        shorts = [
            {
                "title": f"Short #1: 3-Second Pattern Interrupt ({t_clean[:25]})",
                "hook_type": "⚡ Pattern Interrupt (Swipe Stopper)",
                "script": (
                    f"स्क्रीन स्वाइप करने से पहले सिर्फ 10 सेकंड रुकिए, क्योंकि {t_clean} का यह डार्क सच आपको कोई नहीं बताएगा!\n"
                    f"जो चीज़ बाहर से नॉर्मल दिखती है, उसके अंदर का राज़ देखकर बड़े-बड़े एक्सपर्ट्स के होश उड़ गए।\n"
                    f"अगर आपको यकीन नहीं आता, तो खुद ये अनसुने फैक्ट्स चेक कर लीजिए।"
                )
            },
            {
                "title": f"Short #2: The Forbidden Mystery ({t_clean[:25]})",
                "hook_type": "🕵️ The Forbidden Secret / Mystery",
                "script": (
                    f"क्या कभी सोचा है कि {t_clean} के इस अजीबोगरीब पहलू पर कोई खुलकर बात क्यों नहीं करता?\n"
                    f"सालों की रिसर्च के बाद जो दस्तावेज़ सामने आए, उन्होंने इतिहास के पन्नों को हिलाकर रख दिया।\n"
                    f"इस सच को जानने के बाद आप इसे कभी पहले जैसा नहीं देख पाएंगे।"
                )
            },
            {
                "title": f"Short #3: The 99% Reality Check ({t_clean[:25]})",
                "hook_type": "🧠 99% Myth vs Reality Check",
                "script": (
                    f"99% लोग {t_clean} को लेकर यह सबसे बड़ी गलती करते हैं, और उन्हें इसका अंदाज़ा तक नहीं होता!\n"
                    f"हकीकत में साइंस और डेटा कुछ ऐसा दिखाते हैं जो आम धारणा से बिल्कुल उलट है।\n"
                    f"क्या आप भी अब तक इसी गलतफहमी में जी रहे थे?"
                )
            },
            {
                "title": f"Short #4: The Final Warning / Takeaway ({t_clean[:25]})",
                "hook_type": "🚨 Urgent Warning & Call-to-Action",
                "script": (
                    f"अगर आपने आज {t_clean} के इस बदलाव को नज़रअंदाज़ किया, तो आगे चलकर बहुत देर हो सकती है!\n"
                    f"दुनिया तेज़ी से बदल रही है और जो लोग इस सच को पहले समझ लेते हैं, वही आगे रहते हैं।\n"
                    f"अपनी राय नीचे कमेंट्स में ज़रूर बताइए!"
                )
            }
        ]
    else:
        long_script = (
            f"Stop scrolling, because what 99% of people believe about {t_clean} is completely backwards.\n"
            f"When top researchers finally looked past the mainstream headlines, the actual evidence left everyone speechless.\n"
            f"High-resolution documentation and raw data revealed a pattern that had been hidden in plain sight for decades.\n"
            f"The deeper you investigate the numbers, the more obvious the real truth becomes.\n"
            f"So the question is: are you ready to see what is really happening behind closed doors?"
        )
        shorts = [
            {
                "title": f"Short #1: The 3-Second Shock Hook ({t_clean[:25]})",
                "hook_type": "⚡ Extreme Pattern Interrupt",
                "script": (
                    f"Wait! Before you swipe away, this terrifying fact about {t_clean} will change how you think forever.\n"
                    f"Behind the calm surface lies an untold reality that most people are completely blind to.\n"
                    f"Look at the evidence and decide for yourself."
                )
            },
            {
                "title": f"Short #2: The Hidden Truth Nobody Mentions ({t_clean[:25]})",
                "hook_type": "🕵️ The Forbidden Secret",
                "script": (
                    f"Why is almost nobody talking about what really happened with {t_clean}?\n"
                    f"Newly uncovered records paint a completely different picture than the official narrative.\n"
                    f"Once you notice this pattern, you simply cannot unsee it."
                )
            },
            {
                "title": f"Short #3: The Fatal 99% Mistake ({t_clean[:25]})",
                "hook_type": "🧠 The Contrarian Reality Check",
                "script": (
                    f"99% of people make this catastrophic mistake when thinking about {t_clean}.\n"
                    f"Modern data proves that doing the exact opposite is the real secret to mastering it.\n"
                    f"Are you still falling into this common psychological trap?"
                )
            },
            {
                "title": f"Short #4: The Urgent Warning ({t_clean[:25]})",
                "hook_type": "🚨 Urgent Warning & Takeaway",
                "script": (
                    f"If you ignore what is happening right now with {t_clean}, you will regret it sooner than you think!\n"
                    f"Things are moving at lightning speed, and only those who adapt today will stay ahead of the curve.\n"
                    f"Share this with someone who needs to hear it today."
                )
            }
        ]

    return {
        "topic": clean_topic,
        "long_script": long_script,
        "shorts": shorts
    }

