import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any

APP_DIR = Path(__file__).parent.resolve()
DOWNLOADS_DIR = APP_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_JOB_FILE = DOWNLOADS_DIR / "active_render_job.json"

def prevent_windows_sleep():
    """Prevents Windows system from entering sleep mode while rendering video."""
    try:
        import ctypes
        # ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception as e:
        print(f"prevent_windows_sleep error: {e}")

def allow_windows_sleep():
    """Restores normal Windows power saving behavior after render completes."""
    try:
        import ctypes
        # ES_CONTINUOUS (0x80000000)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    except Exception as e:
        print(f"allow_windows_sleep error: {e}")

class BackgroundRenderManager:
    """
    Server-Side Detached Background Job Manager:
    Runs video generation in an independent OS daemon thread completely decoupled from the browser WebSocket.
    Guarantees:
    1. If the user locks mobile screen, minimizes browser, or switches apps, rendering CONTINUES 100%.
    2. Prevents Windows PC from sleeping during render.
    3. Persists live progress and status to active_render_job.json.
    4. Auto-restores results when the user reopens the app.
    """
    _lock = threading.Lock()
    _active_thread: Optional[threading.Thread] = None
    _cancel_event = threading.Event()

    @classmethod
    def get_job(cls) -> Optional[Dict[str, Any]]:
        """Reads active job state safely from disk."""
        try:
            if ACTIVE_JOB_FILE.exists():
                with open(ACTIVE_JOB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data.get("job_id"):
                        return data
        except Exception as e:
            print(f"Error reading active job file: {e}")
    @classmethod
    def is_running(cls) -> bool:
        """Checks if a background job is actively running."""
        job = cls.get_job()
        if not job or job.get("status") != "running":
            return False
        if cls._active_thread is not None:
            return cls._active_thread.is_alive()
        # If server restarted or process crashed and was running > 10 mins without update
        if time.time() - job.get("updated_at", 0) > 600:
            return False
        return True

    @classmethod
    def update_job(
        cls,
        job_id: str,
        progress: Optional[float] = None,
        status_text: Optional[str] = None,
        status: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        """Atomically updates job status on disk."""
        with cls._lock:
            job = cls.get_job() or {"job_id": job_id}
            job["job_id"] = job_id
            if progress is not None:
                job["progress"] = round(float(progress), 3)
            if status_text is not None:
                job["status_text"] = status_text
            if status is not None:
                job["status"] = status
            if result is not None:
                job["result"] = result
            if error_message is not None:
                job["error_message"] = error_message
            job["updated_at"] = time.time()

            try:
                temp_f = ACTIVE_JOB_FILE.with_suffix(".tmp")
                with open(temp_f, "w", encoding="utf-8") as f:
                    json.dump(job, f, indent=2)
                temp_f.replace(ACTIVE_JOB_FILE)
            except Exception as e:
                print(f"Error writing job status: {e}")

    @classmethod
    def start_job(cls, params: Dict[str, Any], pipeline_fn) -> tuple[bool, str]:
        """Launches a detached background video generation job."""
        with cls._lock:
            # Check if active thread is genuinely still executing
            if cls._active_thread and cls._active_thread.is_alive():
                curr = cls.get_job()
                if curr and curr.get("status") == "running":
                    return False, "A video is already generating in the background."

            job_id = time.strftime('%Y%m%d_%H%M%S')
            cls._cancel_event.clear()
            prevent_windows_sleep()

            job_data = {
                "job_id": job_id,
                "status": "running",
                "progress": 0.05,
                "status_text": "Starting background video pipeline...",
                "started_at": time.time(),
                "updated_at": time.time(),
                "topic": params.get("main_topic") or "Video",
                "script_snippet": params.get("script_text", "")[:120],
                "result": None,
                "error_message": None
            }
            try:
                with open(ACTIVE_JOB_FILE, "w", encoding="utf-8") as f:
                    json.dump(job_data, f, indent=2)
            except Exception as e:
                print(f"Error initializing job file: {e}")

            def _worker():
                def _callback(pct, text, state="info"):
                    cls.update_job(job_id, progress=pct, status_text=text)

                try:
                    res = pipeline_fn(
                        script_text=params.get("script_text", ""),
                        main_topic=params.get("main_topic", ""),
                        media_pref=params.get("media_pref", "both"),
                        speed_mult=params.get("speed_mult", 1.25),
                        tts_rate=params.get("tts_rate", "+25%"),
                        voice_name=params.get("voice_name", "hi-IN-MadhurNeural"),
                        do_voice=params.get("do_voice", True),
                        pb_key=params.get("pb_key", ""),
                        ai_key=params.get("ai_key", ""),
                        tw=params.get("tw", 1920),
                        th=params.get("th", 1080),
                        orient=params.get("orient", "horizontal"),
                        fit_m=params.get("fit_m", "smart_crop"),
                        kb_style=params.get("kb_style", "auto"),
                        b_badge=params.get("b_badge", True),
                        b_style=params.get("b_style", "Floating Glass Pill"),
                        b_pos=params.get("b_pos", "Top-Left"),
                        b_subs=params.get("b_subs", True),
                        sub_style=params.get("sub_style", "Creator Viral"),
                        p_buffer=params.get("p_buffer", 0.0),
                        bgm_k=params.get("bgm_k", "dark_mystery"),
                        custom_bgm=params.get("custom_bgm"),
                        bgm_vol=params.get("bgm_vol", 0.12),
                        niche_k=params.get("niche_k", "history"),
                        status_container=None,
                        render_bar=None,
                        existing_scenes=params.get("existing_scenes"),
                        existing_scene_assets=params.get("existing_scene_assets"),
                        existing_selected_assets=params.get("existing_selected_assets"),
                        progress_callback=_callback,
                        cancel_event=cls._cancel_event
                    )

                    if res and res.get("merged_video"):
                        cls.update_job(
                            job_id,
                            progress=1.0,
                            status_text="🎉 Video generation complete!",
                            status="completed",
                            result=res
                        )
                    elif cls._cancel_event.is_set():
                        cls.update_job(
                            job_id,
                            status="cancelled",
                            status_text="⚠️ Video generation cancelled by user."
                        )
                    else:
                        cls.update_job(
                            job_id,
                            status="error",
                            error_message="Video generation pipeline failed to produce verified output video."
                        )
                except Exception as ex:
                    print(f"Background worker fatal exception: {ex}")
                    cls.update_job(job_id, status="error", error_message=str(ex))
                finally:
                    allow_windows_sleep()

            cls._active_thread = threading.Thread(
                target=_worker,
                daemon=True,
                name=f"VideoRenderThread_{job_id}"
            )
            cls._active_thread.start()
            return True, job_id

    @classmethod
    def cancel_job(cls):
        """Signals active background render to abort safely."""
        with cls._lock:
            cls._cancel_event.set()
            job = cls.get_job()
            if job:
                cls.update_job(
                    job["job_id"],
                    status="cancelled",
                    status_text="Aborting render..."
                )
            allow_windows_sleep()

    @classmethod
    def clear_job(cls):
        """Clears completed or dismissed job file."""
        with cls._lock:
            try:
                ACTIVE_JOB_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            allow_windows_sleep()
