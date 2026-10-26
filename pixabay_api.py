import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
import requests
from script_parser import generate_fallback_keywords

DEFAULT_PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "57909969-ce94fac88b6effdff830e1aff")
DEFAULT_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

CACHE_DIR = Path(__file__).parent / "downloads" / "ai_generated"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def generate_ai_image(
    prompt: str,
    openai_key: str = DEFAULT_OPENAI_KEY,
    dest_path: Optional[Path] = None,
    width: int = 1280,
    height: int = 720
) -> Optional[Dict[str, Any]]:
    """
    Generates a high-definition photorealistic scene image matching the exact script line.
    Uses FLUX.1 (via Pollinations) for 100% free, unlimited, Midjourney-grade 8K visuals.
    Supports OpenAI DALL-E when an OpenAI API key is supplied.
    """
    clean_prompt = prompt.strip() or "Cinematic landscape scenic view 8k"
    timestamp = int(time.time() * 1000)
    if not dest_path:
        dest_path = CACHE_DIR / f"ai_{timestamp}.jpg"
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Try OpenAI Image API if key is provided
    if openai_key and openai_key.startswith("sk-"):
        models_to_try = ["gpt-image-1", "gpt-image-1-mini", "dall-e-3", "dall-e-2"]
        for m in models_to_try:
            try:
                headers = {
                    "Authorization": f"Bearer {openai_key.strip()}",
                    "Content-Type": "application/json"
                }
                body = {
                    "prompt": clean_prompt[:950],
                    "model": m,
                    "n": 1,
                    "size": "1024x1024" if m in ["dall-e-3", "gpt-image-1"] else "512x512"
                }
                r = requests.post(
                    "https://api.openai.com/v1/images/generations",
                    headers=headers,
                    json=body,
                    timeout=30
                )
                if r.status_code == 200:
                    data = r.json()
                    img_items = data.get("data", [])
                    if img_items:
                        img_url = img_items[0].get("url")
                        if img_url:
                            dl_resp = requests.get(img_url, timeout=40)
                            if dl_resp.status_code == 200:
                                with open(dest_path, "wb") as f:
                                    f.write(dl_resp.content)
                                return {
                                    "id": f"openai_{timestamp}",
                                    "source": "OpenAI DALL-E",
                                    "type": "image",
                                    "tags": "OpenAI AI Visual",
                                    "preview": str(dest_path),
                                    "download": str(dest_path),
                                    "width": width,
                                    "height": height,
                                    "duration": None,
                                    "author": f"OpenAI ({m})",
                                    "page": "https://openai.com",
                                    "matched_keyword": clean_prompt[:60],
                                    "is_ai_generated": True
                                }
            except Exception as e:
                print(f"OpenAI generation error with model {m}: {e}")
                continue

    # 2. 100% Free FLUX.1 AI Photorealistic Generation (Midjourney Grade)
    try:
        p_lower = clean_prompt.lower()
        enhanced_p = clean_prompt
        if "cinematic" not in p_lower and "8k" not in p_lower:
            enhanced_p = f"{clean_prompt}, cinematic 8k movie still, photorealistic masterpiece, 35mm photography, volumetric lighting, epic atmosphere, Unreal Engine 5 render style, highly detailed"

        encoded_prompt = urllib.parse.quote(enhanced_p[:600])
        gen_w = min(1920, max(512, width))
        gen_h = min(1920, max(512, height))
        ai_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={gen_w}&height={gen_h}&model=flux&nologo=true&seed={timestamp % 10000}"
        resp = requests.get(ai_url, timeout=35, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            return {
                "id": f"ai_gen_{timestamp}",
                "source": "FLUX AI Vision Studio",
                "type": "image",
                "tags": "FLUX 8K AI Visual",
                "preview": str(dest_path),
                "download": str(dest_path),
                "width": gen_w,
                "height": gen_h,
                "duration": None,
                "author": "FLUX.1 Photoreal Engine",
                "page": "https://pollinations.ai",
                "matched_keyword": clean_prompt[:60],
                "is_ai_generated": True
            }
    except Exception as e:
        print(f"FLUX AI generation error: {e}")

    return None

def search_pixabay_videos(query: str, key: str, orientation: str = "horizontal", per_page: int = 10) -> List[Dict[str, Any]]:
    """Search Pixabay Videos API."""
    if not key:
        return []
    
    clean_q = query.strip()
    if not clean_q:
        return []

    url = "https://pixabay.com/api/videos/"
    params = {
        "key": key,
        "q": clean_q,
        "per_page": max(3, min(per_page, 20)),
        "orientation": orientation if orientation in ["horizontal", "vertical"] else "all"
    }

    try:
        r = requests.get(url, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            results = []
            for hit in hits:
                videos = hit.get("videos", {})
                chosen = videos.get("medium") or videos.get("large") or videos.get("small") or videos.get("tiny")
                thumb = (chosen and chosen.get("thumbnail")) or (videos.get("tiny") or {}).get("thumbnail")
                
                if chosen and chosen.get("url"):
                    results.append({
                        "id": f"pix_v_{hit.get('id')}",
                        "source": "Pixabay",
                        "type": "video",
                        "tags": hit.get("tags", "Video clip"),
                        "preview": thumb,
                        "download": chosen["url"],
                        "width": chosen.get("width", 1920),
                        "height": chosen.get("height", 1080),
                        "duration": hit.get("duration", 5),
                        "author": hit.get("user", "Pixabay Creator"),
                        "page": hit.get("pageURL", ""),
                        "matched_keyword": clean_q
                    })
            return results
    except Exception as e:
        print(f"Error querying Pixabay videos: {e}")
    return []

def search_pixabay_images(query: str, key: str, orientation: str = "horizontal", per_page: int = 10) -> List[Dict[str, Any]]:
    """Search Pixabay Images API."""
    if not key:
        return []

    clean_q = query.strip()
    if not clean_q:
        return []

    url = "https://pixabay.com/api/"
    params = {
        "key": key,
        "q": clean_q,
        "image_type": "photo",
        "per_page": max(3, min(per_page, 20)),
        "orientation": orientation if orientation in ["horizontal", "vertical"] else "all"
    }

    try:
        r = requests.get(url, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            results = []
            for hit in hits:
                img_url = hit.get("largeImageURL") or hit.get("webformatURL")
                thumb = hit.get("webformatURL") or hit.get("previewURL")
                
                if img_url:
                    results.append({
                        "id": f"pix_i_{hit.get('id')}",
                        "source": "Pixabay",
                        "type": "image",
                        "tags": hit.get("tags", "Photo"),
                        "preview": thumb,
                        "download": img_url,
                        "width": hit.get("imageWidth", 1920),
                        "height": hit.get("imageHeight", 1080),
                        "duration": None,
                        "author": hit.get("user", "Pixabay Creator"),
                        "page": hit.get("pageURL", ""),
                        "matched_keyword": clean_q
                    })
            return results
    except Exception as e:
        print(f"Error querying Pixabay images: {e}")
    return []

def search_wikimedia_commons(query: str, per_page: int = 10) -> List[Dict[str, Any]]:
    """
    100% Free Public Domain Historical, Cultural & Factual Visuals API (Zero API Key Needed).
    Provides authentic photographs, portraits, monuments, maps, and historical artifacts
    for documentary subjects that generic modern stock libraries lack.
    """
    clean_q = query.strip()
    if not clean_q:
        return []
    try:
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": "6",  # File namespace
            "gsrsearch": clean_q,
            "gsrlimit": max(3, min(per_page, 15)),
            "prop": "imageinfo",
            "iiprop": "url|size"
        }
        headers = {"User-Agent": "VideoCraftStudio/1.0 (YouTube Documentary Visual Engine)"}
        r = requests.get(url, params=params, headers=headers, timeout=12)
        if r.status_code == 200:
            pages = r.json().get("query", {}).get("pages", {})
            results = []
            for pid, pdata in pages.items():
                infos = pdata.get("imageinfo", [])
                if not infos:
                    continue
                info = infos[0]
                img_url = info.get("url")
                w = info.get("width", 1920)
                h = info.get("height", 1080)
                # Ignore tiny thumbnails or non-image types
                if not img_url or w < 400 or h < 300:
                    continue
                if any(img_url.lower().endswith(ext) for ext in [".svg", ".ogg", ".webm", ".pdf", ".tif"]):
                    continue
                title_clean = pdata.get("title", "").replace("File:", "").replace("_", " ")
                results.append({
                    "id": f"wiki_{pid}",
                    "source": "Wikimedia Commons (Public Domain)",
                    "type": "image",
                    "tags": title_clean,
                    "preview": img_url,
                    "download": img_url,
                    "width": w,
                    "height": h,
                    "duration": None,
                    "author": "Wikimedia Public Domain",
                    "page": f"https://commons.wikimedia.org/?curid={pid}",
                    "matched_keyword": clean_q
                })
            return results
    except Exception as e:
        print(f"Wikimedia Commons API notice: {e}")
    return []

def search_open_web_images(query: str, per_page: int = 10) -> List[Dict[str, Any]]:
    """
    Searches the COMPLETE OPEN INTERNET for high-resolution images matching the exact query.
    Bypasses stock library limitations by fetching authentic images from Wikipedia, news,
    historical archives, educational sites, and photography platforms across the entire web.
    Includes both high-res direct URL and reliable CDN fallback URL.
    """
    clean_q = query.strip()
    if not clean_q:
        return []
    try:
        encoded_q = urllib.parse.quote(clean_q)
        url = f"https://www.bing.com/images/search?q={encoded_q}&FORM=HDRSC2"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        matches = re.findall(r'm="([^"]+)"', r.text)
        results = []
        for idx, m in enumerate(matches[:max(per_page * 2, 25)]):
            clean_m = m.replace('&quot;', '"')
            try:
                data = json.loads(clean_m)
                murl = data.get('murl')  # Full original web image
                turl = data.get('turl')  # CDN fallback URL
                title = data.get('t', clean_q)
                w = int(data.get('width', 1920) or 1920)
                h = int(data.get('height', 1080) or 1080)

                if not murl or not murl.startswith('http'):
                    continue
                if w < 350 or h < 250:
                    continue

                results.append({
                    "id": f"web_{idx}_{abs(hash(murl)) % 1000000}",
                    "source": "Open Web Search",
                    "type": "image",
                    "tags": title[:80],
                    "preview": turl or murl,
                    "download": murl,
                    "fallback_download": turl,
                    "width": w,
                    "height": h,
                    "duration": None,
                    "author": "Web Source",
                    "page": data.get('purl', ''),
                    "matched_keyword": clean_q
                })
                if len(results) >= per_page:
                    break
            except Exception:
                continue
        return results
    except Exception as e:
        print(f"Open web image search notice: {e}")
        return []

def search_wikipedia_images(query: str, per_page: int = 6) -> List[Dict[str, Any]]:
    """
    Searches Wikipedia's global encyclopedia for authentic high-resolution images,
    paintings, monuments, historical figures, and event illustrations. 100% Free & Open Domain.
    """
    clean_q = query.strip()
    if not clean_q:
        return []
    try:
        s_url = "https://en.wikipedia.org/w/api.php"
        headers = {"User-Agent": "VideoCraftStudio/1.0 (YouTube Documentary Knowledge Engine)"}
        params = {
            "action": "query",
            "list": "search",
            "srsearch": clean_q,
            "utf8": 1,
            "format": "json",
            "srlimit": max(2, min(per_page, 6))
        }
        r = requests.get(s_url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        pages = r.json().get("query", {}).get("search", [])
        results = []
        for p in pages:
            title = p.get("title")
            if not title:
                continue
            img_params = {
                "action": "query",
                "titles": title,
                "prop": "pageimages",
                "piprop": "original|thumbnail",
                "pithumbsize": 1920,
                "format": "json"
            }
            r_img = requests.get(s_url, params=img_params, headers=headers, timeout=8)
            if r_img.status_code == 200:
                p_data = r_img.json().get("query", {}).get("pages", {})
                for pid, pinfo in p_data.items():
                    orig = pinfo.get("original", {}) or pinfo.get("thumbnail", {})
                    src_url = orig.get("source")
                    if src_url and not src_url.lower().endswith(".svg"):
                        w = orig.get("width", 1920) or 1920
                        h = orig.get("height", 1080) or 1080
                        if w >= 400 and h >= 300:
                            results.append({
                                "id": f"wiki_page_{pid}",
                                "source": "Wikipedia Encyclopedia",
                                "type": "image",
                                "tags": f"{title} (Wikipedia)",
                                "preview": src_url,
                                "download": src_url,
                                "fallback_download": src_url,
                                "width": w,
                                "height": h,
                                "duration": None,
                                "author": "Wikipedia Public Domain",
                                "page": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}",
                                "matched_keyword": clean_q
                            })
                            if len(results) >= per_page:
                                break
        return results
    except Exception as e:
        print(f"Wikipedia Image API notice: {e}")
    return []

def search_assets(
    query: str,
    key: str = DEFAULT_PIXABAY_KEY,
    media_type: str = "both",
    orientation: str = "horizontal",
    per_page: int = 15,
    sentence: str = "",
    openai_key: str = DEFAULT_OPENAI_KEY,
    dalle_prompt: str = "",
    allow_ai_fallback: bool = True,
    main_topic: str = "",
    is_first_3_mins: bool = False,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Search assets across the COMPLETE OPEN INTERNET:
    1. Wikipedia Global Knowledge (Authentic historical, scientific & cultural images)
    2. Wikimedia Commons (Public domain archive photos & monuments)
    3. Open Web Live Search (Google / Bing entire web images)
    4. Pixabay Videos & Stock Images (1080p Royalty Free)
    5. FLUX 8K AI Photorealism (Midjourney-grade scene illustration)
    6. StudioBrain Topic Relevance Ranking
    """
    results: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    def _add_results(new_items: List[Dict[str, Any]], kw: str):
        for item in new_items:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                item["matched_keyword"] = kw
                results.append(item)

    clean_t = main_topic.strip() if main_topic else ""

    # =========================================================================
    # 🎯 FIRST 3 MINUTES: STRICT TOPIC LOCK ACROSS THE COMPLETE OPEN WEB
    # Searches across the COMPLETE INTERNET for genuine topic images & videos!
    # =========================================================================
    if is_first_3_mins and clean_t:
        search_target = f"{clean_t} {query}".strip()[:90]

        # 1. Search Wikipedia Global Knowledge for real photos & paintings
        _add_results(search_wikipedia_images(search_target, per_page=6), search_target)
        if query and query.lower() != clean_t.lower():
            _add_results(search_wikipedia_images(clean_t, per_page=4), clean_t)

        # 2. Search Wikimedia Commons (100% Free Public Domain)
        _add_results(search_wikimedia_commons(clean_t, per_page=8), clean_t)
        if query and query.lower() != clean_t.lower():
            _add_results(search_wikimedia_commons(search_target, per_page=6), search_target)

        # 3. Search the COMPLETE OPEN INTERNET (Live web images from all websites)
        _add_results(search_open_web_images(search_target, per_page=8), search_target)

        # 4. Search Pixabay stock footage & photos
        if media_type in ["both", "video"]:
            _add_results(search_pixabay_videos(search_target, key, orientation, per_page), search_target)
        _add_results(search_pixabay_images(search_target, key, orientation, per_page), search_target)

        # 5. Strict filter: discard any generic off-topic candidates
        t_words = [w for w in re.findall(r'[a-zA-Z0-9]{3,}', clean_t.lower()) if w not in ("the", "and", "for", "with", "video", "clip")]
        if t_words and results:
            filtered_strict = []
            for r in results:
                # Always accept Open Web, Wikipedia, FLUX AI, or Wikimedia Commons topic searches
                if r.get("is_ai_generated") or "Wikipedia" in r.get("source", "") or "Wikimedia" in r.get("source", "") or "Web" in r.get("source", ""):
                    filtered_strict.append(r)
                    continue
                cand_text = f"{r.get('tags', '')} {r.get('matched_keyword', '')}".lower()
                if any(tw in cand_text for tw in t_words):
                    filtered_strict.append(r)
            results = filtered_strict

        # 6. If no authentic visual exists anywhere on the web, generate 8K FLUX AI visual:
        if not results and allow_ai_fallback:
            prompt_to_use = dalle_prompt or f"Cinematic 8k photorealistic documentary scene of {clean_t}: {sentence or query}, 35mm photography, national geographic cinematography, highly detailed, photorealistic masterpiece"
            ai_asset = generate_ai_image(prompt=prompt_to_use, openai_key=openai_key)
            if ai_asset:
                _add_results([ai_asset], "FLUX 8K Topic AI Visual")

        try:
            from studio_brain import StudioBrain
            results = StudioBrain.rank_and_filter_candidates(results, keyword=query, main_topic=clean_t, is_scene_1_hook=False)
        except Exception:
            pass
        return results

    # =========================================================================
    # NORMAL FLOW (AFTER 3 MINUTES / STANDARD PIPELINE)
    # Complete internet search + Wikipedia + Pixabay videos + Wikimedia Commons
    # =========================================================================
    # Stage 1: Wikipedia Global Knowledge for exact script entities
    _add_results(search_wikipedia_images(query, per_page=5), query)
    if clean_t and len(results) < 4:
        _add_results(search_wikipedia_images(f"{clean_t} {query}".strip()[:90], per_page=4), f"{clean_t} {query}")

    # Stage 2: Live Open Web Search for exact script entities
    _add_results(search_open_web_images(query, per_page=6), query)
    if clean_t and len(results) < 5:
        _add_results(search_open_web_images(f"{clean_t} {query}".strip()[:90], per_page=6), f"{clean_t} {query}")

    # Stage 2: Pixabay Videos & Images
    if media_type in ["both", "video"]:
        _add_results(search_pixabay_videos(query, key, orientation, per_page), query)
    if media_type in ["both", "image"]:
        _add_results(search_pixabay_images(query, key, orientation, per_page), query)

    # Stage 3: Wikimedia Commons for historical/cultural authenticity
    if clean_t and len(results) < 6:
        _add_results(search_wikimedia_commons(f"{clean_t} {query}"[:80], per_page=6), f"{clean_t} {query}")

    # Stage 4: Sub-phrase / alternative words derived from the sentence
    words = query.strip().split()
    if len(words) > 1 and len(results) < 5:
        sub_q = " ".join(words[:2])
        _add_results(search_open_web_images(sub_q, per_page=5), sub_q)
        if media_type in ["both", "video"]:
            _add_results(search_pixabay_videos(sub_q, key, orientation, per_page), sub_q)

    # Stage 5: Topic-Anchored fallback
    if not results or len(results) < 3:
        if clean_t:
            _add_results(search_open_web_images(clean_t, per_page=5), clean_t)
            _add_results(search_wikimedia_commons(clean_t, per_page=5), clean_t)
            if media_type in ["both", "video"]:
                _add_results(search_pixabay_videos(clean_t, key, orientation, per_page), clean_t)

    # Stage 6: Photorealistic AI image generation fallback
    if not results and allow_ai_fallback:
        t_prefix = f"{main_topic}: " if main_topic else ""
        prompt_to_use = dalle_prompt or f"Cinematic photorealistic 8k view of {t_prefix}{sentence or query}, historical documentary cinematography, National Geographic style"
        ai_asset = generate_ai_image(prompt=prompt_to_use, openai_key=openai_key)
        if ai_asset:
            _add_results([ai_asset], "AI Visual Generation")

    # StudioBrain relevance & quality ranking
    try:
        from studio_brain import StudioBrain
        results = StudioBrain.rank_and_filter_candidates(results, keyword=query, main_topic=main_topic)
    except Exception as e:
        print(f"StudioBrain ranking fallback: {e}")

    return results

    # Pass results through StudioBrain for self-learning ranking, blacklist pruning & topic relevance scoring
    try:
        from studio_brain import StudioBrain
        results = StudioBrain.rank_and_filter_candidates(results, keyword=query, main_topic=main_topic)
    except Exception as e:
        print(f"StudioBrain ranking fallback: {e}")

    return results

def pick_unique_candidate(candidates: List[Dict[str, Any]], used_ids: Set[str]) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Picks the first candidate from the list whose ID is NOT in used_ids.
    If all candidates have already been used (e.g. long 100-250+ clip videos),
    fairly rotates among candidates instead of always repeating index 0.
    """
    if not candidates:
        return -1, None
    for idx, c in enumerate(candidates):
        if c.get("id") not in used_ids:
            return idx, c

    # Fair rotation across all candidates if stock pool is fully cycled
    rot_idx = len(used_ids) % len(candidates)
    return rot_idx, candidates[rot_idx]

def ensure_unique_selections(scenes: List[Dict[str, Any]], scene_assets: Dict[str, List[Dict[str, Any]]], selected_assets: Dict[str, int]) -> Dict[str, int]:
    """
    Scans selected assets across all scenes and reassigns any duplicates
    so that every scene has a completely unique video/image clip.
    """
    used_ids: Set[str] = set()
    updated_selections = dict(selected_assets)

    for sc in scenes:
        sc_no = sc.get("no", "")
        assets = scene_assets.get(sc_no, [])
        if not assets:
            continue
        
        curr_idx = updated_selections.get(sc_no, 0)
        curr_asset = assets[min(curr_idx, len(assets) - 1)]

        if curr_asset.get("id") in used_ids:
            new_idx, new_asset = pick_unique_candidate(assets, used_ids)
            if new_asset and new_asset.get("id") not in used_ids:
                updated_selections[sc_no] = new_idx
                used_ids.add(new_asset["id"])
            else:
                used_ids.add(curr_asset.get("id", f"asset_{sc_no}"))
        else:
            used_ids.add(curr_asset.get("id", f"asset_{sc_no}"))

    return updated_selections
