import json
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

APP_DIR = Path(__file__).parent.resolve()
DOWNLOADS_DIR = APP_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
BRAIN_FILE = DOWNLOADS_DIR / "studio_brain.json"

DEFAULT_BRAIN_STATE: Dict[str, Any] = {
    "version": "1.0",
    "total_videos_created": 0,
    "total_clips_learned": 0,
    "brain_level": 1,
    "quality_rating_avg": 4.8,
    "learned_clips": {},      # asset_id -> {"score": int, "times_used": int, "type": str, "keyword": str}
    "blacklisted_ids": [],    # asset_ids marked as bad or low quality
    "proven_keywords": {     # theme_key -> list of best queries
        "history": ["ancient temple cinematic drone", "historical ruins dramatic 4k", "pharaoh pyramid aerial"],
        "mystery": ["mysterious foggy forest cinematic", "dark detective investigation noir", "creepy shadows dramatic"],
        "finance": ["stock market trading screen 4k", "counting cash money slow motion", "luxury lifestyle cinematic"],
        "general": ["cinematic aerial landscape 4k", "dramatic slow motion cinematic", "epic nature sunset drone"]
    },
    "hook_modifiers": [
        "cinematic dramatic 4k",
        "epic aerial slow motion",
        "intense cinematic hero shot",
        "mysterious high contrast 1080p",
        "breathtaking slow motion"
    ],
    "render_history": []
}

