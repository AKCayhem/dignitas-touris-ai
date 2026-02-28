"""
Agent 7 – Publisher
Publishes the final video to YouTube, Instagram, Facebook, and Telegram.
Supports immediate and scheduled publishing with retry logic.
"""

import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

import config
from utils.logger import logger
from utils.file_manager import get_output_path


# Queue file for scheduled posts
QUEUE_FILE = Path(__file__).parent.parent / "logs" / "publish_queue.json"


class PublisherAgent:
    """Handles multi-platform social media publishing with retry logic."""

    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds between retries

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TourismAgent/1.0"})
        self._scheduler = None   # Set externally via set_scheduler()
        logger.info("PublisherAgent ready")

    def set_scheduler(self, scheduler) -> None:
        """Inject the APScheduler instance for deferred posts."""
        self._scheduler = scheduler

    # ── Platform publishers ───────────────────────────────────────────────────

    def publish_to_youtube(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        thumbnail_path: Optional[Path] = None,
    ) -> Optional[str]:
        """
        Upload a video to YouTube using the Data API v3.

        Args:
            video_path:      Path to the video file.
            title:           Video title (≤100 chars).
            description:     Video description.
            tags:            List of tags (strings, no '#').
            thumbnail_path:  Optional custom thumbnail.

        Returns:
            YouTube video URL string, or None on failure.
        """
        if not all([config.YOUTUBE_CLIENT_ID, config.YOUTUBE_CLIENT_SECRET,
                    config.YOUTUBE_REFRESH_TOKEN]):
            logger.warning("YouTube credentials incomplete; skipping YouTube upload")
            return None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                from googleapiclient.discovery import build
                from google.oauth2.credentials import Credentials
                from googleapiclient.http import MediaFileUpload

                creds = Credentials(
                    token=None,
                    refresh_token=config.YOUTUBE_REFRESH_TOKEN,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=config.YOUTUBE_CLIENT_ID,
                    client_secret=config.YOUTUBE_CLIENT_SECRET,
                )
                youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

                # Clean tags (remove '#')
                clean_tags = [t.lstrip("#") for t in tags]

                body = {
                    "snippet": {
                        "title": title[:100],
                        "description": description,
                        "tags": clean_tags[:15],
                        "categoryId": "19",   # Travel & Events
                        "defaultLanguage": config.LOCATION["language"],
                    },
                    "status": {
                        "privacyStatus": "public",
                        "selfDeclaredMadeForKids": False,
                    },
                }

                media = MediaFileUpload(
                    str(video_path),
                    mimetype="video/mp4",
                    resumable=True,
                    chunksize=1024 * 1024 * 5,  # 5 MB chunks
                )

                request = youtube.videos().insert(
                    part=",".join(body.keys()),
                    body=body,
                    media_body=media,
                )

                response = None
                while response is None:
                    _, response = request.next_chunk()

                video_id = response["id"]
                url = f"https://www.youtube.com/watch?v={video_id}"

                # Upload thumbnail if provided
                if thumbnail_path and thumbnail_path.exists():
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
                    ).execute()
                    logger.info("Thumbnail uploaded to YouTube")

                logger.info(f"✅ YouTube upload complete: {url}")
                return url

            except Exception as exc:
                logger.warning(f"YouTube attempt {attempt}/{self.MAX_RETRIES} failed: {exc}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)

        logger.error("YouTube upload failed after all retries")
        return None

    def publish_to_instagram(
        self,
        video_path: Path,
        caption: str,
        thumbnail_path: Optional[Path] = None,
    ) -> Optional[str]:
        """
        Publish a Reel to Instagram via Meta Graph API.

        Args:
            video_path:     Path to the video file.
            caption:        Post caption with hashtags.
            thumbnail_path: Optional cover image.

        Returns:
            Instagram post URL, or None on failure.
        """
        if not all([config.INSTAGRAM_ACCESS_TOKEN, config.INSTAGRAM_PAGE_ID]):
            logger.warning("Instagram credentials missing; skipping")
            return None

        base_url = f"https://graph.facebook.com/v18.0/{config.INSTAGRAM_PAGE_ID}"
        params = {"access_token": config.INSTAGRAM_ACCESS_TOKEN}

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Step 1: Create container
                container_data: dict = {
                    "media_type": "REELS",
                    "video_url": self._upload_video_to_cdn(video_path),
                    "caption": caption[:2200],
                }
                if thumbnail_path and thumbnail_path.exists():
                    container_data["thumb_offset"] = "0"

                resp = self.session.post(
                    f"{base_url}/media",
                    params=params,
                    json=container_data,
                    timeout=60,
                )
                resp.raise_for_status()
                container_id = resp.json()["id"]

                # Step 2: Wait for video processing
                self._wait_for_ig_processing(container_id, params)

                # Step 3: Publish
                pub_resp = self.session.post(
                    f"{base_url}/media_publish",
                    params=params,
                    json={"creation_id": container_id},
                    timeout=30,
                )
                pub_resp.raise_for_status()
                post_id = pub_resp.json()["id"]
                url = f"https://www.instagram.com/p/{post_id}/"
                logger.info(f"✅ Instagram published: {url}")
                return url

            except Exception as exc:
                logger.warning(f"Instagram attempt {attempt}/{self.MAX_RETRIES} failed: {exc}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)

        logger.error("Instagram publishing failed after all retries")
        return None

    def publish_to_facebook(
        self,
        video_path: Path,
        description: str,
        thumbnail_path: Optional[Path] = None,
    ) -> Optional[str]:
        """
        Upload video to Facebook Page.

        Args:
            video_path:   Path to the video file.
            description:  Post description.

        Returns:
            Facebook post URL, or None on failure.
        """
        if not all([config.FACEBOOK_ACCESS_TOKEN, config.FACEBOOK_PAGE_ID]):
            logger.warning("Facebook credentials missing; skipping")
            return None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                url = f"https://graph-video.facebook.com/v18.0/{config.FACEBOOK_PAGE_ID}/videos"
                with open(video_path, "rb") as vf:
                    resp = self.session.post(
                        url,
                        data={
                            "description": description[:5000],
                            "access_token": config.FACEBOOK_ACCESS_TOKEN,
                        },
                        files={"source": vf},
                        timeout=300,
                    )
                resp.raise_for_status()
                post_id = resp.json().get("id", "")
                fb_url = f"https://www.facebook.com/video/{post_id}"
                logger.info(f"✅ Facebook published: {fb_url}")
                return fb_url

            except Exception as exc:
                logger.warning(f"Facebook attempt {attempt}/{self.MAX_RETRIES} failed: {exc}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)

        logger.error("Facebook publishing failed after all retries")
        return None

    def publish_to_telegram(
        self,
        video_path: Path,
        caption: str,
        channel_id: Optional[str] = None,
    ) -> Optional[int]:
        """
        Send video to Telegram channel via Bot API.

        Args:
            video_path: Path to the video file.
            caption:    Post caption (up to 1024 chars for Telegram).
            channel_id: Override channel ID from config.

        Returns:
            Telegram message ID, or None on failure.
        """
        token = config.TELEGRAM_BOT_TOKEN
        channel = channel_id or config.TELEGRAM_CHANNEL_ID

        if not token or not channel:
            logger.warning("Telegram credentials missing; skipping")
            return None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                url = f"https://api.telegram.org/bot{token}/sendVideo"
                with open(video_path, "rb") as vf:
                    resp = self.session.post(
                        url,
                        data={
                            "chat_id": channel,
                            "caption": caption[:1024],
                            "parse_mode": "Markdown",
                            "supports_streaming": True,
                        },
                        files={"video": vf},
                        timeout=300,
                    )
                resp.raise_for_status()
                msg_id = resp.json()["result"]["message_id"]

                # Pin the message
                self.session.post(
                    f"https://api.telegram.org/bot{token}/pinChatMessage",
                    data={"chat_id": channel, "message_id": msg_id},
                    timeout=10,
                )

                logger.info(f"✅ Telegram published: message_id={msg_id}")
                return msg_id

            except Exception as exc:
                logger.warning(f"Telegram attempt {attempt}/{self.MAX_RETRIES} failed: {exc}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)

        logger.error("Telegram publishing failed after all retries")
        return None

    # ── Orchestrated publishing ───────────────────────────────────────────────

    async def publish_to_all_platforms(
        self,
        video_path: Path,
        content_data: dict,
        schedule_time: Optional[datetime] = None,
    ) -> dict[str, str | int | None]:
        """
        Publish to all configured platforms simultaneously (or schedule them).

        Args:
            video_path:    Path to the final video.
            content_data:  Dict with 'title', 'captions', 'thumbnail', 'tags'.
            schedule_time: If set, queue posts for this datetime instead.

        Returns:
            Dict of platform → URL/message_id/None.
        """
        if schedule_time:
            return self._schedule_all(video_path, content_data, schedule_time)

        results: dict = {}
        platforms = config.SCHEDULE["platforms"]
        captions = content_data.get("captions", {})
        thumbnail = content_data.get("thumbnail")
        title = content_data.get("title", config.LOCATION["name"])
        tags = content_data.get("tags", config.LOCATION["hashtags"])

        # Run all platform uploads concurrently
        loop = asyncio.get_event_loop()
        tasks = {}

        if "youtube" in platforms:
            tasks["youtube"] = loop.run_in_executor(
                None, self.publish_to_youtube,
                video_path, title, captions.get("youtube", ""),
                tags, thumbnail,
            )
        if "instagram" in platforms:
            tasks["instagram"] = loop.run_in_executor(
                None, self.publish_to_instagram,
                video_path, captions.get("instagram", ""), thumbnail,
            )
        if "facebook" in platforms:
            tasks["facebook"] = loop.run_in_executor(
                None, self.publish_to_facebook,
                video_path, captions.get("facebook", ""), thumbnail,
            )
        if "telegram" in platforms:
            tasks["telegram"] = loop.run_in_executor(
                None, self.publish_to_telegram,
                video_path, captions.get("telegram", ""),
            )

        for platform, task in tasks.items():
            try:
                results[platform] = await task
            except Exception as exc:
                logger.error(f"{platform} publish error: {exc}")
                results[platform] = None

        logger.info(f"Publishing results: {results}")
        return results

    def schedule_post(
        self,
        platform: str,
        content: dict,
        publish_time: datetime,
    ) -> str:
        """
        Persist a post to the JSON queue for deferred publishing.

        Args:
            platform:     Platform name.
            content:      Content payload.
            publish_time: When to publish.

        Returns:
            Queue entry ID.
        """
        queue = self._load_queue()
        entry_id = f"{platform}_{publish_time.strftime('%Y%m%d_%H%M%S')}"
        queue[entry_id] = {
            "platform": platform,
            "content": content,
            "publish_time": publish_time.isoformat(),
            "status": "pending",
        }
        self._save_queue(queue)
        logger.info(f"Post scheduled: {entry_id} at {publish_time}")
        return entry_id

    def verify_upload(self, platform: str, post_id: str) -> bool:
        """
        Confirm an upload is live on the given platform.

        Args:
            platform: Platform name.
            post_id:  Video/post ID returned during upload.

        Returns:
            True if the post is publicly accessible.
        """
        try:
            if platform == "youtube":
                url = f"https://www.youtube.com/watch?v={post_id}"
                resp = self.session.head(url, timeout=10)
                return resp.status_code == 200

            elif platform == "telegram":
                return bool(post_id)   # Message IDs are immediately valid

            else:
                # Generic check: try to fetch the URL
                resp = self.session.head(str(post_id), timeout=10)
                return resp.status_code in (200, 301, 302)

        except Exception as exc:
            logger.warning(f"Verification failed for {platform}/{post_id}: {exc}")
            return False

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _upload_video_to_cdn(self, video_path: Path) -> str:
        """
        Instagram requires a publicly accessible video URL.
        In production, upload to your own CDN / S3 bucket.
        This is a placeholder that logs a warning and returns an empty string.
        """
        logger.warning(
            "Instagram requires a public video URL. "
            "Please upload the video to a CDN (e.g. S3/Cloudflare R2) "
            "and set the URL here. Returning placeholder."
        )
        return ""  # Replace with actual CDN URL

    def _wait_for_ig_processing(self, container_id: str, params: dict, timeout: int = 120) -> None:
        """Poll Instagram until the video container is fully processed."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self.session.get(
                f"https://graph.facebook.com/v18.0/{container_id}",
                params={**params, "fields": "status_code"},
                timeout=10,
            )
            status = resp.json().get("status_code", "")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise RuntimeError("Instagram video processing failed")
            time.sleep(5)
        raise TimeoutError("Instagram processing timeout")

    def _schedule_all(
        self, video_path: Path, content_data: dict, schedule_time: datetime
    ) -> dict:
        """Queue posts for all platforms at *schedule_time*."""
        results = {}
        for platform in config.SCHEDULE["platforms"]:
            entry_id = self.schedule_post(platform, content_data, schedule_time)
            results[platform] = f"scheduled:{entry_id}"
        return results

    def _load_queue(self) -> dict:
        if QUEUE_FILE.exists():
            try:
                return json.loads(QUEUE_FILE.read_text())
            except Exception:
                pass
        return {}

    def _save_queue(self, queue: dict) -> None:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        QUEUE_FILE.write_text(json.dumps(queue, indent=2))
