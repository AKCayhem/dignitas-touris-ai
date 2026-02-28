"""
main.py – Tourism Agent Pipeline Entry Point
=============================================
Runs the full automated pipeline:
  Trend Discovery → Script → Images → Video → Voice → Music → Publish → Analytics

Usage examples:
  python main.py                          # Full pipeline, publish to all platforms
  python main.py --dry-run                # Full pipeline, skip publishing
  python main.py --platform youtube       # Publish to YouTube only
  python main.py --topic "Tunis beaches"  # Override trend discovery
  python main.py --preview                # Ask for confirmation before publishing
  python main.py --language arabic        # Arabic content
  python main.py --count 3                # Generate 3 videos
  python main.py --schedule               # Run on cron schedule (blocks)
"""

import sys
import asyncio
import argparse
import random
from datetime import datetime
from pathlib import Path

from colorama import init as colorama_init, Fore, Style
from tqdm import tqdm

colorama_init(autoreset=True)

# ── Project imports ───────────────────────────────────────────────────────────
import config
from config import LOCATION, CONTENT_STYLE, SCHEDULE
from utils.logger import logger
from utils.file_manager import ensure_dirs
from utils.scheduler import AgentScheduler
from agents.trend_agent     import TrendDiscoveryAgent
from agents.script_agent    import ScriptWriterAgent
from agents.image_agent     import ImageCollectorAgent
from agents.video_agent     import VideoCreatorAgent
from agents.voice_agent     import VoiceGeneratorAgent
from agents.music_agent     import MusicAgent
from agents.publisher_agent import PublisherAgent
from agents.analytics_agent import AnalyticsAgent


# ── Agent singletons ─────────────────────────────────────────────────────────
trend_agent     = TrendDiscoveryAgent()
script_agent    = ScriptWriterAgent()
image_agent     = ImageCollectorAgent()
video_agent     = VideoCreatorAgent()
voice_agent     = VoiceGeneratorAgent()
music_agent     = MusicAgent()
publisher_agent = PublisherAgent()
analytics_agent = AnalyticsAgent()
scheduler       = AgentScheduler()
publisher_agent.set_scheduler(scheduler)


# ── CLI argument parser ───────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    """Define all command-line flags."""
    parser = argparse.ArgumentParser(
        description="Tourism Agent – Automated Travel Video Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run full pipeline but skip actual publishing (for testing)",
    )
    parser.add_argument(
        "--platform", choices=["youtube", "instagram", "facebook", "telegram"],
        help="Publish to a single platform only",
    )
    parser.add_argument(
        "--topic", type=str,
        help='Override trend discovery with a custom topic',
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="Ask for confirmation before publishing the video",
    )
    parser.add_argument(
        "--language", choices=["en", "arabic", "fr"], default="en",
        help="Content language (default: en)",
    )
    parser.add_argument(
        "--count", type=int, default=1,
        help="Number of videos to generate in batch mode (default: 1)",
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="Run continuously on cron schedule (blocks the process)",
    )
    parser.add_argument(
        "--analytics", action="store_true",
        help="Fetch analytics for recent posts and generate report",
    )
    return parser


# ── Core pipeline ─────────────────────────────────────────────────────────────

