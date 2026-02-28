"""
Agent 4 – Video Creator
Assembles a polished 60-second vertical travel video using moviepy.
Applies Ken Burns effect, crossfade transitions, animated text overlays,
colour grading, intro/outro animations, and watermark.
"""

import random
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageEnhance
from tqdm import tqdm

# moviepy imports (graceful fallback so the rest of the code can be imported)
try:
    from moviepy.editor import (
        ImageClip, ColorClip, CompositeVideoClip,
        concatenate_videoclips, AudioFileClip,
        TextClip, VideoFileClip, VideoClip,
    )
    try:
        from moviepy.video.fx.fadein  import fadein
        from moviepy.video.fx.fadeout import fadeout
    except ImportError:
        fadein = fadeout = None
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

import config
from utils.logger import logger
from utils.file_manager import get_output_path, timestamped_filename

W, H   = config.VIDEO_CONFIG["resolution"]   # 1080 × 1920
FPS    = config.VIDEO_CONFIG["fps"]
TOTAL  = config.VIDEO_CONFIG["duration_seconds"]   # 60 s
N_IMG  = config.VIDEO_CONFIG["images_per_video"]   # 12
PER_IMG = TOTAL / N_IMG                             # 5 s per image


class VideoCreatorAgent:
    """Creates fully produced travel videos from a list of images."""

    def __init__(self) -> None:
        if not MOVIEPY_AVAILABLE:
            logger.warning("moviepy not installed – video creation disabled")
        logger.info("VideoCreatorAgent ready")

    # ── Public API ───────────────────────────────────────────────────────────

    def create_image_slideshow(
        self,
        images: list[Path],
        durations: Optional[list[float]] = None,
        transitions: str = "fade",
    ):
        """
        Build a continuous slideshow clip from *images* with Ken Burns effect
        and crossfade transitions.

        Args:
            images:      List of image Paths (should be pre-resized).
            durations:   Per-image durations in seconds; defaults to equal split.
            transitions: Currently only 'fade' is supported.

        Returns:
            moviepy CompositeVideoClip or None if moviepy unavailable.
        """
        if not MOVIEPY_AVAILABLE:
            logger.error("moviepy unavailable; cannot create slideshow")
            return None

        if durations is None:
            durations = [PER_IMG] * len(images)

        clips = []
        td = config.VIDEO_CONFIG["transition_duration"]

        for i, (img_path, dur) in enumerate(
            tqdm(zip(images, durations), total=len(images), desc="Building slideshow")
        ):
            clip = self._make_ken_burns_clip(img_path, dur)
            clip = self._apply_colour_grade(clip)

            # Crossfade: all clips except the first fade in
            if i > 0:
                clip = clip.crossfadein(td)

            clips.append(clip)

        # Concatenate with crossfade overlap
        video = concatenate_videoclips(clips, method="compose", padding=-td)
        logger.info(f"Slideshow built: {video.duration:.1f}s, {len(clips)} clips")
        return video

    def add_text_overlays(self, video_clip, text_data: dict):
        """
        Add animated text overlays to each image segment of the video.

        Args:
            video_clip: Base moviepy clip.
            text_data:  Script dict containing 'hook', 'transition_texts', etc.

        Returns:
            CompositeVideoClip with text overlays.
        """
        if not MOVIEPY_AVAILABLE or video_clip is None:
            return video_clip

        overlays = []
        hook_text = text_data.get("hook", "")
        texts     = text_data.get("transition_texts", [])

        # Hook overlay – first 3 seconds, large and centred
        if hook_text:
            hook_clip = (
                TextClip(hook_text, fontsize=56, color="white", font="DejaVu-Sans-Bold",
                         method="caption", size=(W - 80, None), align="center")
                .set_start(0)
                .set_duration(3)
                .set_position("center")
                .crossfadein(0.3)
                .crossfadeout(0.3)
            )
            overlays.append(hook_clip)

        # Per-image text overlays
        for i, text in enumerate(texts[:N_IMG]):
            start = i * PER_IMG
            txt_clip = (
                TextClip(text, fontsize=44, color="white", font="DejaVu-Sans",
                         method="caption", size=(W - 80, None), align="center",
                         stroke_color="black", stroke_width=2)
                .set_start(start + 0.3)
                .set_duration(PER_IMG - 0.6)
                .set_position(("center", H - 220))
                .crossfadein(0.3)
                .crossfadeout(0.3)
            )
            overlays.append(txt_clip)

        # Progress bar (thin white line at very bottom)
        def make_progress_bar(t):
            """Dynamically draw progress bar frame."""
            progress = t / video_clip.duration
            bar_w = int(W * progress)
            frame = np.zeros((8, W, 4), dtype=np.uint8)
            frame[:, :bar_w, :] = [255, 255, 255, 180]
            return frame

        bar_clip = (
            VideoFileClip.__new__(VideoFileClip)  # placeholder
        )
        # Use a colour clip as a simpler progress bar
        bar_clips = []
        for second in range(int(video_clip.duration)):
            bar_w = max(1, int(W * second / video_clip.duration))
            bar = (
                ColorClip(size=(bar_w, 6), color=[255, 255, 255])
                .set_opacity(0.7)
                .set_start(second)
                .set_duration(1)
                .set_position((0, H - 10))
            )
            bar_clips.append(bar)

        all_overlays = [video_clip] + overlays + bar_clips
        return CompositeVideoClip(all_overlays, size=(W, H))

    def add_intro_animation(self, video_clip, location_name: str):
        """
        Prepend a 2-second black-screen intro with the location name revealed
        letter by letter.

        Args:
            video_clip:    Main video clip.
            location_name: Text to reveal.

        Returns:
            Modified clip with intro prepended.
        """
        if not MOVIEPY_AVAILABLE or video_clip is None:
            return video_clip

        bg = ColorClip(size=(W, H), color=[0, 0, 0]).set_duration(2)
        title = (
            TextClip(location_name.upper(), fontsize=80, color="#FFD700",
                     font="DejaVu-Sans-Bold", method="label")
            .set_position("center")
            .set_duration(2)
            .crossfadein(0.5)
        )
        intro = CompositeVideoClip([bg, title], size=(W, H))
        result = concatenate_videoclips([intro, video_clip], method="compose")
        logger.info("Intro animation added")
        return result

    def add_outro_animation(self, video_clip, call_to_action: str):
        """
        Append a 3-second dark outro with the call-to-action text.

        Args:
            video_clip:      Main video clip.
            call_to_action:  CTA string.

        Returns:
            Modified clip with outro appended.
        """
        if not MOVIEPY_AVAILABLE or video_clip is None:
            return video_clip

        bg = ColorClip(size=(W, H), color=[10, 10, 10]).set_duration(3)
        cta = (
            TextClip(call_to_action, fontsize=52, color="white",
                     font="DejaVu-Sans-Bold", method="caption", size=(W - 100, None))
            .set_position("center")
            .set_duration(3)
            .crossfadein(0.4)
        )
        follow = (
            TextClip("👆 Follow for more travel content!", fontsize=36, color="#FFD700",
                     font="DejaVu-Sans", method="caption", size=(W - 100, None))
            .set_position(("center", H // 2 + 80))
            .set_duration(3)
            .crossfadein(0.6)
        )
        outro = CompositeVideoClip([bg, cta, follow], size=(W, H))
        result = concatenate_videoclips([video_clip, outro], method="compose")
        logger.info("Outro animation added")
        return result

    def add_watermark(self, video_clip, channel_name: str):
        """
        Add a semi-transparent watermark to the top-right corner.

        Args:
            video_clip:   Input clip.
            channel_name: Text to display as watermark.

        Returns:
            Clip with watermark.
        """
        if not MOVIEPY_AVAILABLE or video_clip is None:
            return video_clip

        watermark = (
            TextClip(f"© {channel_name}", fontsize=28, color="white",
                     font="DejaVu-Sans", method="label")
            .set_opacity(0.5)
            .set_duration(video_clip.duration)
            .set_position((W - 200, 20))
        )
        return CompositeVideoClip([video_clip, watermark], size=(W, H))

    def export_video(
        self,
        final_clip,
        output_path: str | Path | None = None,
        quality: str = "high",
    ) -> Path:
        """
        Render and export the final video clip.

        Args:
            final_clip:  moviepy clip ready for export.
            output_path: Destination path (auto-generated if None).
            quality:     'high' or 'preview'.

        Returns:
            Path to the exported video file.
        """
        if not MOVIEPY_AVAILABLE or final_clip is None:
            # Return a dummy path when moviepy is not available
            dummy = get_output_path("videos", "video_unavailable.txt")
            dummy.write_text("moviepy not installed – video export skipped")
            return dummy

        if output_path is None:
            fname = timestamped_filename("video", "mp4")
            output_path = get_output_path("videos", fname)
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        settings = {
            "high": dict(codec="libx264", audio_codec="aac",
                         fps=FPS, bitrate="4000k", preset="medium"),
            "preview": dict(codec="libx264", audio_codec="aac",
                            fps=FPS, bitrate="1000k", preset="ultrafast"),
        }
        params = settings.get(quality, settings["high"])

        logger.info(f"Exporting video ({quality}) → {output_path.name}")
        final_clip.write_videofile(
            str(output_path),
            **params,
            logger=None,          # suppress moviepy's own progress output
            threads=4,
        )

        # Also export a low-res preview
        if quality == "high":
            preview_path = output_path.with_name(output_path.stem + "_preview.mp4")
            final_clip.write_videofile(str(preview_path), **settings["preview"],
                                       logger=None, threads=2)
            logger.info(f"Preview exported → {preview_path.name}")

        logger.info(f"✅ Video exported: {output_path}")
        return output_path

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _make_ken_burns_clip(self, image_path: Path, duration: float):
        """
        Apply a slow zoom-in or zoom-out (Ken Burns) effect to an image clip.

        Randomly chooses zoom direction; scale goes from 1.0 to 1.1 or vice-versa.
        """
        zoom_in = random.choice([True, False])
        scale_start = 1.0 if zoom_in else 1.1
        scale_end   = 1.1 if zoom_in else 1.0

        # Pan direction (slight random offset)
        pan_x = random.uniform(-0.03, 0.03)
        pan_y = random.uniform(-0.03, 0.03)

        def make_frame(t):
            """Return a numpy frame for time *t* with Ken Burns applied."""
            progress = t / duration
            scale = scale_start + (scale_end - scale_start) * progress

            img = Image.open(image_path).convert("RGB")
            img = img.resize((W, H), Image.LANCZOS)

            # Compute enlarged size
            sw = int(W * scale)
            sh = int(H * scale)
            img = img.resize((sw, sh), Image.LANCZOS)

            # Pan offset
            ox = int((sw - W) * (0.5 + pan_x * progress))
            oy = int((sh - H) * (0.5 + pan_y * progress))
            ox = max(0, min(ox, sw - W))
            oy = max(0, min(oy, sh - H))
            img = img.crop((ox, oy, ox + W, oy + H))

            return np.array(img)

        clip = VideoClip(make_frame, duration=duration)
        return clip.set_fps(FPS)

    def _apply_colour_grade(self, clip):
        """
        Apply subtle warm colour grading to a clip:
        - Slight saturation boost
        - Slight warmth (more red/yellow)
        """
        def grade_frame(frame):
            img = Image.fromarray(frame)
            img = ImageEnhance.Color(img).enhance(1.2)        # saturation
            img = ImageEnhance.Contrast(img).enhance(1.05)    # slight contrast
            arr = np.array(img, dtype=np.float32)
            # Warm tint: boost R slightly, reduce B slightly
            arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.03, 0, 255)
            arr[:, :, 2] = np.clip(arr[:, :, 2] * 0.97, 0, 255)
            return arr.astype(np.uint8)

        return clip.fl_image(grade_frame)
