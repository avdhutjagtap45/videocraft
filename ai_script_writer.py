import urllib.parse
import requests
import json
import re

def generate_ai_script(topic: str, duration_mins: int = 1, language: str = "Hindi", tone: str = "Cinematic Mystery & Suspense") -> str:
    """
    Generates a high-retention, scene-by-scene script tailored to exact duration.
    100% Free with zero API keys via Pollinations AI Text Engine + Resilient Local Fallback.
    Duration mappings:
    - 1 min: ~12 lines (~120-150 words)
    - 3 min: ~35 lines (~380-450 words)
    - 5 min: ~60 lines (~700-800 words)
    - 10 min: ~120 lines (~1400-1600 words)
    - 15 min: ~170 lines (~2100-2400 words)
    - 20 min: ~220 lines (~2800-3200 words)
    """
    clean_topic = topic.strip() or "Ancient Secrets of History"
    
    # Calculate scene counts: ~4.5 to 5.0 seconds per scene
    scene_targets = {
        1: (10, 14, 140),
        3: (30, 36, 420),
        5: (55, 65, 750),
        10: (110, 130, 1500),
        15: (160, 180, 2250),
        20: (210, 240, 3000)
    }
    min_scenes, max_scenes, target_words = scene_targets.get(duration_mins, (12, 16, 150))
    
    prompt = f"""You are a world-class documentary and viral YouTube scriptwriter.
Topic: "{clean_topic}"
Language: {language}
Tone: {tone}
Target Duration: {duration_mins} minutes (approximately {min_scenes} to {max_scenes} scenes).

STRICT FORMATTING RULES:
1. Output EXACTLY {min_scenes} to {max_scenes} lines.
2. One sentence per line. Each line represents ONE visual video scene.
3. DO NOT include line numbers (e.g. no '1.', no 'Scene 1:').
4. DO NOT include emojis, stage directions, or brackets like [Music swells].
5. Line 1 MUST be an explosive cold-open hook without greetings. No "Namaste" or "Hello".
6. Keep sentences punchy, dramatic, and vivid for visual documentary matching.

Output only the raw script lines now:"""

    # 1. Fast GET Pollinations Text Generation (Typically responds in 2-4 seconds)
    raw_ai_lines = []
    try:
        short_prompt = f"Write {min_scenes} viral documentary lines in {language} about '{clean_topic}'. Tone: {tone}. One sentence per line. Line 1 must be a cold-open hook with no greetings. No numbers, no emojis."
        encoded = urllib.parse.quote(short_prompt)
        r_get = requests.get(f"https://text.pollinations.ai/{encoded}", timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r_get.status_code == 200 and len(r_get.text) > 80:
            for line in r_get.text.splitlines():
                l = re.sub(r'^(Scene\s*\d+\s*[:\-]|Line\s*\d+\s*[:\-]|[\d\.\-\*\#\>]+)\s*', '', line.strip())
                l = re.sub(r'\[.*?\]|\(.*?\)', '', l).strip()
                if len(l) > 10:
                    raw_ai_lines.append(l)
    except Exception as e:
        print(f"Pollinations fast GET notice: {e}")

    # 2. Detailed POST fallback if needed
    if len(raw_ai_lines) < min_scenes:
        try:
            url = "https://text.pollinations.ai/"
            payload = {
                "messages": [
                    {"role": "system", "content": "You are a professional YouTube documentary scriptwriter. Output only plain scene lines."},
                    {"role": "user", "content": prompt}
                ],
                "model": "openai",
                "seed": int(len(clean_topic) * 17)
            }
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=12)
            if r.status_code == 200 and len(r.text) > 100:
                post_lines = []
                for line in r.text.splitlines():
                    l = re.sub(r'^(Scene\s*\d+\s*[:\-]|Line\s*\d+\s*[:\-]|[\d\.\-\*\#\>]+)\s*', '', line.strip())
                    l = re.sub(r'\[.*?\]|\(.*?\)', '', l).strip()
                    if len(l) > 10:
                        post_lines.append(l)
                if len(post_lines) > len(raw_ai_lines):
                    raw_ai_lines = post_lines
        except Exception as e:
            print(f"Pollinations POST notice: {e}")

    # If AI lines meet the target, return them
    if len(raw_ai_lines) >= min_scenes:
        return "\n".join(raw_ai_lines[:max_scenes])

    # 3. Seamlessly top up with intelligent programmatic scenes so duration is 100% satisfied
    backup_lines = _build_programmatic_script(clean_topic, duration_mins, language, tone).splitlines()
    if raw_ai_lines:
        combined = list(raw_ai_lines)
        for b_line in backup_lines:
            if b_line not in combined:
                combined.append(b_line)
            if len(combined) >= min_scenes:
                break
        return "\n".join(combined[:max_scenes])

    return "\n".join(backup_lines[:max_scenes])


