"""
Agent 1 – Trend Discovery
Discovers trending travel topics using Google Trends, Reddit, YouTube,
DuckDuckGo and NewsAPI, then ranks them for video production.
"""

import time
import asyncio
from collections import Counter
from typing import Any

import aiohttp
import praw
from pytrends.request import TrendReq
from duckduckgo_search import DDGS
from newsapi import NewsApiClient
from googleapiclient.discovery import build

import config
from utils.logger import logger


class TrendDiscoveryAgent:
    """Discovers trending travel content ideas for a target location."""

    def __init__(self) -> None:
        self.location = config.LOCATION
        self.pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25), retries=2)
        self._reddit: praw.Reddit | None = None
        self._youtube = None
        self._news: NewsApiClient | None = None
        self._init_clients()

    # ── Client initialisation ────────────────────────────────────────────────

    def _init_clients(self) -> None:
        """Initialise optional third-party clients (swallow errors gracefully)."""
        # Reddit
        if config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET:
            try:
                self._reddit = praw.Reddit(
                    client_id=config.REDDIT_CLIENT_ID,
                    client_secret=config.REDDIT_CLIENT_SECRET,
                    user_agent=config.REDDIT_USER_AGENT,
                )
                logger.info("Reddit client initialised")
            except Exception as exc:
                logger.warning(f"Reddit init failed: {exc}")

        # YouTube
        if config.YOUTUBE_CLIENT_ID:
            try:
                # YouTube Data API uses API key, not OAuth for search
                # We use a service-account-style key here
                self._youtube = build(
                    "youtube", "v3",
                    developerKey=config.YOUTUBE_CLIENT_ID,
                    cache_discovery=False,
                )
                logger.info("YouTube client initialised")
            except Exception as exc:
                logger.warning(f"YouTube init failed: {exc}")

        # NewsAPI
        if config.NEWS_API_KEY:
            try:
                self._news = NewsApiClient(api_key=config.NEWS_API_KEY)
                logger.info("NewsAPI client initialised")
            except Exception as exc:
                logger.warning(f"NewsAPI init failed: {exc}")

    # ── Public API ───────────────────────────────────────────────────────────

    async def discover_all_trends(self) -> dict[str, Any]:
        """
        Run all trend sources concurrently and aggregate results.

        Returns:
            Dict with keys: google, reddit, youtube, news, ranked.
        """
        logger.info(f"🔍 Discovering trends for {self.location['name']} …")

        # Run blocking calls in thread pool to keep async
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self.get_google_trends, self.location["keywords"]),
            loop.run_in_executor(None, self.get_reddit_trends),
            loop.run_in_executor(None, self.get_youtube_trends, self.location["name"]),
            loop.run_in_executor(None, self.get_news_trends, self.location["name"]),
            loop.run_in_executor(None, self.get_duckduckgo_trends, self.location["name"]),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        google_trends, reddit_trends, yt_trends, news_trends, ddg_trends = [
            r if not isinstance(r, Exception) else []
            for r in results
        ]

        all_trends = {
            "google": google_trends,
            "reddit": reddit_trends,
            "youtube": yt_trends,
            "news": news_trends,
            "duckduckgo": ddg_trends,
        }
        all_trends["ranked"] = self.analyze_and_rank_trends(all_trends)
        logger.info(f"✅ Trend discovery complete. Top topic: {all_trends['ranked'][0]['topic'] if all_trends['ranked'] else 'N/A'}")
        return all_trends

    def get_best_topic(self, trends: dict) -> str:
        """Return the single best trending topic string."""
        ranked = trends.get("ranked", [])
        return ranked[0]["topic"] if ranked else self.location["keywords"][0]

    # ── Google Trends ─────────────────────────────────────────────────────────

    def get_google_trends(
        self,
        keywords: list[str],
        timeframe: str = "now 7-d",
    ) -> list[dict]:
        """
        Fetch Google Trends interest + rising queries for location keywords.

        Args:
            keywords:  Keywords to analyse (uses first 5; pytrends limit).
            timeframe: pytrends timeframe string.

        Returns:
            List of dicts with keys 'topic' and 'score'.
        """
        results: list[dict] = []
        try:
            kw_list = keywords[:5]
            self.pytrends.build_payload(kw_list, timeframe=timeframe, geo="")
            time.sleep(1)  # Respect rate limit

            # Interest over time
            iot = self.pytrends.interest_over_time()
            if not iot.empty:
                for kw in kw_list:
                    if kw in iot.columns:
                        score = int(iot[kw].mean())
                        results.append({"topic": kw, "score": score, "source": "google_trends"})

            time.sleep(1)
            # Related queries – rising
            related = self.pytrends.related_queries()
            for kw in kw_list:
                rising = related.get(kw, {}).get("rising")
                if rising is not None and not rising.empty:
                    for _, row in rising.head(3).iterrows():
                        results.append({
                            "topic": row["query"],
                            "score": int(row.get("value", 50)),
                            "source": "google_rising",
                        })
            logger.info(f"Google Trends: {len(results)} topics found")
        except Exception as exc:
            logger.warning(f"Google Trends error: {exc}")

        return results

    # ── Reddit ────────────────────────────────────────────────────────────────

    def get_reddit_trends(
        self,
        subreddits: list[str] | None = None,
    ) -> list[dict]:
        """
        Find hot posts on travel subreddits mentioning the target location.

        Args:
            subreddits: List of subreddit names to search.

        Returns:
            List of topic dicts.
        """
        if not self._reddit:
            logger.warning("Reddit client not available; skipping")
            return []

        subreddits = subreddits or ["travel", "solotravel", "backpacking", "tourism"]
        results: list[dict] = []
        location_name = self.location["name"].lower()

        for sub_name in subreddits:
            try:
                sub = self._reddit.subreddit(sub_name)
                for post in sub.hot(limit=10):
                    title_lower = post.title.lower()
                    if location_name in title_lower or self.location["country"].lower() in title_lower:
                        results.append({
                            "topic": post.title,
                            "score": post.score,
                            "source": f"reddit/{sub_name}",
                        })
                time.sleep(0.5)
            except Exception as exc:
                logger.warning(f"Reddit r/{sub_name} error: {exc}")

        logger.info(f"Reddit: {len(results)} relevant posts found")
        return results

    # ── YouTube ───────────────────────────────────────────────────────────────

    def get_youtube_trends(self, location_keyword: str) -> list[dict]:
        """
        Search YouTube for recent travel videos about the location.

        Args:
            location_keyword: Location name to search for.

        Returns:
            List of topic dicts derived from top video titles.
        """
        if not self._youtube:
            logger.warning("YouTube client not available; using DuckDuckGo fallback")
            return self._youtube_via_ddg(location_keyword)

        results: list[dict] = []
        try:
            response = (
                self._youtube.search()
                .list(
                    q=f"{location_keyword} travel guide",
                    part="snippet",
                    type="video",
                    order="viewCount",
                    publishedAfter="2024-01-01T00:00:00Z",
                    maxResults=10,
                    videoDuration="medium",
                )
                .execute()
            )
            for item in response.get("items", []):
                title = item["snippet"]["title"]
                results.append({
                    "topic": title,
                    "score": 70,  # YouTube doesn't return raw view counts in search
                    "source": "youtube",
                    "video_id": item["id"].get("videoId", ""),
                })
            logger.info(f"YouTube: {len(results)} videos found")
        except Exception as exc:
            logger.warning(f"YouTube API error: {exc}")
            results = self._youtube_via_ddg(location_keyword)

        return results

    def _youtube_via_ddg(self, query: str) -> list[dict]:
        """Fallback: scrape YouTube search results via DuckDuckGo."""
        results: list[dict] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:youtube.com {query} travel", max_results=5):
                    results.append({"topic": r["title"], "score": 60, "source": "ddg_yt"})
        except Exception as exc:
            logger.warning(f"DuckDuckGo YouTube fallback error: {exc}")
        return results

    # ── News ──────────────────────────────────────────────────────────────────

    def get_news_trends(self, location_keyword: str) -> list[dict]:
        """
        Fetch recent travel news about the location from NewsAPI.

        Args:
            location_keyword: Location name.

        Returns:
            List of topic dicts.
        """
        if not self._news:
            logger.warning("NewsAPI client not available; skipping")
            return []

        results: list[dict] = []
        try:
            articles = self._news.get_everything(
                q=f"{location_keyword} travel tourism",
                language="en",
                sort_by="publishedAt",
                page_size=20,
            )
            for article in articles.get("articles", []):
                results.append({
                    "topic": article["title"],
                    "score": 65,
                    "source": "newsapi",
                    "url": article.get("url", ""),
                })
            logger.info(f"NewsAPI: {len(results)} articles found")
        except Exception as exc:
            logger.warning(f"NewsAPI error: {exc}")
        return results

    # ── DuckDuckGo ────────────────────────────────────────────────────────────

    def get_duckduckgo_trends(self, location_keyword: str) -> list[dict]:
        """
        Search DuckDuckGo for trending travel content about the location.

        Args:
            location_keyword: Search term.

        Returns:
            List of topic dicts.
        """
        results: list[dict] = []
        queries = [
            f"{location_keyword} travel tips 2024",
            f"best things to do {location_keyword}",
            f"{location_keyword} hidden gems",
        ]
        try:
            with DDGS() as ddgs:
                for q in queries:
                    for r in ddgs.text(q, max_results=5):
                        results.append({
                            "topic": r["title"],
                            "score": 55,
                            "source": "duckduckgo",
                        })
                    time.sleep(0.3)
            logger.info(f"DuckDuckGo: {len(results)} results found")
        except Exception as exc:
            logger.warning(f"DuckDuckGo error: {exc}")
        return results

    # ── Analysis & Ranking ────────────────────────────────────────────────────

    def analyze_and_rank_trends(self, all_trends: dict) -> list[dict]:
        """
        Combine all trend sources, score by frequency + engagement, and return
        the top 3 content ideas.

        Args:
            all_trends: Dict of source → list of topic dicts.

        Returns:
            Top 3 ranked topics as list of dicts.
        """
        # Flatten everything
        flat: list[dict] = []
        for source_list in all_trends.values():
            if isinstance(source_list, list):
                flat.extend(source_list)

        if not flat:
            logger.warning("No trends found; using default location keywords")
            return [{"topic": kw, "score": 50} for kw in self.location["keywords"][:3]]

        # Count keyword frequency across titles
        word_counter: Counter = Counter()
        topic_scores: dict[str, int] = {}
        for item in flat:
            topic = item.get("topic", "")
            score = item.get("score", 50)
            # Accumulate raw scores
            key = topic.lower()[:80]
            topic_scores[key] = topic_scores.get(key, 0) + score
            for word in topic.lower().split():
                if len(word) > 4:
                    word_counter[word] += 1

        # Add frequency bonus
        ranked_items = []
        for item in flat:
            key = item.get("topic", "").lower()[:80]
            base_score = topic_scores.get(key, 50)
            # Bonus: how many of the topic's words are trending
            freq_bonus = sum(word_counter.get(w, 0) for w in key.split() if len(w) > 4)
            final_score = base_score + freq_bonus
            ranked_items.append({
                "topic": item.get("topic", ""),
                "score": final_score,
                "source": item.get("source", "unknown"),
            })

        # Deduplicate and sort
        seen_topics: set[str] = set()
        unique_ranked: list[dict] = []
        for item in sorted(ranked_items, key=lambda x: x["score"], reverse=True):
            key = item["topic"].lower()[:80]
            if key not in seen_topics:
                seen_topics.add(key)
                unique_ranked.append(item)
            if len(unique_ranked) >= 3:
                break

        logger.info(f"Top trend: '{unique_ranked[0]['topic']}' (score {unique_ranked[0]['score']})")
        return unique_ranked

    # ── Hashtag builder ───────────────────────────────────────────────────────

    def get_best_hashtags(self, trends: list[dict]) -> dict[str, list[str]]:
        """
        Build platform-specific hashtag sets combining location tags with
        trending topics.

        Args:
            trends: Ranked trend list from analyze_and_rank_trends().

        Returns:
            Dict of platform → hashtag list.
        """
        base_tags = self.location["hashtags"]
        # Generate extra tags from top trend keywords
        trend_tags: list[str] = []
        for item in trends[:3]:
            words = item["topic"].split()
            for word in words:
                clean = word.strip(".,!?\"'").replace(" ", "")
                if len(clean) > 3:
                    trend_tags.append(f"#{clean.capitalize()}")

        all_tags = list(dict.fromkeys(base_tags + trend_tags))  # deduplicate

        return {
            "instagram": all_tags[:30],
            "youtube":   all_tags[:15],
            "tiktok":    all_tags[:10],
            "facebook":  all_tags[:5],
        }
