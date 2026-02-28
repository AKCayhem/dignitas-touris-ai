"""
Agent 2 – Script Writer
Uses Google Gemini 1.5 Flash (free: 1 M tokens/day) to generate
viral travel video scripts and platform-specific captions.
"""

import json
import random
from pathlib import Path
from datetime import datetime

from google import genai
import config
from utils.logger import logger
from utils.file_manager import get_output_path, timestamped_filename


class ScriptWriterAgent:
    """Generates viral travel video scripts powered by Gemini 1.5 Flash."""

    # Gemini model name (free tier)
    MODEL_NAME = "gemini-2.0-flash"

    def __init__(self) -> None:
        if not config.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set; script generation will fail")
        else:
            self.client = genai.Client(api_key=config.GEMINI_API_KEY)
            logger.info(f"Gemini model '{self.MODEL_NAME}' ready")

    # ── Public API ───────────────────────────────────────────────────────────

    async def generate_video_script(
        self,
        trend_topic: str,
        location: dict,
        style: str,
    ) -> dict:
        """
        Generate a complete 60-second video script via Gemini.

        Args:
            trend_topic: The trending topic to base the video on.
            location:    Location config dict (from config.LOCATION).
            style:       Video style string (e.g. 'top 5 hidden gems').

        Returns:
            Parsed script dict with all required keys.
        """
        prompt = self._build_prompt(trend_topic, location, style)
        logger.info(f"Generating script for topic: '{trend_topic}' style: '{style}'")

        try:
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=prompt
            )
            raw = response.text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            script = json.loads(raw)
            logger.info(f"✅ Script generated: '{script.get('title', 'Untitled')}'")
            return script

        except json.JSONDecodeError as exc:
            logger.error(f"Could not parse Gemini JSON response: {exc}")
            return self._fallback_script(trend_topic, location, style)
        except Exception as exc:
            logger.error(f"Gemini API error: {exc}")
            return self._fallback_script(trend_topic, location, style)

    def generate_thumbnail_title(self, script: dict) -> str:
        """
        Extract a clickable, SEO-friendly thumbnail title from the script.

        Args:
            script: Script dict returned by generate_video_script().

        Returns:
            Title string ≤ 60 characters.
        """
        title = script.get("thumbnail_text") or script.get("title", "")
        # Ensure max 60 chars; add ellipsis if truncated
        if len(title) > 60:
            title = title[:57] + "…"
        return title

    def adapt_caption_for_platform(self, base_caption: str, platform: str) -> str:
        """
        Reformat a base caption for a specific social-media platform.

        Args:
            base_caption: The master description from the script.
            platform:     One of 'instagram', 'youtube', 'facebook', 'telegram'.

        Returns:
            Platform-optimised caption string.
        """
        location_name = config.LOCATION["name"]
        hashtags = config.LOCATION["hashtags"]
        cta = config.CONTENT_STYLE["call_to_action"]

        platform = platform.lower()

        if platform == "instagram":
            # Emojis, 30 hashtags, line breaks
            tag_block = " ".join(hashtags[:30])
            caption = (
                f"✈️ {base_caption}\n\n"
                f"📍 {location_name}\n\n"
                f"💾 {cta}\n\n"
                f".\n.\n.\n"
                f"{tag_block}"
            )

        elif platform == "youtube":
            # SEO description with chapters placeholder
            tag_block = ", ".join(hashtags[:15])
            caption = (
                f"{base_caption}\n\n"
                f"📍 Location: {location_name}\n\n"
                f"⏱️ CHAPTERS:\n"
                f"0:00 Introduction\n"
                f"0:10 Main highlights\n"
                f"0:50 Final thoughts\n\n"
                f"🔔 Subscribe for more travel content!\n\n"
                f"Tags: {tag_block}"
            )

        elif platform == "facebook":
            tag_block = " ".join(hashtags[:5])
            caption = (
                f"{base_caption}\n\n"
                f"Have you ever visited {location_name}? Let us know in the comments! 💬\n\n"
                f"{tag_block}"
            )

        elif platform == "telegram":
            # Clean text, key highlights
            caption = (
                f"🌍 *{location_name}* – Must-See Destination!\n\n"
                f"{base_caption}\n\n"
                f"📌 Save this post for your travel bucket list!"
            )

        else:
            caption = base_caption

        return caption

    def save_script(self, script_data: dict, filename: str | None = None) -> dict:
        """
        Save the script as JSON and human-readable TXT.

        Args:
            script_data: Script dict.
            filename:    Optional base name (without extension).

        Returns:
            Dict with keys 'json_path' and 'txt_path'.
        """
        base = filename or timestamped_filename("script", "")
        base = base.rstrip(".")

        json_path = get_output_path("scripts", f"{base}.json")
        txt_path  = get_output_path("scripts", f"{base}.txt")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, indent=2, ensure_ascii=False)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self._script_to_readable(script_data))

        logger.info(f"Script saved → {json_path.name} / {txt_path.name}")
        return {"json_path": str(json_path), "txt_path": str(txt_path)}

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _build_prompt(self, topic: str, location: dict, style: str) -> str:
        attractions = ", ".join(location.get("local_attractions", []))
        return f"""You are a viral travel content creator specialising in short-form video.
Write a script for a 60-second vertical video (TikTok / Reels style).

Location : {location['name']}, {location['country']}
Topic    : {topic}
Style    : {style}
Tone     : Exciting, inspiring, conversational
Audience : Travel lovers aged 18-45
Attractions to mention: {attractions}

Return ONLY a valid JSON object (no markdown, no preamble) with EXACTLY these keys:
{{
  "hook": "First 3 seconds – shocking fact or question to stop the scroll",
  "intro": "Seconds 3-10 – brief intro",
  "main_content": ["point 1", "point 2", "point 3", "point 4", "point 5"],
  "transition_texts": ["text for image 1", "text for image 2", "text for image 3",
                       "text for image 4", "text for image 5", "text for image 6",
                       "text for image 7", "text for image 8", "text for image 9",
                       "text for image 10", "text for image 11", "text for image 12"],
  "voiceover_script": "Full 60-second narration text",
  "outro": "Last 5 seconds with call to action",
  "title": "YouTube/social media title (60 chars max)",
  "description": "Full platform description (approx 200 words)",
  "thumbnail_text": "Bold 4-word text for thumbnail",
  "search_queries": ["query1", "query2", "query3"]
}}"""

    def _fallback_script(self, topic: str, location: dict, style: str) -> dict:
        """Return a basic script when Gemini is unavailable."""
        loc = location["name"]
        return {
            "hook": f"Did you know {loc} is one of North Africa's best-kept secrets?",
            "intro": f"Welcome to {loc}!",
            "main_content": [
                f"Explore the ancient Medina of {loc}",
                "Discover stunning Mediterranean beaches",
                "Taste authentic local cuisine",
                "Visit world-class historical sites",
                "Experience vibrant local culture",
            ],
            "transition_texts": [
                f"Welcome to {loc}!",
                "Ancient Medina",
                "Blue & White Streets",
                "Carthage Ruins",
                "Local Cuisine",
                "Mediterranean Views",
                "Bardo Museum",
                "Sidi Bou Said",
                "Local Markets",
                "Sunset Spots",
                "Hidden Gems",
                f"Visit {loc} Today!",
            ],
            "voiceover_script": (
                f"Welcome to {loc}, Tunisia's incredible capital city. "
                f"From the ancient Medina to the sparkling Mediterranean coast, "
                f"{loc} has something for every traveller. Explore the iconic blue and white "
                f"streets of Sidi Bou Said, walk among the ruins of ancient Carthage, "
                f"and discover flavours you'll never forget. "
                f"Save this video for your next adventure!"
            ),
            "outro": "Save this for your next trip! Like and follow for more!",
            "title": f"Top 5 Reasons to Visit {loc} Right Now",
            "description": (
                f"Discover the hidden gems of {loc}, Tunisia. "
                f"From ancient ruins to stunning beaches, {loc} offers an unforgettable "
                f"travel experience. Watch to find out why {loc} should be your next destination!"
            ),
            "thumbnail_text": f"Visit {loc} NOW!",
            "search_queries": [
                f"{loc} travel photography",
                f"Tunisia tourism landscape",
                f"Medina {loc} streets",
            ],
        }

    @staticmethod
    def _script_to_readable(script: dict) -> str:
        """Convert script dict to a nicely formatted plain-text string."""
        lines = [
            "=" * 60,
            "TOURISM VIDEO SCRIPT",
            "=" * 60,
            "",
            f"TITLE: {script.get('title', '')}",
            "",
            f"HOOK (0-3s):",
            f"  {script.get('hook', '')}",
            "",
            f"INTRO (3-10s):",
            f"  {script.get('intro', '')}",
            "",
            "MAIN CONTENT:",
        ]
        for i, point in enumerate(script.get("main_content", []), 1):
            lines.append(f"  {i}. {point}")
        lines += [
            "",
            "TRANSITION TEXTS:",
        ]
        for i, txt in enumerate(script.get("transition_texts", []), 1):
            lines.append(f"  [{i:02d}] {txt}")
        lines += [
            "",
            "VOICEOVER SCRIPT:",
            script.get("voiceover_script", ""),
            "",
            f"OUTRO: {script.get('outro', '')}",
            "",
            f"THUMBNAIL TEXT: {script.get('thumbnail_text', '')}",
            "",
            "SEARCH QUERIES:",
        ]
        for q in script.get("search_queries", []):
            lines.append(f"  - {q}")
        lines += ["", "=" * 60]
        return "\n".join(lines)