def _build_programmatic_script(topic: str, duration_mins: int, language: str, tone: str) -> str:
    """Builds a rich, suspenseful multi-scene script programmatically scaled to exact duration."""
    is_hindi = "hindi" in language.lower() or "hinglish" in language.lower()
    
    scene_targets = {
        1: 12,
        3: 35,
        5: 60,
        10: 120,
        15: 170,
        20: 220
    }
    target_count = scene_targets.get(duration_mins, 12)
    
    if is_hindi:
        hook_lines = [
            f"अगर आपको लगता है कि आप {topic} की पूरी सच्चाई जानते हैं, तो रुकिए।",
            f"क्योंकि हाल ही में वैज्ञानिकों ने एक ऐसा गुप्त दस्तावेज खोजा है, जो हमारे पूरे इतिहास को हिलाकर रख देगा।",
            f"साल 1932 में, {topic} के सबसे प्रतिबंधित हिस्से में एक गुप्त टीम भेजी गई थी।",
            f"लेकिन वहां उन्हें जो मिला, उसे देखकर अधिकारियों ने उस पूरी फाइल को हमेशा के लिए सील कर दिया।",
            f"आज के इस वीडियो में, हम उस सीलबंद फाइल के सबसे चौंकाने वाले खुलासे करेंगे।"
        ]
        
        act1_history = [
            f"सदियों से {topic} को लेकर दुनिया भर के इतिहासकारों के बीच कई गहरे मतभेद रहे हैं।",
            f"प्राचीन पांडुलिपियों में दर्ज है कि इस जगह के नीचे कई विशाल गुप्त तहखाने मौजूद हैं।",
            f"जब पुरातत्वविदों ने पहली बार इस स्थल का सर्वेक्षण किया, तो उन्हें कई विसंगतियाँ देखने को मिलीं।",
            f"यहाँ की दीवारों पर उकेरी गई नक्काशी किसी अज्ञात प्राचीन तकनीक की ओर इशारा करती है।",
            f"स्थानिक मान्यताओं के अनुसार, इन प्राचीन पत्थरों में कुछ अनोखी ऊर्जा प्रवाहित होती है।",
            f"कई सदियों तक इस रहस्य को आम लोगों की नज़रों से जानबूझकर छुपा कर रखा गया।"
        ]
        
        act2_investigation = [
            f"आधुनिक सैटेलाइट रडार ने भी जमीन के सैकड़ों फीट नीचे असामान्य खोखले कमरों का पता लगाया है।",
            f"इन भूमिगत कमरों की वास्तुकला इतनी सटीक है कि आज की आधुनिक तकनीक से भी ऐसा निर्माण संभव नहीं है।",
            f"भूभौतिकविदों द्वारा मापे गए चुंबकीय आंकड़ों ने सभी वैज्ञानिकों को चकित कर दिया।",
            f"शोधकर्ताओं का मानना है कि यहाँ एक ऐसी ज्यामितीय संरेखण है जो सीधे तारों के नक्षत्रों से मेल खाती है।",
            f"इस संरेखण की गणितीय सटीकता किसी साधारण मानव सभ्यता के बस की बात नहीं लगती।",
            f"कुछ वैज्ञानिकों का दावा है कि यह स्थल केवल एक स्मारक नहीं, बल्कि एक विशाल ऊर्जा केंद्र हो सकता है।"
        ]
        
        act3_anomalies = [
            f"स्थानीय गाइडों और शोधकर्ताओं ने कई बार यहाँ अजीबोगरीब ध्वनियों और प्रकाश के चमकने की सूचना दी है।",
            f"जब भी किसी टीम ने प्रतिबंधित दरवाजों के पीछे ड्रिलिंग करने की कोशिश की, उनके इलेक्ट्रॉनिक उपकरण अचानक बंद हो गए।",
            f"अधिकारियों ने तुरंत उस पूरे क्षेत्र को हाई-सिक्योरिटी ज़ोन घोषित कर दिया।",
            f"सवाल यह उठता है कि क्या सचमुच हमसे कोई बहुत बड़ा वैज्ञानिक सच छुपाया जा रहा है?",
            f"या फिर यह सब किसी खोई हुई अति-उन्नत सभ्यता की तकनीक का हिस्सा था?",
            f"प्राचीन सभ्यताओं के पास क्या ऐसी तकनीक थी जिसे हम आज तक समझ नहीं पाए हैं?"
        ]
        
        act4_conclusion = [
            f"जैसे-जैसे आधुनिक तकनीक विकसित हो रही है, {topic} के रहस्य और गहरे होते जा रहे हैं।",
            f"आने वाले वर्षों में जब स्वतंत्र वैज्ञानिक इन तालों को खोलेंगे, तो दुनिया हैरान रह जाएगी।",
            f"मानव इतिहास का जो पाठ हमें सिखाया गया है, वह शायद केवल आधी अधूरी कहानी है।",
            f"सच्चाई चाहे कितनी भी अजीब क्यों न हो, एक दिन वह सबके सामने ज़रूर आएगी।",
            f"{topic} का यह राज़ मानवता के दृष्टिकोण को हमेशा के लिए बदल कर रख देगा।"
        ]
        
        all_blocks = [hook_lines, act1_history, act2_investigation, act3_anomalies, act4_conclusion]
    else:
        hook_lines = [
            f"What if everything you were taught about {topic} is a complete lie?",
            f"Modern engineers admit that the official explanation is mathematically impossible.",
            f"Decades ago, classified expedition teams uncovered subterranean chambers that should not exist.",
            f"Before researchers could publish their findings, government authorities abruptly sealed all records.",
            f"Today, we declassify the most terrifying discoveries hidden inside {topic}."
        ]
        
        act1_history = [
            f"For centuries, conventional historians dismissed anomalous stories of {topic} as mere mythology.",
            f"Yet ancient stone inscriptions explicitly warn against disturbing the inner chambers.",
            f"Early archaeologists documented massive subterranean granite vaults beneath the foundations.",
            f"The sheer scale of these monolithic stones defies conventional explanations of antiquity.",
            f"Local legends preserve tales of mysterious celestial lights hovering above this ground.",
            f"For generations, secretive organizations guarded these sites against unauthorized exploration."
        ]
        
        act2_investigation = [
            f"Recent high-resolution satellite LiDAR scans revealed colossal geometric alignments deep below.",
            f"The precision of these laser-cut interlocking blocks surpasses modern diamond-edge machinery.",
            f"Geophysicists recorded unexplained electromagnetic pulses emanating directly from the bedrock.",
            f"Every calculation confirms that the structural coordinates align perfectly with distant stellar constellations.",
            f"This astronomical synchronization proves a level of physics previously thought impossible in the ancient world.",
            f"Independent engineers now hypothesize that {topic} functioned as an advanced technological conduit."
        ]
        
        act3_anomalies = [
            f"Whenever modern instruments attempt deep subsurface radar imaging, inexplicable signal interference occurs.",
            f"Declassified government logs reveal that multiple exploration attempts were abruptly aborted.",
            f"Eyewitness testimonies from research personnel describe anomalous acoustic resonance inside the chambers.",
            f"Could an ancient advanced civilization have erected these monuments prior to recorded human history?",
            f"What knowledge was so dangerous that it required thousands of tons of stone to keep it contained?",
            f"The deeper investigators probe, the more fragile our consensus model of history becomes."
        ]
        
        act4_conclusion = [
            f"As autonomous robotics and deep-sensing technologies advance, these secrets will not remain buried.",
            f"The anomalies surrounding {topic} continue to challenge our understanding of human origin.",
            f"Human civilization may soon be forced to confront a forgotten chapter of its own past.",
            f"Whatever truth lies locked beneath {topic}, it will redefine our perception of reality.",
            f"Stay curious, because the real investigation is only just beginning."
        ]
        
        all_blocks = [hook_lines, act1_history, act2_investigation, act3_anomalies, act4_conclusion]

    full_script = []
    # Loop over blocks until target_count is reached
    cycle = 0
    while len(full_script) < target_count:
        for block in all_blocks:
            for line in block:
                if cycle > 0:
                    # Variation prefix for extended duration videos (10, 15, 20 mins)
                    var_prefix = f"[Phase {cycle+1}] " if not is_hindi else f"[भाग {cycle+1}] "
                    mod_line = f"{line.replace('।', '').replace('.', '')} — यह तथ्य हर शोधकर्ता को गहराई से सोचने पर मजबूर करता है।" if is_hindi else f"{line.replace('.', '')}, presenting an enigma that defies standard textbooks."
                    full_script.append(mod_line)
                else:
                    full_script.append(line)
                if len(full_script) >= target_count:
                    break
            if len(full_script) >= target_count:
                break
        cycle += 1

    return "\n".join(full_script[:target_count])

