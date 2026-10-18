"""Central configuration for the YouTube automation pipeline.

All behaviour is driven by environment variables so the same code runs
identically on a laptop, in CI (GitHub Actions), or on a self-hosted runner.
Nothing here costs money — see PLAN.md §3.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = Path(os.environ.get("CONTENT_DIR", REPO_ROOT / "content"))
QUEUE_DIR = CONTENT_DIR / "queue"
PUBLISHED_DIR = CONTENT_DIR / "published"
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", REPO_ROOT / "output"))
ASSET_CACHE_DIR = Path(os.environ.get("ASSET_CACHE_DIR", OUTPUT_DIR / "asset_cache"))


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # --- rendering -------------------------------------------------------
    width: int = int(os.environ.get("VIDEO_WIDTH", "1280"))
    height: int = int(os.environ.get("VIDEO_HEIGHT", "720"))
    fps: int = int(os.environ.get("VIDEO_FPS", "30"))
    # Draft renders can stay 720p; bump to 1080p for final publishes.
    burn_captions: bool = _env_bool("BURN_CAPTIONS", True)
    ken_burns: bool = _env_bool("KEN_BURNS", True)  # disable on very slow CPUs

    # --- narration -------------------------------------------------------
    voice: str = os.environ.get("TTS_VOICE", "en-US-ChristopherNeural")
    tts_rate: str = os.environ.get("TTS_RATE", "+0%")
    words_per_second: float = float(os.environ.get("WORDS_PER_SECOND", "2.5"))

    # --- assets ----------------------------------------------------------
    pexels_api_key: str = os.environ.get("PEXELS_API_KEY", "")
    pixabay_api_key: str = os.environ.get("PIXABAY_API_KEY", "")
    clips_per_scene: int = int(os.environ.get("CLIPS_PER_SCENE", "2"))
    min_clip_seconds: float = float(os.environ.get("MIN_CLIP_SECONDS", "3.0"))
    enable_keyless_sources: bool = _env_bool("ENABLE_KEYLESS_SOURCES", True)

    # --- music (optional, local CC0 files only — never scraped) ----------
    music_dir: Path = Path(os.environ.get("MUSIC_DIR", REPO_ROOT / "assets" / "music"))
    music_enabled: bool = _env_bool("MUSIC_ENABLED", False)
    music_volume: str = os.environ.get("MUSIC_VOLUME", "0.07")

    # --- YouTube upload --------------------------------------------------
    youtube_client_secret: str = os.environ.get("YOUTUBE_CLIENT_SECRET", "")  # JSON string
    youtube_refresh_token: str = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
    auto_publish: bool = _env_bool("AUTO_PUBLISH", False)  # needs audited API project
    default_privacy: str = os.environ.get("DEFAULT_PRIVACY", "private")
    playlist_id: str = os.environ.get("YOUTUBE_PLAYLIST_ID", "")

    # --- safety rails ----------------------------------------------------
    max_longform_per_day: int = int(os.environ.get("MAX_LONGFORM_PER_DAY", "1"))
    dry_run: bool = _env_bool("DRY_RUN", False)

    tags_extra: list[str] = field(default_factory=lambda: [
        "documentary", "explainer", "faceless",
    ])

    def ensure_dirs(self) -> None:
        for d in (OUTPUT_DIR, ASSET_CACHE_DIR, PUBLISHED_DIR):
            d.mkdir(parents=True, exist_ok=True)


CONFIG = Config()
