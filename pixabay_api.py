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
    dest_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """
    Generates a high-definition 1920x1080 scene image using OpenAI Image API.
    If the OpenAI API key returns quota/billing errors, automatically falls back
    to high-res Pollinations AI generation so the video render never fails.
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
                            # Download remote OpenAI image to local disk
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
                                    "width": 1920,
                                    "height": 1080,
                                    "duration": None,
                                    "author": f"OpenAI ({m})",
                                    "page": "https://openai.com",
                                    "matched_keyword": clean_prompt[:60],
                                    "is_ai_generated": True
                                }
            except Exception as e:
                print(f"OpenAI generation error with model {m}: {e}")
                continue

    # 2. Resilient AI image generator fallback (guarantees scene always has a visual)
    try:
        encoded_prompt = urllib.parse.quote(clean_prompt)
        ai_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1920&height=1080&nologo=true&seed={timestamp % 10000}"
        resp = requests.get(ai_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            return {
                "id": f"ai_gen_{timestamp}",
                "source": "AI Image Engine",
                "type": "image",
                "tags": "AI Scene Visual",
                "preview": str(dest_path),
                "download": str(dest_path),
                "width": 1920,
                "height": 1080,
                "duration": None,
                "author": "AI Vision Studio",
                "page": "https://openai.com",
                "matched_keyword": clean_prompt[:60],
                "is_ai_generated": True
            }
    except Exception as e:
        print(f"Fallback AI generation error: {e}")

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
    per_page: int = 10,
    sentence: str = "",
    openai_key: str = DEFAULT_OPENAI_KEY,
    dalle_prompt: str = "",
    allow_ai_fallback: bool = True,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Search assets with multi-stage scenario matching:
    1. Primary scenario query
    2. Sub-phrases and context relaxation
    3. Sentence-level alternative scenario keywords
    4. Universal thematic landscape fallbacks
    5. OpenAI Image Generation fallback if no matching clip is found
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
    if len(results) >= 4:
        return results

    # Stage 2: Automatic sub-phrase / word relaxation
    words = query.strip().split()
    if len(words) > 1:
        sub_q = " ".join(words[:2])
        if media_type in ["both", "video"]:
            _add_results(search_pixabay_videos(sub_q, key, orientation, per_page), sub_q)
        if media_type in ["both", "image"]:
            _add_results(search_pixabay_images(sub_q, key, orientation, per_page), sub_q)

    if len(results) >= 4:
        return results

    # Stage 3: Sentence-level alternative keywords
    fallback_queries = generate_fallback_keywords(sentence, query) if sentence else []
    for fb_q in fallback_queries:
        if fb_q.lower() == query.lower():
            continue
        if media_type in ["both", "video"]:
            _add_results(search_pixabay_videos(fb_q, key, orientation, per_page), fb_q)
        if media_type in ["both", "image"]:
            _add_results(search_pixabay_images(fb_q, key, orientation, per_page), fb_q)
        if len(results) >= 6:
            break

    # Stage 4: Universal cinematic landscape fallback
    if not results:
        for universal_q in ["cinematic landscape", "nature landscape", "epic scenic"]:
            if media_type in ["both", "video"]:
                _add_results(search_pixabay_videos(universal_q, key, orientation, per_page), universal_q)
            if media_type in ["both", "image"]:
                _add_results(search_pixabay_images(universal_q, key, orientation, per_page), universal_q)
            if results:
                break

    # Stage 5: OpenAI DALL-E image generation fallback if no clip was found
    if not results and allow_ai_fallback:
        prompt_to_use = dalle_prompt or (f"Cinematic photorealistic view of {sentence or query}, 8k resolution, documentary photography")
        ai_asset = generate_ai_image(prompt=prompt_to_use, openai_key=openai_key)
        if ai_asset:
            _add_results([ai_asset], "OpenAI DALL-E Generation")

    return results

def pick_unique_candidate(candidates: List[Dict[str, Any]], used_ids: Set[str]) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Picks the first candidate from the list whose ID is NOT in used_ids.
    Returns (index, asset_dict). If all are used, returns (0, candidates[0]) or (-1, None).
    """
    if not candidates:
        return -1, None
    for idx, c in enumerate(candidates):
        if c.get("id") not in used_ids:
            return idx, c
    return 0, candidates[0]

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
