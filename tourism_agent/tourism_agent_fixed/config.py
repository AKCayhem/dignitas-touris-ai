"""
Configuration file for Tourism Agent System.
Modify LOCATION to target any place you want to promote.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── BASE PATHS ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# ─── TARGET LOCATION ──────────────────────────────────────────────────────────
LOCATION = {
    "name": "Tunis",
    "country": "Tunisia",
    "language": "en",
    "hashtags": [
        "#Tunis", "#Tunisia", "#VisitTunisia", "#NorthAfrica",
        "#travel", "#tourism", "#hiddengem", "#travelgram",
        "#wanderlust", "#travelafrica", "#mediterraneanlife"
    ],
    "keywords": [
        "Tunis travel", "Tunisia tourism", "visit Tunis",
        "things to do in Tunis", "Tunis hidden gems"
    ],
    "local_attractions": [
        "Medina of Tunis", "Carthage ruins", "Sidi Bou Said",
        "Bardo Museum", "Tunis beaches"
    ]
}

# ─── VIDEO SETTINGS ───────────────────────────────────────────────────────────
VIDEO_CONFIG = {
    "duration_seconds": 60,
    "fps": 24,
    "resolution": (1080, 1920),   # Vertical 9:16 for TikTok/Reels
    "images_per_video": 12,
    "transition_duration": 0.5,
    "font": "Arial",
    "font_size": 50,
    "text_color": "white",
    "text_shadow": True
}

# ─── PUBLISHING SCHEDULE ──────────────────────────────────────────────────────
SCHEDULE = {
    "post_times": ["09:00", "17:00", "20:00"],
    "timezone": "Africa/Tunis",
    "platforms": ["youtube", "instagram", "facebook", "telegram"]
}

# ─── CONTENT STYLE ────────────────────────────────────────────────────────────
CONTENT_STYLE = {
    "tone": "exciting and inspiring",
    "target_audience": "travel lovers aged 18-45",
    "video_styles": [
        "top 5 hidden gems", "best food spots",
        "day in the life", "historical facts",
        "sunset spots", "local culture"
    ],
    "hook_style": "question or shocking fact in first 3 seconds",
    "call_to_action": "Save this for your next trip!"
}

# ─── API KEYS (loaded from .env) ──────────────────────────────────────────────
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
UNSPLASH_ACCESS_KEY     = os.getenv("UNSPLASH_ACCESS_KEY", "")
PEXELS_API_KEY          = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY         = os.getenv("PIXABAY_API_KEY", "")
ELEVENLABS_API_KEY      = os.getenv("ELEVENLABS_API_KEY", "")
YOUTUBE_CLIENT_ID       = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET   = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN   = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
INSTAGRAM_ACCESS_TOKEN  = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_PAGE_ID       = os.getenv("INSTAGRAM_PAGE_ID", "")
FACEBOOK_ACCESS_TOKEN   = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
FACEBOOK_PAGE_ID        = os.getenv("FACEBOOK_PAGE_ID", "")
TELEGRAM_BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID     = os.getenv("TELEGRAM_CHANNEL_ID", "")
NEWS_API_KEY            = os.getenv("NEWS_API_KEY", "")
REDDIT_CLIENT_ID        = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET    = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT       = os.getenv("REDDIT_USER_AGENT", "TourismBot/1.0")
