"""News source API clients (NewsAPI, Tavily, RSS)."""

import hashlib
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp
import feedparser
from aiolimiter import AsyncLimiter
from newsapi import NewsApiClient
from tavily import AsyncTavilyClient

from ..models.news import NewsArticle, NewsQuery, NewsSource
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class NewsAPISource:
    """Client for NewsAPI.org."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize NewsAPI client.

        Args:
            api_key: NewsAPI key (defaults to config)
        """
        self.api_key = api_key or config.settings.newsapi_key.get_secret_value()
        self.client = NewsApiClient(api_key=self.api_key)

        # Rate limiter: NewsAPI has 100 requests per day on free tier
        # We'll use a conservative limit from config
        rate_limit = config.settings.api_rate_limit_calls_per_minute
        self.rate_limiter = AsyncLimiter(max_rate=rate_limit, time_period=60)

    async def search_news(
        self,
        keywords: List[str],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        language: str = "en",
        max_results: int = 100,
    ) -> List[NewsArticle]:
        """Search for news articles.

        Args:
            keywords: Search keywords
            from_date: Start date
            to_date: End date
            language: Article language
            max_results: Maximum results

        Returns:
            List of NewsArticle objects
        """
        query = " OR ".join(keywords)

        # Default to last 24 hours if no dates provided
        if not from_date:
            from_date = datetime.now() - timedelta(days=1)
        if not to_date:
            to_date = datetime.now()

        try:
            # Rate limit API calls
            async with self.rate_limiter:
                response = self.client.get_everything(
                    q=query,
                    from_param=from_date.strftime("%Y-%m-%d"),
                    to=to_date.strftime("%Y-%m-%d"),
                    language=language,
                    sort_by="publishedAt",
                    page_size=min(max_results, 100),  # NewsAPI max is 100
                )

            articles = []
            for article_data in response.get("articles", []):
                try:
                    article = self._parse_article(article_data)
                    articles.append(article)
                except Exception as e:
                    logger.warning("newsapi_article_parse_error", error=str(e))

            logger.info("newsapi_search_complete", count=len(articles), query=query)
            return articles

        except Exception as e:
            logger.error("newsapi_search_error", error=str(e))
            return []

    def _parse_article(self, data: dict) -> NewsArticle:
        """Parse NewsAPI article data.

        Args:
            data: Raw article data from NewsAPI

        Returns:
            NewsArticle object
        """
        # Generate unique ID from URL
        article_id = hashlib.md5(data["url"].encode()).hexdigest()

        # Parse published date
        published_at = datetime.fromisoformat(
            data["publishedAt"].replace("Z", "+00:00")
        )

        return NewsArticle(
            id=article_id,
            url=data["url"],
            source=NewsSource.NEWSAPI,
            source_name=data["source"]["name"],
            title=data["title"],
            description=data.get("description"),
            content=data.get("content"),
            author=data.get("author"),
            published_at=published_at,
            image_url=data.get("urlToImage"),
            language="en",
        )


class TavilySource:
    """Client for Tavily AI search."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Tavily client.

        Args:
            api_key: Tavily API key (defaults to config)
        """
        self.api_key = api_key or config.settings.tavily_api_key.get_secret_value()
        self.client = AsyncTavilyClient(api_key=self.api_key) if self.api_key else None

        # Rate limiter: Use conservative limit from config
        rate_limit = config.settings.api_rate_limit_calls_per_minute
        self.rate_limiter = AsyncLimiter(max_rate=rate_limit, time_period=60)

    async def search_news(
        self,
        keywords: List[str],
        max_results: int = 10,
        search_depth: str = "advanced",
    ) -> List[NewsArticle]:
        """Search for news using Tavily.

        Args:
            keywords: Search keywords
            max_results: Maximum results
            search_depth: Search depth (basic/advanced)

        Returns:
            List of NewsArticle objects
        """
        if not self.client:
            logger.warning("tavily_client_not_configured")
            return []

        query = " ".join(keywords)

        try:
            # Rate limit API calls
            async with self.rate_limiter:
                response = await self.client.search(
                    query=query,
                    max_results=max_results,
                    search_depth=search_depth,
                    include_raw_content=True,
                )

            articles = []
            for result in response.get("results", []):
                try:
                    article = self._parse_result(result)
                    articles.append(article)
                except Exception as e:
                    logger.warning("tavily_result_parse_error", error=str(e))

            logger.info("tavily_search_complete", count=len(articles), query=query)
            return articles

        except Exception as e:
            logger.error("tavily_search_error", error=str(e))
            return []

    def _parse_result(self, data: dict) -> NewsArticle:
        """Parse Tavily search result.

        Args:
            data: Raw result data from Tavily

        Returns:
            NewsArticle object
        """
        # Generate unique ID from URL
        article_id = hashlib.md5(data["url"].encode()).hexdigest()

        # Tavily doesn't always provide published date
        published_at = datetime.now()
        if "published_date" in data:
            try:
                published_at = datetime.fromisoformat(data["published_date"])
            except Exception:
                pass

        return NewsArticle(
            id=article_id,
            url=data["url"],
            source=NewsSource.TAVILY,
            source_name=data.get("domain", "Unknown"),
            title=data["title"],
            description=data.get("content", ""),
            content=data.get("raw_content", data.get("content", "")),
            published_at=published_at,
            relevance_score=float(data.get("score", 0.5)),
        )


