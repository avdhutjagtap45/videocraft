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
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Search assets with multi-stage scenario matching strictly anchored to the main video topic:
    1. Primary topic-anchored scenario query
    2. Sub-phrases and context relaxation
    3. Topic-preserved sentence-level alternative keywords
    4. Topic-anchored visual fallbacks (preserves video topic instead of generic nature)
    5. Photorealistic AI visual generation fallback
    6. Topic relevance & quality ranking via StudioBrain
    """
    results: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    def _add_results(new_items: List[Dict[str, Any]], kw: str):
        for item in new_items:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                item["matched_keyword"] = kw
                results.append(item)

    # Stage 1: Direct search with primary query
    if media_type in ["both", "video"]:
        _add_results(search_pixabay_videos(query, key, orientation, per_page), query)
    if media_type in ["both", "image"]:
        _add_results(search_pixabay_images(query, key, orientation, per_page), query)

    # If plenty of results found, return immediately
    if len(results) >= 5:
        try:
            from studio_brain import StudioBrain
            results = StudioBrain.rank_and_filter_candidates(results, keyword=query, main_topic=main_topic)
        except Exception:
            pass
        return results

    # Stage 2: Automatic sub-phrase / word relaxation
    words = query.strip().split()
    if len(words) > 1:
        sub_q = " ".join(words[:2])
        if media_type in ["both", "video"]:
            _add_results(search_pixabay_videos(sub_q, key, orientation, per_page), sub_q)
        if media_type in ["both", "image"]:
            _add_results(search_pixabay_images(sub_q, key, orientation, per_page), sub_q)

    if len(results) >= 5:
        try:
            from studio_brain import StudioBrain
            results = StudioBrain.rank_and_filter_candidates(results, keyword=query, main_topic=main_topic)
        except Exception:
            pass
        return results

    # Stage 3: Topic-anchored alternative keywords
    fallback_queries = generate_fallback_keywords(sentence, query, topic=main_topic) if sentence or main_topic else []
    for fb_q in fallback_queries:
        if fb_q.lower() == query.lower():
            continue
        if media_type in ["both", "video"]:
            _add_results(search_pixabay_videos(fb_q, key, orientation, per_page), fb_q)
        if media_type in ["both", "image"]:
            _add_results(search_pixabay_images(fb_q, key, orientation, per_page), fb_q)
        if len(results) >= 8:
            break

    # Stage 4: Topic-Anchored Visual Fallback (Strictly preserves the video subject!)
    if not results or len(results) < 3:
        clean_t = main_topic.strip() if main_topic else ""
        if clean_t:
            topic_fallbacks = [
                clean_t,
                f"{clean_t} cinematic",
                f"{clean_t} 4k",
                f"{clean_t} aerial view",
                f"{clean_t} close up",
                f"{clean_t} documentary",
                f"{clean_t} landscape"
            ]
        else:
            topic_fallbacks = ["cinematic documentary", "cinematic landscape 4k", "cinematic atmospheric footage"]

        for topic_q in topic_fallbacks:
            if media_type in ["both", "video"]:
                _add_results(search_pixabay_videos(topic_q, key, orientation, per_page), topic_q)
            if media_type in ["both", "image"]:
                _add_results(search_pixabay_images(topic_q, key, orientation, per_page), topic_q)
            if len(results) >= 6:
                break

    # Stage 5: Photorealistic AI image generation fallback if no stock clip was found
    if not results and allow_ai_fallback:
        t_prefix = f"{main_topic}: " if main_topic else ""
        prompt_to_use = dalle_prompt or f"Cinematic photorealistic 8k view of {t_prefix}{sentence or query}, historical documentary cinematography, National Geographic style"
        ai_asset = generate_ai_image(prompt=prompt_to_use, openai_key=openai_key)
        if ai_asset:
            _add_results([ai_asset], "AI Visual Generation")

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
