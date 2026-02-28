"""
Agent 8 – Analytics
Fetches post metrics from YouTube and Instagram, stores them in SQLite,
analyses performance trends, and generates weekly HTML/JSON reports.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import requests

import config
from utils.logger import logger
from utils.file_manager import get_output_path

DB_PATH = Path(__file__).parent.parent / "logs" / "analytics.db"


class AnalyticsAgent:
    """Tracks video performance across all publishing platforms."""

    def __init__(self) -> None:
        self._init_db()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TourismAgent/1.0"})
        logger.info("AnalyticsAgent ready")

    # ── Database ─────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create the SQLite database schema if it doesn't exist."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform     TEXT    NOT NULL,
                    post_id      TEXT    NOT NULL,
                    date         TEXT    NOT NULL,
                    metrics_json TEXT    NOT NULL,
                    topic        TEXT,
                    UNIQUE(platform, post_id, date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at   TEXT    NOT NULL,
                    topic        TEXT,
                    style        TEXT,
                    script_path  TEXT,
                    video_path   TEXT,
                    post_ids     TEXT
                )
            """)
            conn.commit()

    def store_metrics(
        self,
        platform: str,
        post_id: str,
        metrics: dict,
        topic: str = "",
    ) -> bool:
        """
        Persist metrics for a post to the local SQLite database.

        Args:
            platform: Platform name.
            post_id:  Platform-specific post/video ID.
            metrics:  Dict of metric name → value.
            topic:    Video topic string.

        Returns:
            True on success.
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO performance
                        (platform, post_id, date, metrics_json, topic)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        platform,
                        post_id,
                        datetime.now().strftime("%Y-%m-%d"),
                        json.dumps(metrics),
                        topic,
                    ),
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"DB write failed: {exc}")
            return False

    def log_content(
        self,
        topic: str,
        style: str,
        script_path: str,
        video_path: str,
        post_ids: dict,
    ) -> None:
        """Record a newly published video to the content log."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    """
                    INSERT INTO content (created_at, topic, style, script_path, video_path, post_ids)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now().isoformat(),
                        topic,
                        style,
                        script_path,
                        video_path,
                        json.dumps(post_ids),
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.warning(f"Content log failed: {exc}")

    # ── Platform metric fetchers ──────────────────────────────────────────────

    def fetch_youtube_analytics(self, video_id: str) -> dict:
        """
        Fetch views, likes, comments, and watch time for a YouTube video.

        Args:
            video_id: YouTube video ID.

        Returns:
            Metrics dict.
        """
        if not all([config.YOUTUBE_CLIENT_ID, config.YOUTUBE_REFRESH_TOKEN]):
            return {}

        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials

            creds = Credentials(
                token=None,
                refresh_token=config.YOUTUBE_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=config.YOUTUBE_CLIENT_ID,
                client_secret=config.YOUTUBE_CLIENT_SECRET,
            )
            youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

            resp = (
                youtube.videos()
                .list(part="statistics", id=video_id)
                .execute()
            )
            items = resp.get("items", [])
            if not items:
                return {}

            stats = items[0]["statistics"]
            metrics = {
                "views":    int(stats.get("viewCount", 0)),
                "likes":    int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "fetched":  datetime.now().isoformat(),
            }
            self.store_metrics("youtube", video_id, metrics)
            logger.info(f"YouTube metrics: {metrics}")
            return metrics

        except Exception as exc:
            logger.warning(f"YouTube analytics error: {exc}")
            return {}

    def fetch_instagram_analytics(self, post_id: str) -> dict:
        """
        Fetch reach, impressions, saves, and shares for an Instagram post.

        Args:
            post_id: Instagram media ID.

        Returns:
            Metrics dict.
        """
        if not all([config.INSTAGRAM_ACCESS_TOKEN, config.INSTAGRAM_PAGE_ID]):
            return {}

        try:
            resp = self.session.get(
                f"https://graph.facebook.com/v18.0/{post_id}/insights",
                params={
                    "metric":       "reach,impressions,saved,shares,profile_visits",
                    "access_token": config.INSTAGRAM_ACCESS_TOKEN,
                },
                timeout=10,
            )
            resp.raise_for_status()
            raw = resp.json().get("data", [])
            metrics = {item["name"]: item.get("values", [{}])[0].get("value", 0) for item in raw}
            metrics["fetched"] = datetime.now().isoformat()
            self.store_metrics("instagram", post_id, metrics)
            logger.info(f"Instagram metrics: {metrics}")
            return metrics

        except Exception as exc:
            logger.warning(f"Instagram analytics error: {exc}")
            return {}

    async def fetch_all_analytics(self, post_ids: dict) -> dict:
        """
        Fetch analytics for all platforms and return combined results.

        Args:
            post_ids: Dict of platform → post_id/URL.

        Returns:
            Dict of platform → metrics.
        """
        results = {}
        for platform, pid in post_ids.items():
            if pid is None:
                continue
            try:
                if platform == "youtube":
                    vid = str(pid).split("v=")[-1] if "youtube.com" in str(pid) else str(pid)
                    results["youtube"] = self.fetch_youtube_analytics(vid)
                elif platform == "instagram":
                    results["instagram"] = self.fetch_instagram_analytics(str(pid))
            except Exception as exc:
                logger.warning(f"Analytics fetch error for {platform}: {exc}")
        return results

    # ── Performance analysis ──────────────────────────────────────────────────

    def analyze_performance(self) -> dict:
        """
        Compute aggregate statistics and identify top performing content.

        Returns:
            Insights dict with averages, best topics, and best posting times.
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT platform, metrics_json, topic, date FROM performance "
                    "ORDER BY date DESC LIMIT 200"
                ).fetchall()
        except Exception as exc:
            logger.error(f"Analytics query failed: {exc}")
            return {}

        if not rows:
            return {"status": "no data yet"}

        platform_metrics: dict[str, list] = {}
        topic_scores: dict[str, list]    = {}

        for platform, metrics_json, topic, date in rows:
            try:
                m = json.loads(metrics_json)
            except Exception:
                continue

            platform_metrics.setdefault(platform, []).append(m)
            if topic:
                views = m.get("views", m.get("reach", 0))
                topic_scores.setdefault(topic, []).append(views)

        # Average views per platform
        avg_views = {}
        for plat, metrics_list in platform_metrics.items():
            vals = [m.get("views", m.get("reach", 0)) for m in metrics_list]
            avg_views[plat] = sum(vals) / len(vals) if vals else 0

        # Best topics
        best_topics = sorted(
            {t: sum(v) / len(v) for t, v in topic_scores.items()}.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        insights = {
            "avg_views_per_platform": avg_views,
            "best_topics": [{"topic": t, "avg_views": round(v, 1)} for t, v in best_topics],
            "total_posts_analysed": len(rows),
            "generated_at": datetime.now().isoformat(),
        }
        logger.info(f"Performance insights generated: {insights}")
        return insights

    def generate_report(self) -> Path:
        """
        Create a weekly performance report as both JSON and HTML.

        Returns:
            Path to the HTML report file.
        """
        insights = self.analyze_performance()

        # JSON
        json_path = get_output_path("reports", f"report_{datetime.now().strftime('%Y_%W')}.json")
        json_path.write_text(json.dumps(insights, indent=2))

        # HTML
        html_path = json_path.with_suffix(".html")
        html_path.write_text(self._render_html_report(insights))

        logger.info(f"Report saved: {html_path.name}")
        return html_path

    def update_content_strategy(self, insights: dict) -> dict:
        """
        Propose strategy adjustments based on analytics insights.

        Args:
            insights: Dict from analyze_performance().

        Returns:
            Updated strategy recommendations.
        """
        strategy = {
            "recommended_styles": [],
            "best_post_times": config.SCHEDULE["post_times"],
            "top_hashtags": config.LOCATION["hashtags"][:10],
        }

        best_topics = insights.get("best_topics", [])
        for item in best_topics[:3]:
            topic = item.get("topic", "")
            # Map topic to a video style
            for style in config.CONTENT_STYLE["video_styles"]:
                if any(word in topic.lower() for word in style.lower().split()):
                    strategy["recommended_styles"].append(style)
                    break

        if not strategy["recommended_styles"]:
            strategy["recommended_styles"] = config.CONTENT_STYLE["video_styles"][:3]

        logger.info(f"Strategy updated: {strategy}")
        return strategy

    # ── HTML rendering ────────────────────────────────────────────────────────

    @staticmethod
    def _render_html_report(insights: dict) -> str:
        """Render insights dict as a simple HTML report."""
        avg = insights.get("avg_views_per_platform", {})
        best = insights.get("best_topics", [])

        platform_rows = "".join(
            f"<tr><td>{p}</td><td>{v:,.0f}</td></tr>" for p, v in avg.items()
        )
        topic_rows = "".join(
            f"<tr><td>{t['topic'][:80]}</td><td>{t['avg_views']:,.0f}</td></tr>"
            for t in best
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Tourism Agent – Weekly Analytics Report</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; color: #333; }}
  h1   {{ color: #1a73e8; }}
  table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
  th {{ background: #f2f2f2; }}
  .stat {{ background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 10px; display: inline-block; }}
</style>
</head>
<body>
<h1>🌍 Tourism Agent – Weekly Report</h1>
<p>Generated: {insights.get('generated_at', 'N/A')} &nbsp;|&nbsp;
   Posts analysed: {insights.get('total_posts_analysed', 0)}</p>

<h2>Average Views per Platform</h2>
<table><tr><th>Platform</th><th>Avg Views</th></tr>{platform_rows}</table>

<h2>Top Performing Topics</h2>
<table><tr><th>Topic</th><th>Avg Views</th></tr>{topic_rows}</table>
</body>
</html>"""