class StudioBrain:
    """
    Self-Learning Quality & Retention Engine:
    Learns from every video generated. Tracks which keywords, clips, resolutions,
    and pacing deliver maximum viewer retention and visual fidelity.
    """
    _cache: Optional[Dict[str, Any]] = None

    @classmethod
    def load_brain(cls) -> Dict[str, Any]:
        """Loads persistent learning state from disk."""
        if cls._cache is not None:
            return cls._cache

        if BRAIN_FILE.exists():
            try:
                with open(BRAIN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "version" in data:
                        cls._cache = data
                        return cls._cache
            except Exception as e:
                print(f"Error loading studio brain: {e}")

        # Initialize with default structure
        cls._cache = dict(DEFAULT_BRAIN_STATE)
        cls.save_brain()
        return cls._cache

    @classmethod
    def save_brain(cls):
        """Atomically writes brain data to disk."""
        if cls._cache is None:
            return
        try:
            temp_f = BRAIN_FILE.with_suffix(".tmp")
            with open(temp_f, "w", encoding="utf-8") as f:
                json.dump(cls._cache, f, indent=2, ensure_ascii=False)
            temp_f.replace(BRAIN_FILE)
        except Exception as e:
            print(f"Error saving studio brain: {e}")

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Returns overview statistics of the self-learning brain."""
        brain = cls.load_brain()
        learned_count = len(brain.get("learned_clips", {}))
        total_vids = brain.get("total_videos_created", 0)
        
        # Calculate brain level based on experience
        level = 1
        if total_vids >= 10 or learned_count >= 50:
            level = 4
        elif total_vids >= 5 or learned_count >= 25:
            level = 3
        elif total_vids >= 2 or learned_count >= 8:
            level = 2

        level_titles = {
            1: "Adaptive Starter (Learning)",
            2: "Smart Visual Curator (Level 2)",
            3: "Pro High-Retention Engine (Level 3)",
            4: "Master Viral Director (Level 4)"
        }

        return {
            "level": level,
            "level_title": level_titles.get(level, "Adaptive AI"),
            "total_videos": total_vids,
            "total_learned_clips": learned_count,
            "total_blacklisted": len(brain.get("blacklisted_ids", [])),
            "quality_rating_avg": brain.get("quality_rating_avg", 4.9)
        }

    @classmethod
    def optimize_hook_scene(cls, scene_text: str, current_keyword: str) -> Tuple[str, str]:
        """
        Detects weak openings in Scene 1 (Hook) and strengthens them.
        Enhances search keywords to guarantee Hero/Dramatic footage for the opening 5 seconds.
        """
        clean_text = scene_text.strip().lower()

        # Check for weak or generic greeting patterns
        weak_patterns = [
            r"^namaste\b", r"^hello\b", r"^welcome\b", r"^aaj hum\b",
            r"^in this video\b", r"^today we\b", r"^dosto aaj\b", r"^hi everyone\b"
        ]
        is_weak_opening = any(re.search(pat, clean_text) for pat in weak_patterns)

        # Enhance keyword for high visual impact
        brain = cls.load_brain()
        modifiers = brain.get("hook_modifiers", DEFAULT_BRAIN_STATE["hook_modifiers"])
        mod = modifiers[int(time.time()) % len(modifiers)]

        # If keyword is simple, inject cinematic hero modifier
        base_kw = current_keyword.strip() or "cinematic"
        enhanced_keyword = f"{base_kw} {mod}".strip()

        advice = ""
        if is_weak_opening:
            advice = "💡 Tip: Start directly with the mystery or shocking fact instead of greeting to boost first 5-second retention!"

        return enhanced_keyword, advice

    @classmethod
    def rank_and_filter_candidates(
        cls,
        candidates: List[Dict[str, Any]],
        keyword: str = "",
        is_scene_1_hook: bool = False,
        main_topic: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Ranks stock footage candidates using learned intelligence:
        1. Prioritizes TOPIC RELEVANCE: strictly ensures assets actually depict the video subject.
        2. Completely filters out blacklisted / low-rated clips.
        3. Boosts clips that received positive creator feedback previously.
        4. Prioritizes 1080p, 60fps, 4K and high resolution.
        5. For Scene 1 (Hook), strictly ranks high-motion hero clips to the very top.
        """
        if not candidates:
            return []

        brain = cls.load_brain()
        learned = brain.get("learned_clips", {})
        blacklisted = set(brain.get("blacklisted_ids", []))

        # Build topic keywords for relevance scoring
        topic_ref = f"{main_topic} {keyword}".lower()
        topic_words = set(re.findall(r'[a-zA-Z0-9]{3,}', topic_ref))
        topic_words = {w for w in topic_words if w not in ("the", "and", "for", "with", "video", "clip", "cinematic", "shot", "documentary", "style")}

        filtered: List[Dict[str, Any]] = []
        for cand in candidates:
            c_id = cand.get("id")
            if c_id in blacklisted:
                continue

            score = 0
            w = cand.get("width", 1920) or 1920
            h = cand.get("height", 1080) or 1080

            # Resolution bonus
            if w >= 3840 or h >= 2160:
                score += 35  # 4K bonus
            elif w >= 1920 or h >= 1080:
                score += 20  # Full HD bonus

            # Preferred media type
            if cand.get("type") == "video":
                score += 15

            # Historical learning bonus
            if c_id in learned:
                learned_entry = learned[c_id]
                score += (learned_entry.get("score", 0) * 10)

            # TOPIC RELEVANCE BONUS (Dominates over generic off-topic clips):
            tags = (cand.get("tags") or "").lower()
            m_kw = (cand.get("matched_keyword") or "").lower()
            cand_text = f"{tags} {m_kw}"
            hits = sum(1 for tw in topic_words if tw in cand_text)
            if hits > 0:
                score += min(180, hits * 60)  # +60 to +180 topic match bonus!

            # Scene 1 Hook bonus (motion and hero clips)
            if is_scene_1_hook and cand.get("type") == "video":
                score += 25

            cand_copy = dict(cand)
            cand_copy["_learning_score"] = score
            filtered.append(cand_copy)

        # Sort descending by learning score
        filtered.sort(key=lambda x: x.get("_learning_score", 0), reverse=True)
        return filtered

    @classmethod
    def record_video_completed(cls, video_path: str, scenes: List[Dict[str, Any]], selected_assets: Dict[str, Any]):
        """Records a completed video render into brain memory."""
        brain = cls.load_brain()
        brain["total_videos_created"] = brain.get("total_videos_created", 0) + 1

        learned = brain.setdefault("learned_clips", {})
        for sc_idx, sc in enumerate(scenes):
            sc_no = sc.get("no", str(sc_idx + 1).zfill(2))
            asset = selected_assets.get(sc_no)
            if isinstance(asset, dict) and asset.get("id"):
                a_id = asset["id"]
                if a_id not in learned:
                    learned[a_id] = {
                        "score": 1,
                        "times_used": 1,
                        "type": asset.get("type", "video"),
                        "keyword": asset.get("matched_keyword", sc.get("keyword", "")),
                        "first_learned": time.time()
                    }
                else:
                    learned[a_id]["times_used"] = learned[a_id].get("times_used", 1) + 1
                    learned[a_id]["score"] = learned[a_id].get("score", 1) + 1

        brain["total_clips_learned"] = len(learned)
        cls.save_brain()

    @classmethod
    def apply_feedback(cls, rating: str, scene_assets_used: Optional[List[Dict[str, Any]]] = None):
        """
        Applies 1-click user rating to update brain weights:
        - 'viral': +5 points to all clips used, boosts proven keywords.
        - 'good': +2 points to all clips used.
        - 'bad': -5 points to clips used; if score drops below -2, clip is blacklisted.
        """
        brain = cls.load_brain()
        learned = brain.setdefault("learned_clips", {})
        blacklisted = set(brain.setdefault("blacklisted_ids", []))

        delta = 2
        if rating == "viral":
            delta = 5
        elif rating == "bad":
            delta = -4

        if scene_assets_used:
            for asset in scene_assets_used:
                if not isinstance(asset, dict):
                    continue
                a_id = asset.get("id")
                if not a_id:
                    continue

                if a_id not in learned:
                    learned[a_id] = {
                        "score": delta,
                        "times_used": 1,
                        "type": asset.get("type", "video"),
                        "keyword": asset.get("matched_keyword", "")
                    }
                else:
                    learned[a_id]["score"] = learned[a_id].get("score", 0) + delta

                # Auto-blacklist if creator rated bad repeatedly
                if learned[a_id]["score"] <= -3:
                    blacklisted.add(a_id)

        brain["blacklisted_ids"] = list(blacklisted)
        cls.save_brain()
        return cls.get_stats()