async def run_full_pipeline(
    override_topic: str | None = None,
    dry_run: bool = False,
    platform_filter: str | None = None,
    language: str = "en",
) -> dict:
    """
    Execute the complete video production and publishing pipeline.

    Args:
        override_topic:  Use this topic instead of discovering trends.
        dry_run:         Skip publishing if True.
        platform_filter: Only publish to this platform.
        language:        Content language code.

    Returns:
        Dict of {platform: url/status} publish results.
    """
    banner("🚀 Starting Tourism Agent Pipeline")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Step 1: Trend Discovery ───────────────────────────────────────────────
    step("1/10", "Discovering Trends")
    if override_topic:
        best_topic = override_topic
        trends = {"ranked": [{"topic": best_topic, "score": 100}]}
        logger.info(f"Using custom topic: {best_topic}")
    else:
        trends = await trend_agent.discover_all_trends()
        best_topic = trend_agent.get_best_topic(trends)

    hashtags = trend_agent.get_best_hashtags(trends.get("ranked", []))
    step_ok(f"Topic: '{best_topic}'")

    # ── Step 2: Script Writing ────────────────────────────────────────────────
    step("2/10", "Writing Script")
    style = random.choice(CONTENT_STYLE["video_styles"])
    if language == "arabic":
        LOCATION["language"] = "ar"

    script = await script_agent.generate_video_script(
        trend_topic=best_topic,
        location=LOCATION,
        style=style,
    )
    script_paths = script_agent.save_script(script, f"script_{timestamp}")
    step_ok(f"Title: '{script.get('title', 'Untitled')}'")

    # ── Step 3: Image Collection ──────────────────────────────────────────────
    step("3/10", "Collecting Images")
    search_queries = script.get("search_queries") or [
        f"{LOCATION['name']} travel",
        f"{LOCATION['name']} landscape",
        f"Tunisia tourism",
    ]
    images = await image_agent.collect_all_images(
        search_queries=search_queries,
        total_needed=config.VIDEO_CONFIG["images_per_video"],
    )
    thumbnail = image_agent.create_thumbnail(
        images[0],
        script.get("thumbnail_text", f"Visit {LOCATION['name']}!"),
        LOCATION["name"],
    )
    step_ok(f"Collected {len(images)} images")

    # ── Step 4: Text Overlays ─────────────────────────────────────────────────
    step("4/10", "Adding Text Overlays to Images")
    transition_texts = script.get("transition_texts", [""] * len(images))
    images_with_text = []
    for img, text in zip(images, transition_texts):
        processed = image_agent.add_text_overlay(img, text)
        images_with_text.append(processed)
    step_ok(f"Overlays applied to {len(images_with_text)} images")

    # ── Step 5: Voiceover ─────────────────────────────────────────────────────
    step("5/10", "Generating Voiceover")
    voiceover = await voice_agent.generate_voice(script.get("voiceover_script", ""))
    voiceover = voice_agent.adjust_audio_speed(
        voiceover, config.VIDEO_CONFIG["duration_seconds"]
    )
    voiceover = voice_agent.add_voice_effects(voiceover)
    step_ok(f"Voiceover: {voiceover.name}")

    # ── Step 6: Background Music ──────────────────────────────────────────────
    step("6/10", "Sourcing Background Music")
    music = await music_agent.search_pixabay_music(mood="inspiring", genre="cinematic")
    music = music_agent.sync_music_to_video(
        music, config.VIDEO_CONFIG["duration_seconds"] + 5
    )
    step_ok(f"Music: {music.name}")

    # ── Step 7: Mix Audio ─────────────────────────────────────────────────────
    step("7/10", "Mixing Audio")
    final_audio = music_agent.mix_audio(voiceover, music, music_volume=0.15)
    step_ok(f"Mixed audio: {final_audio.name}")

    # ── Step 8: Video Creation ────────────────────────────────────────────────
    step("8/10", "Creating Video")
    base_video = video_agent.create_image_slideshow(images_with_text)

    if base_video is not None:
        video_with_text  = video_agent.add_text_overlays(base_video, script)
        video_with_intro = video_agent.add_intro_animation(
            video_with_text, LOCATION["name"]
        )
        video_with_outro = video_agent.add_outro_animation(
            video_with_intro, CONTENT_STYLE["call_to_action"]
        )
        final_clip = video_agent.add_watermark(video_with_outro, LOCATION["name"])

        # Attach the mixed audio
        try:
            from moviepy.editor import AudioFileClip
            audio_clip = AudioFileClip(str(final_audio))
            final_clip = final_clip.set_audio(audio_clip)
        except Exception as exc:
            logger.warning(f"Audio attachment failed: {exc}")

        video_path = video_agent.export_video(
            final_clip,
            output_path=f"output/videos/tourism_{timestamp}.mp4",
            quality="high",
        )
    else:
        # moviepy unavailable – create a placeholder path
        video_path = Path(f"output/videos/tourism_{timestamp}_placeholder.txt")
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_text("Video creation requires moviepy. Run: pip install moviepy")
        logger.warning("Video creation skipped (moviepy not available)")

    step_ok(f"Video: {video_path.name}")

    # ── Step 9: Preview ───────────────────────────────────────────────────────
    # (handled by caller)

    # ── Step 10: Publish ──────────────────────────────────────────────────────
    step("10/10", "Publishing to Social Media")

    # Build platform-specific captions
    captions = {
        platform: script_agent.adapt_caption_for_platform(
            script.get("description", ""), platform
        )
        for platform in SCHEDULE["platforms"]
    }

    if platform_filter:
        captions = {platform_filter: captions.get(platform_filter, "")}

    if dry_run:
        logger.info(f"{Fore.YELLOW}DRY RUN – skipping actual publishing{Style.RESET_ALL}")
        results = {p: "dry-run" for p in captions}
    else:
        # Apply platform filter to SCHEDULE temporarily
        original_platforms = SCHEDULE["platforms"]
        if platform_filter:
            SCHEDULE["platforms"] = [platform_filter]

        results = await publisher_agent.publish_to_all_platforms(
            video_path=video_path,
            content_data={
                "title":     script.get("title", f"Visit {LOCATION['name']}"),
                "captions":  captions,
                "thumbnail": thumbnail,
                "tags":      hashtags.get("instagram", LOCATION["hashtags"]),
            },
        )
        SCHEDULE["platforms"] = original_platforms

    step_ok(f"Published: {results}")

    # ── Log to analytics DB ───────────────────────────────────────────────────
    analytics_agent.log_content(
        topic=best_topic,
        style=style,
        script_path=script_paths.get("json_path", ""),
        video_path=str(video_path),
        post_ids=results,
    )

    # ── Schedule analytics check in 24 h ─────────────────────────────────────
    scheduler.schedule_analytics(analytics_agent.fetch_all_analytics, results)

    banner("✅ Pipeline Complete!")
    return results


