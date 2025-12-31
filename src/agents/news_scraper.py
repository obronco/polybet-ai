"""News Scraper Agent - Monitors and aggregates news from multiple sources."""

from datetime import datetime, timedelta
from typing import List, Optional

from ..api.news_sources import NewsAggregator
from ..models.news import NewsArticle, NewsQuery, NewsSource
from ..rag.vector_store import vector_store
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class NewsScraperAgent:
    """Agent responsible for scraping and aggregating news from multiple sources."""

    def __init__(
        self,
        newsapi_key: Optional[str] = None,
        tavily_key: Optional[str] = None,
        rss_feeds: Optional[List[str]] = None,
    ):
        """Initialize News Scraper Agent.

        Args:
            newsapi_key: NewsAPI key (defaults to config)
            tavily_key: Tavily API key (defaults to config)
            rss_feeds: List of RSS feed URLs
        """
        self.aggregator = NewsAggregator(
            newsapi_key=newsapi_key,
            tavily_key=tavily_key,
            rss_feeds=rss_feeds,
        )
        self.markets_config = config.markets_config
        logger.info("news_scraper_agent_initialized")

    async def scrape_news(
        self,
        lookback_hours: int = 24,
        max_results_per_source: int = 100,
    ) -> List[NewsArticle]:
        """Scrape news from all configured sources.

        Args:
            lookback_hours: How many hours back to search
            max_results_per_source: Max results per source

        Returns:
            List of NewsArticle objects
        """
        logger.info("scraping_news", lookback_hours=lookback_hours)

        # Build keywords from market config
        keywords = self._get_all_keywords()

        # Create news query
        query = NewsQuery(
            keywords=keywords,
            sources=[NewsSource.NEWSAPI, NewsSource.TAVILY],
            from_date=datetime.now() - timedelta(hours=lookback_hours),
            to_date=datetime.now(),
            max_results=max_results_per_source,
        )

        # Fetch news from all sources
        articles = await self.aggregator.search_all_sources(query)

        # Filter and process articles
        filtered_articles = self._filter_articles(articles)

        # Index in vector store for RAG
        if filtered_articles:
            vector_store.add_news_articles(filtered_articles)

        logger.info(
            "news_scraping_complete",
            total_fetched=len(articles),
            after_filtering=len(filtered_articles),
        )

        return filtered_articles

    async def scrape_category_news(
        self,
        category: str,
        lookback_hours: int = 24,
    ) -> List[NewsArticle]:
        """Scrape news for a specific category.

        Args:
            category: Category name (e.g., 'politics', 'crypto')
            lookback_hours: Hours to look back

        Returns:
            List of NewsArticle objects
        """
        logger.info("scraping_category_news", category=category)

        # Get keywords for this category
        keywords = self._get_category_keywords(category)
        if not keywords:
            logger.warning("no_keywords_for_category", category=category)
            return []

        query = NewsQuery(
            keywords=keywords,
            sources=[NewsSource.NEWSAPI, NewsSource.TAVILY],
            from_date=datetime.now() - timedelta(hours=lookback_hours),
            max_results=50,
        )

        articles = await self.aggregator.search_all_sources(query)

        # Tag articles with category
        for article in articles:
            article.category = category

        # Index in vector store
        if articles:
            vector_store.add_news_articles(articles)

        logger.info(
            "category_news_scraped",
            category=category,
            count=len(articles),
        )

        return articles

    async def scrape_targeted_news(
        self,
        keywords: List[str],
        lookback_hours: int = 12,
    ) -> List[NewsArticle]:
        """Scrape news for specific keywords.

        Args:
            keywords: Specific keywords to search for
            lookback_hours: Hours to look back

        Returns:
            List of NewsArticle objects
        """
        logger.info("scraping_targeted_news", keywords=keywords)

        query = NewsQuery(
            keywords=keywords,
            sources=[NewsSource.NEWSAPI, NewsSource.TAVILY],
            from_date=datetime.now() - timedelta(hours=lookback_hours),
            max_results=30,
        )

        articles = await self.aggregator.search_all_sources(query)

        # Index in vector store
        if articles:
            vector_store.add_news_articles(articles)

        logger.info("targeted_news_scraped", count=len(articles))
        return articles

    def _get_all_keywords(self) -> List[str]:
        """Get all keywords from market config.

        Returns:
            List of all keywords across all categories
        """
        all_keywords = []
        focus_keywords = self.markets_config.get("focus_keywords", {})

        for category_keywords in focus_keywords.values():
            all_keywords.extend(category_keywords)

        # Add priority keywords
        priority_keywords = self.markets_config.get("priority_keywords", [])
        all_keywords.extend(priority_keywords)

        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in all_keywords:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique_keywords.append(kw)

        return unique_keywords

    def _get_category_keywords(self, category: str) -> List[str]:
        """Get keywords for a specific category.

        Args:
            category: Category name

        Returns:
            List of keywords for the category
        """
        focus_keywords = self.markets_config.get("focus_keywords", {})
        return focus_keywords.get(category.lower(), [])

    def _filter_articles(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Filter articles based on quality and relevance.

        Args:
            articles: List of articles to filter

        Returns:
            Filtered list of articles
        """
        filtered = []

        for article in articles:
            # Skip if no title or URL
            if not article.title or not article.url:
                continue

            # Skip if too old (beyond lookback)
            if not article.is_recent(hours=48):
                continue

            # Skip if title is too short (likely junk)
            if len(article.title) < 10:
                continue

            # Check for excluded terms (optional)
            exclude_terms = ["sponsored", "advertisement", "promoted"]
            if any(term in article.title.lower() for term in exclude_terms):
                continue

            filtered.append(article)

        return filtered

    async def get_recent_news(
        self,
        hours: int = 24,
        limit: Optional[int] = None,
    ) -> List[NewsArticle]:
        """Get recent news from vector store.

        Args:
            hours: Hours to look back
            limit: Optional limit on results

        Returns:
            List of recent NewsArticle objects
        """
        # This would query the vector store for recent news
        # For now, this is a placeholder
        logger.info("getting_recent_news", hours=hours)
        return []

    def get_breaking_news(self, max_age_hours: int = 2) -> List[NewsArticle]:
        """Get breaking news (very recent).

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            List of breaking news articles
        """
        # Filter for very recent, high-priority news
        logger.info("getting_breaking_news", max_age=max_age_hours)
        return []

    async def monitor_continuous(
        self,
        interval_minutes: int = 15,
        callback=None,
    ) -> None:
        """Continuously monitor news sources at regular intervals.

        Args:
            interval_minutes: Monitoring interval
            callback: Optional callback function for new articles
        """
        import asyncio

        logger.info("starting_continuous_monitoring", interval=interval_minutes)

        while True:
            try:
                articles = await self.scrape_news(
                    lookback_hours=1,  # Only check last hour
                    max_results_per_source=50,
                )

                if callback and articles:
                    await callback(articles)

                # Wait for next interval
                await asyncio.sleep(interval_minutes * 60)

            except Exception as e:
                logger.error("monitoring_error", error=str(e))
                # Wait before retrying
                await asyncio.sleep(60)
