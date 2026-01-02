"""News Pipeline - Handles news scraping and aggregation."""

from typing import List, Optional

from ..agents.news_scraper import NewsScraperAgent
from ..models.news import NewsArticle
from ..utils.logger import get_logger

logger = get_logger(__name__)


class NewsPipeline:
    """Pipeline for fetching and filtering news from multiple sources."""

    def __init__(self, news_scraper: Optional[NewsScraperAgent] = None):
        """Initialize News Pipeline.

        Args:
            news_scraper: News scraper agent (creates default if None)
        """
        self.news_scraper = news_scraper or NewsScraperAgent()
        logger.info("news_pipeline_initialized")

    async def fetch_recent_news(
        self,
        lookback_hours: int = 24,
        max_results_per_source: int = 100,
    ) -> List[NewsArticle]:
        """Fetch recent news from all configured sources.

        Args:
            lookback_hours: How many hours back to search
            max_results_per_source: Max results per source

        Returns:
            List of filtered NewsArticle objects
        """
        logger.info("fetching_recent_news", lookback_hours=lookback_hours)

        try:
            articles = await self.news_scraper.scrape_news(
                lookback_hours=lookback_hours,
                max_results_per_source=max_results_per_source,
            )

            logger.info("news_fetch_complete", count=len(articles))
            return articles

        except Exception as e:
            logger.error("news_fetch_error", error=str(e))
            return []

    async def fetch_category_news(
        self,
        category: str,
        lookback_hours: int = 24,
    ) -> List[NewsArticle]:
        """Fetch news for a specific category.

        Args:
            category: Category name (e.g., 'politics', 'crypto')
            lookback_hours: Hours to look back

        Returns:
            List of category-specific NewsArticle objects
        """
        logger.info("fetching_category_news", category=category)

        try:
            articles = await self.news_scraper.scrape_category_news(
                category=category,
                lookback_hours=lookback_hours,
            )

            logger.info("category_news_complete", category=category, count=len(articles))
            return articles

        except Exception as e:
            logger.error("category_news_error", category=category, error=str(e))
            return []

    async def fetch_targeted_news(
        self,
        keywords: List[str],
        lookback_hours: int = 12,
    ) -> List[NewsArticle]:
        """Fetch news for specific keywords.

        Args:
            keywords: Specific keywords to search for
            lookback_hours: Hours to look back

        Returns:
            List of targeted NewsArticle objects
        """
        logger.info("fetching_targeted_news", keywords=keywords)

        try:
            articles = await self.news_scraper.scrape_targeted_news(
                keywords=keywords,
                lookback_hours=lookback_hours,
            )

            logger.info("targeted_news_complete", count=len(articles))
            return articles

        except Exception as e:
            logger.error("targeted_news_error", error=str(e))
            return []