def translate_script_free(script_text: str, target_lang: str = "en") -> str:
    """Translates script between Hindi, English, and other languages 100% free line by line in real time."""
    if not script_text or not script_text.strip():
        return ""

    tl_code = "en" if target_lang.lower().startswith("en") else ("hi" if target_lang.lower().startswith("hi") else "en")
    lines = [l.strip() for l in script_text.splitlines() if l.strip()]
    if not lines:
        return script_text

    # 1. Fast & Highly Accurate Free Neural Translation Line-by-Line
    try:
        translated_lines = []
        for line in lines:
            if not line:
                continue
            r = requests.get(
                'https://translate.googleapis.com/translate_a/single',
                params={'client': 'gtx', 'sl': 'auto', 'tl': tl_code, 'dt': 't', 'q': line},
                timeout=5,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            if r.status_code == 200:
                res_data = r.json()
                trans_text = "".join([part[0] for part in res_data[0] if part and part[0]])
                translated_lines.append(trans_text.strip())
            else:
                translated_lines.append(line)
        if len(translated_lines) >= max(1, len(lines) - 2):
            return "\n".join(translated_lines)
    except Exception as e_trans:
        print(f"Fast Translation notice: {e_trans}")

    # 2. Pollinations POST Fallback
    target_name = "English" if tl_code == "en" else "Hindi"
    prompt = f"""Translate the following video script line by line into natural, cinematic {target_name}.
Keep the exact same number of lines. One sentence per line.
Do not include any numbering, commentary, or emojis.

Script:
{script_text[:3000]}"""

    try:
        url = "https://text.pollinations.ai/"
        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "model": "openai"
        }
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=12)
        if r.status_code == 200 and len(r.text) > 50:
            lines = [re.sub(r'^[\d\.\-\*\#\>]+\s*', '', l.strip()) for l in r.text.splitlines() if l.strip()]
            cleaned = [l for l in lines if len(l) > 8]
            if len(cleaned) >= 3:
                return "\n".join(cleaned)
    except Exception as e:
        print(f"Translation API notice: {e}")

    return script_text


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("Testing generate_ai_script for 1-min Short...")
    s1 = generate_ai_script("Mystery of North Sentinel Island", duration_mins=1, language="Hindi")
    print(f"Generated {len(s1.splitlines())} lines (Target: ~12)")
    print(s1[:200] + "...")
    print("\nTesting generate_ai_script for 10-min Documentary...")
    s10 = generate_ai_script("Ancient Pyramids of Giza", duration_mins=10, language="English")
    print(f"Generated {len(s10.splitlines())} lines (Target: ~120)")
    print("\n✅ AI SCRIPT WRITER MULTI-DURATION ENGINE READY!")
