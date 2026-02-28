"""
Centralised logging for the Tourism Agent pipeline.
Uses loguru for rich, coloured output + file rotation.
"""

import sys
from pathlib import Path
from loguru import logger

LOG_FILE = Path(__file__).parent.parent / "logs" / "agent.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Remove default handler then add our custom ones
logger.remove()

# ── Console handler (coloured) ────────────────────────────────────────────────
logger.add(
    sys.stdout,
    colorize=True,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    level="DEBUG",
)

# ── File handler (rotated daily, kept 7 days) ─────────────────────────────────
logger.add(
    str(LOG_FILE),
    rotation="1 day",
    retention="7 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    encoding="utf-8",
)

__all__ = ["logger"]
