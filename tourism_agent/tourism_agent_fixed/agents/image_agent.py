"""
Agent 3 – Image Collector
Downloads high-quality, royalty-free travel images from Unsplash,
Pexels, Pixabay, and Wikimedia Commons, then prepares them for
the video pipeline (resize, text overlay, thumbnail).
"""

import io
import time
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance
from tqdm import tqdm

import config
from utils.logger import logger
from utils.file_manager import get_output_path, timestamped_filename, deduplicate_files

# Target resolution (width × height)
W, H = config.VIDEO_CONFIG["resolution"]   # 1080 × 1920


class ImageCollectorAgent:
    """Downloads and prepares images for the video creation pipeline."""

    UNSPLASH_BASE  = "https://api.unsplash.com"
    PEXELS_BASE    = "https://api.pexels.com/v1"
    PIXABAY_BASE   = "https://pixabay.com/api"
    WIKIMEDIA_BASE = "https://commons.wikimedia.org/w/api.php"

    def __init__(self) -> None:
        self.unsplash_key = config.UNSPLASH_ACCESS_KEY
        self.pexels_key   = config.PEXELS_API_KEY
        self.pixabay_key  = config.PIXABAY_API_KEY
        self.session      = requests.Session()
        self.session.headers.update({"User-Agent": "TourismAgent/1.0"})
        self._font_cache: dict[int, ImageFont.FreeTypeFont] = {}
        logger.info("ImageCollectorAgent ready")

    # ── Source-specific search/download ──────────────────────────────────────

    def search_unsplash(self, query: str, count: int = 5) -> list[Path]:
        """
        Search Unsplash and download high-quality portrait photos.

        Args:
            query: Search term.
            count: Number of images to download.

        Returns:
            List of local file paths.
        """
        if not self.unsplash_key:
            logger.warning("Unsplash key missing; skipping")
            return []

        paths: list[Path] = []
        try:
            resp = self.session.get(
                f"{self.UNSPLASH_BASE}/search/photos",
                params={
                    "query": query,
                    "per_page": count,
                    "orientation": "portrait",
                    "client_id": self.unsplash_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            for item in resp.json().get("results", []):
                url = item["urls"].get("full") or item["urls"].get("regular")
                if url:
                    path = self._download_image(url, f"unsplash_{item['id']}.jpg")
                    if path:
                        paths.append(path)
        except Exception as exc:
            logger.warning(f"Unsplash error: {exc}")
        return paths

    def search_pexels(self, query: str, count: int = 4) -> list[Path]:
        """
        Search Pexels and download authentic travel photos.

        Args:
            query: Search term.
            count: Number of images.

        Returns:
            List of local file paths.
        """
        if not self.pexels_key:
            logger.warning("Pexels key missing; skipping")
            return []

        paths: list[Path] = []
        try:
            resp = self.session.get(
                f"{self.PEXELS_BASE}/search",
                params={"query": query, "per_page": count, "orientation": "portrait"},
                headers={"Authorization": self.pexels_key},
                timeout=15,
            )
            resp.raise_for_status()
            for item in resp.json().get("photos", []):
                url = item["src"].get("original") or item["src"].get("large2x")
                if url:
                    path = self._download_image(url, f"pexels_{item['id']}.jpg")
                    if path:
                        paths.append(path)
        except Exception as exc:
            logger.warning(f"Pexels error: {exc}")
        return paths

    def search_pixabay(self, query: str, count: int = 3) -> list[Path]:
        """
        Search Pixabay specifically for aerial/drone travel shots.

        Args:
            query: Search term.
            count: Number of images.

        Returns:
            List of local file paths.
        """
        if not self.pixabay_key:
            logger.warning("Pixabay key missing; skipping")
            return []

        paths: list[Path] = []
        try:
            resp = self.session.get(
                self.PIXABAY_BASE,
                params={
                    "key": self.pixabay_key,
                    "q": query,
                    "image_type": "photo",
                    "category": "travel",
                    "orientation": "vertical",
                    "per_page": count,
                    "safesearch": "true",
                },
                timeout=15,
            )
            resp.raise_for_status()
            for item in resp.json().get("hits", []):
                url = item.get("largeImageURL") or item.get("webformatURL")
                if url:
                    path = self._download_image(url, f"pixabay_{item['id']}.jpg")
                    if path:
                        paths.append(path)
        except Exception as exc:
            logger.warning(f"Pixabay error: {exc}")
        return paths

    def search_wikimedia(self, query: str, count: int = 3) -> list[Path]:
        """
        Search Wikimedia Commons for freely licensed travel images (no key needed).

        Args:
            query: Search term.
            count: Number of images.

        Returns:
            List of local file paths.
        """
        paths: list[Path] = []
        try:
            resp = self.session.get(
                self.WIKIMEDIA_BASE,
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": f"File:{query} travel",
                    "gsrnamespace": 6,
                    "gsrlimit": count,
                    "prop": "imageinfo",
                    "iiprop": "url|size",
                    "format": "json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                for info in page.get("imageinfo", []):
                    url = info.get("url", "")
                    if url and any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                        fname = f"wiki_{page.get('pageid', 'x')}.jpg"
                        path = self._download_image(url, fname)
                        if path:
                            paths.append(path)
        except Exception as exc:
            logger.warning(f"Wikimedia error: {exc}")
        return paths

    # ── Orchestrated collection ───────────────────────────────────────────────

    async def collect_all_images(
        self,
        search_queries: list[str],
        total_needed: int = 12,
    ) -> list[Path]:
        """
        Run all image sources in parallel, deduplicate, resize to video
        resolution, and return exactly *total_needed* images.

        Args:
            search_queries: List of search terms from the script.
            total_needed:   Exact number of images required.

        Returns:
            List of *total_needed* processed image Paths.
        """
        logger.info(f"Collecting {total_needed} images for queries: {search_queries}")

        loop = asyncio.get_event_loop()
        all_paths: list[Path] = []

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = []
            for query in search_queries:
                futures.append(loop.run_in_executor(pool, self.search_unsplash, query, 4))
                futures.append(loop.run_in_executor(pool, self.search_pexels,   query, 3))
                futures.append(loop.run_in_executor(pool, self.search_pixabay,  query, 2))
                futures.append(loop.run_in_executor(pool, self.search_wikimedia, query, 2))

            results = await asyncio.gather(*futures, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_paths.extend(result)

        # Deduplicate
        all_paths = deduplicate_files(all_paths)

        # If we still don't have enough, fall back to location-name search
        if len(all_paths) < total_needed:
            location_name = config.LOCATION["name"]
            extra = self.search_unsplash(location_name, total_needed - len(all_paths) + 3)
            all_paths.extend(extra)
            all_paths = deduplicate_files(all_paths)

        # Resize to video resolution
        resized: list[Path] = []
        for p in tqdm(all_paths[:total_needed], desc="Resizing images"):
            rp = self._resize_to_video_format(p)
            if rp:
                resized.append(rp)

        # Pad with placeholders if still short
        while len(resized) < total_needed:
            resized.append(resized[-1] if resized else self._create_placeholder(len(resized)))

        logger.info(f"✅ {len(resized[:total_needed])} images ready")
        return resized[:total_needed]

    # ── Image manipulation ────────────────────────────────────────────────────

    def add_text_overlay(
        self,
        image_path: Path,
        text: str,
        position: str = "bottom",
    ) -> Path:
        """
        Add a semi-transparent gradient + white text overlay onto an image.

        Args:
            image_path: Path to source image.
            text:       Text to overlay.
            position:   'bottom', 'top', or 'center'.

        Returns:
            Path to the modified image.
        """
        try:
            img = Image.open(image_path).convert("RGBA")
            draw = ImageDraw.Draw(img)
            font = self._get_font(config.VIDEO_CONFIG["font_size"])

            img_w, img_h = img.size
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]

            # Gradient overlay height
            grad_h = int(img_h * 0.3)

            # Position
            if position == "bottom":
                grad_y = img_h - grad_h
                text_x = (img_w - text_w) // 2
                text_y = img_h - text_h - 30
            elif position == "top":
                grad_y = 0
                text_x = (img_w - text_w) // 2
                text_y = 20
            else:  # center
                grad_y = (img_h - grad_h) // 2
                text_x = (img_w - text_w) // 2
                text_y = (img_h - text_h) // 2

            # Draw gradient
            gradient = Image.new("RGBA", (img_w, grad_h))
            for y in range(grad_h):
                alpha = int(180 * (y / grad_h)) if position == "bottom" else int(180 * (1 - y / grad_h))
                for x in range(img_w):
                    gradient.putpixel((x, y), (0, 0, 0, alpha))
            img.paste(gradient, (0, grad_y), gradient)

            # Shadow
            if config.VIDEO_CONFIG.get("text_shadow"):
                draw.text((text_x + 2, text_y + 2), text, font=font, fill=(0, 0, 0, 200))
            draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))

            # Save as RGB
            out_img = img.convert("RGB")
            out_path = get_output_path("images", f"overlay_{image_path.name}")
            out_img.save(out_path, quality=92)
            return out_path

        except Exception as exc:
            logger.warning(f"Text overlay failed for {image_path.name}: {exc}")
            return image_path

    def create_thumbnail(
        self,
        best_image: Path,
        title_text: str,
        location_name: str,
    ) -> Path:
        """
        Create an eye-catching thumbnail from the best image.

        Args:
            best_image:    Source image path.
            title_text:    Bold text to show (4 words max).
            location_name: Location name for badge.

        Returns:
            Path to thumbnail JPEG.
        """
        try:
            img = Image.open(best_image).convert("RGB")
            img = img.resize((1280, 720), Image.LANCZOS)  # YouTube thumbnail size
            draw = ImageDraw.Draw(img)
            img_w, img_h = img.size

            # Dark vignette border
            for margin in range(40, 0, -1):
                alpha_val = int(200 * (1 - margin / 40))
                draw.rectangle([margin, margin, img_w - margin, img_h - margin],
                                outline=(0, 0, 0), width=1)

            # Title text (large, centered, with shadow)
            font_large = self._get_font(72)
            font_small = self._get_font(36)

            # Title
            tb = draw.textbbox((0, 0), title_text, font=font_large)
            tw = tb[2] - tb[0]
            tx = (img_w - tw) // 2
            ty = img_h // 2 - 60
            draw.text((tx + 3, ty + 3), title_text, font=font_large, fill=(0, 0, 0))
            draw.text((tx, ty), title_text, font=font_large, fill=(255, 235, 59))

            # Location badge
            badge_text = f"📍 {location_name}"
            bb = draw.textbbox((0, 0), badge_text, font=font_small)
            bw = bb[2] - bb[0]
            bx = (img_w - bw) // 2
            by = ty + 90
            draw.rectangle([bx - 10, by - 5, bx + bw + 10, by + 40], fill=(220, 20, 60))
            draw.text((bx, by), badge_text, font=font_small, fill=(255, 255, 255))

            out_path = get_output_path("images", "thumbnail.jpg")
            img.save(out_path, quality=95)
            logger.info(f"Thumbnail created: {out_path.name}")
            return out_path

        except Exception as exc:
            logger.warning(f"Thumbnail creation failed: {exc}")
            return best_image

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _download_image(self, url: str, filename: str) -> Optional[Path]:
        """Download an image from *url* and save to the images folder."""
        dest = get_output_path("images", filename)
        if dest.exists():
            return dest  # Already downloaded
        try:
            resp = self.session.get(url, timeout=20, stream=True)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            logger.debug(f"Downloaded: {filename}")
            return dest
        except Exception as exc:
            logger.warning(f"Download failed for {filename}: {exc}")
            return None

    def _resize_to_video_format(self, image_path: Path) -> Optional[Path]:
        """
        Resize/crop an image to the video resolution (portrait, 9:16).
        Uses smart crop: keeps centre of image.
        """
        try:
            img = Image.open(image_path).convert("RGB")
            target_w, target_h = W, H

            # Compute scale to fill the target canvas
            scale = max(target_w / img.width, target_h / img.height)
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)

            # Centre crop
            left = (new_w - target_w) // 2
            top  = (new_h - target_h) // 2
            img  = img.crop((left, top, left + target_w, top + target_h))

            # Mild saturation boost for vibrancy
            img = ImageEnhance.Color(img).enhance(1.15)

            out_path = get_output_path("images", f"resized_{image_path.name}")
            img.save(out_path, quality=90)
            return out_path

        except Exception as exc:
            logger.warning(f"Resize failed for {image_path.name}: {exc}")
            return None

    def _create_placeholder(self, index: int) -> Path:
        """Create a solid-colour placeholder image when we run out of downloads."""
        colours = [
            (52, 152, 219), (46, 204, 113), (155, 89, 182),
            (231, 76, 60),  (241, 196, 15), (26, 188, 156),
        ]
        colour = colours[index % len(colours)]
        img = Image.new("RGB", (W, H), colour)
        draw = ImageDraw.Draw(img)
        font = self._get_font(60)
        text = config.LOCATION["name"]
        tb = draw.textbbox((0, 0), text, font=font)
        tw = tb[2] - tb[0]
        draw.text(((W - tw) // 2, H // 2 - 30), text, font=font, fill=(255, 255, 255))
        out_path = get_output_path("images", f"placeholder_{index:02d}.jpg")
        img.save(out_path)
        return out_path

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Load (and cache) a TrueType font at *size*."""
        if size not in self._font_cache:
            try:
                self._font_cache[size] = ImageFont.truetype("Arial.ttf", size)
            except IOError:
                try:
                    # Linux common paths
                    for path in [
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                    ]:
                        if Path(path).exists():
                            self._font_cache[size] = ImageFont.truetype(path, size)
                            break
                    else:
                        raise IOError("No TrueType font found")
                except IOError:
                    self._font_cache[size] = ImageFont.load_default()
        return self._font_cache[size]