class RSSSource:
    """RSS feed aggregator."""

    def __init__(self, feed_urls: Optional[List[str]] = None):
        """Initialize RSS source.

        Args:
            feed_urls: List of RSS feed URLs
        """
        self.feed_urls = feed_urls or []

    async def fetch_feeds(
        self,
        max_articles_per_feed: int = 20,
    ) -> List[NewsArticle]:
        """Fetch articles from RSS feeds.

        Args:
            max_articles_per_feed: Maximum articles per feed

        Returns:
            List of NewsArticle objects
        """
        all_articles = []

        async with aiohttp.ClientSession() as session:
            for feed_url in self.feed_urls:
                try:
                    articles = await self._fetch_feed(
                        session, feed_url, max_articles_per_feed
                    )
                    all_articles.extend(articles)
                except Exception as e:
                    logger.error("rss_feed_error", feed_url=feed_url, error=str(e))

        logger.info("rss_fetch_complete", count=len(all_articles))
        return all_articles

    async def _fetch_feed(
        self,
        session: aiohttp.ClientSession,
        feed_url: str,
        max_articles: int,
    ) -> List[NewsArticle]:
        """Fetch a single RSS feed.

        Args:
            session: aiohttp session
            feed_url: RSS feed URL
            max_articles: Maximum articles to fetch

        Returns:
            List of NewsArticle objects
        """
        try:
            async with session.get(feed_url) as response:
                content = await response.text()
                feed = feedparser.parse(content)

                articles = []
                for entry in feed.entries[:max_articles]:
                    try:
                        article = self._parse_entry(entry, feed.feed)
                        articles.append(article)
                    except Exception as e:
                        logger.warning("rss_entry_parse_error", error=str(e))

                return articles

        except Exception as e:
            logger.error("rss_fetch_error", feed_url=feed_url, error=str(e))
            return []

    def _parse_entry(self, entry: dict, feed_info: dict) -> NewsArticle:
        """Parse RSS feed entry.

        Args:
            entry: Feed entry
            feed_info: Feed metadata

        Returns:
            NewsArticle object
        """
        # Generate unique ID from URL
        article_id = hashlib.md5(entry.link.encode()).hexdigest()

        # Parse published date
        published_at = datetime.now()
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            from time import mktime

            published_at = datetime.fromtimestamp(mktime(entry.published_parsed))

        # Get content
        content = entry.get("summary", "")
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].value

        return NewsArticle(
            id=article_id,
            url=entry.link,
            source=NewsSource.RSS,
            source_name=feed_info.get("title", "RSS Feed"),
            title=entry.title,
            description=entry.get("summary", ""),
            content=content,
            author=entry.get("author"),
            published_at=published_at,
        )


class NewsAggregator:
    """Aggregates news from multiple sources."""

    def __init__(
        self,
        newsapi_key: Optional[str] = None,
        tavily_key: Optional[str] = None,
        rss_feeds: Optional[List[str]] = None,
    ):
        """Initialize news aggregator.

        Args:
            newsapi_key: NewsAPI key
            tavily_key: Tavily API key
            rss_feeds: RSS feed URLs
        """
        self.newsapi = NewsAPISource(newsapi_key)
        self.tavily = TavilySource(tavily_key)
        self.rss = RSSSource(rss_feeds or [])

    async def search_all_sources(
        self,
        query: NewsQuery,
    ) -> List[NewsArticle]:
        """Search all configured news sources.

        Args:
            query: NewsQuery object with search parameters

        Returns:
            Aggregated list of NewsArticle objects
        """
        all_articles = []

        # Search NewsAPI
        if NewsSource.NEWSAPI in query.sources:
            try:
                newsapi_articles = await self.newsapi.search_news(
                    keywords=query.keywords,
                    from_date=query.from_date,
                    to_date=query.to_date,
                    max_results=query.max_results,
                )
                all_articles.extend(newsapi_articles)
            except Exception as e:
                logger.error("newsapi_search_failed", error=str(e))

        # Search Tavily
        if NewsSource.TAVILY in query.sources and self.tavily.client:
            try:
                tavily_articles = await self.tavily.search_news(
                    keywords=query.keywords,
                    max_results=min(query.max_results, 10),
                )
                all_articles.extend(tavily_articles)
            except Exception as e:
                logger.error("tavily_search_failed", error=str(e))

        # Fetch RSS feeds
        if NewsSource.RSS in query.sources and self.rss.feed_urls:
            try:
                rss_articles = await self.rss.fetch_feeds()
                all_articles.extend(rss_articles)
            except Exception as e:
                logger.error("rss_fetch_failed", error=str(e))

        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if str(article.url) not in seen_urls:
                seen_urls.add(str(article.url))
                unique_articles.append(article)

        logger.info(
            "news_aggregation_complete",
            total=len(all_articles),
            unique=len(unique_articles),
        )

        return unique_articles