# ── CLI helpers ───────────────────────────────────────────────────────────────

def banner(text: str) -> None:
    print(f"\n{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  {text}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}\n")


def step(num: str, description: str) -> None:
    print(f"\n{Fore.BLUE}[Step {num}]{Style.RESET_ALL} {description} …")


def step_ok(detail: str) -> None:
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} {detail}")


async def run_batch(count: int, args: argparse.Namespace) -> None:
    """Generate and schedule *count* videos."""
    logger.info(f"Batch mode: generating {count} videos")
    for i in range(count):
        logger.info(f"Batch video {i + 1}/{count}")
        try:
            await run_full_pipeline(
                override_topic=args.topic,
                dry_run=args.dry_run,
                platform_filter=args.platform,
                language=args.language,
            )
        except Exception as exc:
            logger.error(f"Batch video {i + 1} failed: {exc}")


async def run_scheduled() -> None:
    """Block and run on cron schedule."""
    banner("⏰ Scheduled Mode")
    logger.info(f"Post times: {SCHEDULE['post_times']} ({SCHEDULE['timezone']})")

    scheduler.start()
    scheduler.schedule_pipeline(
        lambda: asyncio.create_task(run_full_pipeline())
    )
    scheduler.schedule_trend_discovery(
        lambda: asyncio.create_task(trend_agent.discover_all_trends())
    )
    scheduler.schedule_cleanup(
        lambda: None  # Add file cleanup logic here if needed
    )

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    """Main async entry point."""
    parser = build_arg_parser()
    args   = parser.parse_args()

    # Ensure output directories exist
    ensure_dirs()

    # ── Analytics-only mode ───────────────────────────────────────────────────
    if args.analytics:
        banner("📊 Analytics Mode")
        insights = analytics_agent.analyze_performance()
        report   = analytics_agent.generate_report()
        print(f"\n{Fore.GREEN}Report saved: {report}{Style.RESET_ALL}")
        import json
        print(json.dumps(insights, indent=2))
        return

    # ── Scheduled mode ────────────────────────────────────────────────────────
    if args.schedule:
        await run_scheduled()
        return

    # ── Batch mode ────────────────────────────────────────────────────────────
    if args.count > 1:
        await run_batch(args.count, args)
        return

    # ── Single video pipeline ─────────────────────────────────────────────────
    results = await run_full_pipeline(
        override_topic=args.topic,
        dry_run=args.dry_run,
        platform_filter=args.platform,
        language=args.language,
    )

    # Preview confirmation
    if args.preview and not args.dry_run:
        print(f"\n{Fore.YELLOW}Video ready for publishing.{Style.RESET_ALL}")
        confirm = input("Publish now? [y/N] ").strip().lower()
        if confirm != "y":
            logger.info("Publishing cancelled by user")
            return

    print(f"\n{Fore.GREEN}🎉 Done! Results:{Style.RESET_ALL}")
    for platform, url in results.items():
        status = f"{Fore.GREEN}{url}{Style.RESET_ALL}" if url and url != "dry-run" else f"{Fore.YELLOW}{url or 'failed'}{Style.RESET_ALL}"
        print(f"  {platform:12} → {status}")


if __name__ == "__main__":
    asyncio.run(main())
