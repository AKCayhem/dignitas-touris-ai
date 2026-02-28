"""
File-system helpers for the Tourism Agent pipeline.
All paths use pathlib.Path for cross-platform support.
"""

import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from utils.logger import logger


BASE_DIR   = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"

DIRS = {
    "videos":  OUTPUT_DIR / "videos",
    "images":  OUTPUT_DIR / "images",
    "audio":   OUTPUT_DIR / "audio",
    "scripts": OUTPUT_DIR / "scripts",
    "reports": OUTPUT_DIR / "reports",
    "logs":    BASE_DIR / "logs",
}


def ensure_dirs() -> None:
    """Create all required output directories if they don't exist."""
    for name, path in DIRS.items():
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory ready: {path}")


def timestamped_filename(prefix: str, ext: str) -> str:
    """Return a unique filename like 'video_20240601_153045.mp4'."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.{ext.lstrip('.')}"


def get_output_path(category: str, filename: str) -> Path:
    """
    Build a full Path inside the correct output sub-folder.

    Args:
        category: One of 'videos', 'images', 'audio', 'scripts', 'reports'.
        filename: The file name (with extension).

    Returns:
        Full Path object.
    """
    folder = DIRS.get(category, OUTPUT_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / filename


def file_hash(path: Path) -> str:
    """Return MD5 hash of a file for deduplication checks."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def deduplicate_files(paths: list[Path]) -> list[Path]:
    """
    Remove duplicate files (by content hash) from a list of paths.

    Args:
        paths: List of Path objects.

    Returns:
        De-duplicated list preserving original order.
    """
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        try:
            h = file_hash(p)
            if h not in seen:
                seen.add(h)
                unique.append(p)
        except Exception as exc:
            logger.warning(f"Could not hash {p}: {exc}")
            unique.append(p)  # keep it rather than lose it
    removed = len(paths) - len(unique)
    if removed:
        logger.info(f"Removed {removed} duplicate file(s)")
    return unique


def cleanup_temp_files(folder: Path, older_than_days: int = 7) -> int:
    """
    Delete files in *folder* that are older than *older_than_days*.

    Returns:
        Number of files deleted.
    """
    from datetime import timedelta
    cutoff = datetime.now().timestamp() - older_than_days * 86400
    count = 0
    for p in folder.rglob("*"):
        if p.is_file() and p.stat().st_mtime < cutoff:
            try:
                p.unlink()
                count += 1
            except Exception as exc:
                logger.warning(f"Could not delete {p}: {exc}")
    logger.info(f"Cleaned up {count} old temp file(s) from {folder}")
    return count


def copy_to_output(src: Path, category: str, new_name: str | None = None) -> Path:
    """
    Copy *src* into the appropriate output sub-folder.

    Args:
        src:      Source file path.
        category: Output category folder name.
        new_name: Optional new filename; defaults to original name.

    Returns:
        Destination Path.
    """
    dest = get_output_path(category, new_name or src.name)
    shutil.copy2(src, dest)
    logger.debug(f"Copied {src.name} → {dest}")
    return dest
