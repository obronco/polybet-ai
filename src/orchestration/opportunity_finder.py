"""Opportunity Finder - Correlates news with markets to find trading opportunities."""

from typing import List, Optional

from ..agents.analyst import AnalystAgent
from ..agents.market_intel import MarketIntelligenceAgent
from ..models.market import Market, MarketOpportunity
from ..models.news import NewsArticle
from ..utils.logger import get_logger

logger = get_logger(__name__)


class OpportunityFinder:
    """Finds trading opportunities by correlating news with markets."""

    def __init__(
        self,
        analyst: Optional[AnalystAgent] = None,
        market_intel: Optional[MarketIntelligenceAgent] = None,
    ):
        """Initialize Opportunity Finder.

        Args:
            analyst: Analyst agent (creates default if None)
            market_intel: Market intelligence agent (creates default if None)
        """
        self.analyst = analyst or AnalystAgent()
        self.market_intel = market_intel or MarketIntelligenceAgent()
        logger.info("opportunity_finder_initialized")

    async def find_from_news(
        self,
        news_articles: List[NewsArticle],
        min_relevance: float = 0.5,
        top_k: int = 10,
    ) -> List[MarketOpportunity]:
        """Find market opportunities from news articles.

        Args:
            news_articles: List of news articles to analyze
            min_relevance: Minimum relevance score threshold
            top_k: Maximum number of opportunities to return

        Returns:
            List of MarketOpportunity objects ranked by score
        """
        logger.info(
            "finding_opportunities_from_news",
            num_articles=len(news_articles),
            min_relevance=min_relevance,
        )

        if not news_articles:
            logger.warning("no_news_articles_provided")
            return []

        try:
            # Use analyst to find correlated markets
            opportunities = await self.analyst.find_opportunities_from_news(
                news_articles=news_articles,
                min_relevance=min_relevance,
            )

            # Consolidate and rank
            consolidated = self.analyst.consolidate_opportunities(opportunities)
            ranked = self.analyst.rank_opportunities(consolidated)

            # Return top k
            top_opportunities = ranked[:top_k]

            logger.info(
                "opportunities_found",
                total=len(opportunities),
                consolidated=len(consolidated),
                top_k=len(top_opportunities),
            )

            return top_opportunities

        except Exception as e:
            logger.error("opportunity_finding_error", error=str(e))
            return []

    async def find_from_markets(
        self,
        markets: List[Market],
        min_relevance: float = 0.5,
    ) -> List[MarketOpportunity]:
        """Find opportunities by analyzing existing markets.

        Args:
            markets: List of markets to analyze
            min_relevance: Minimum relevance score threshold

        Returns:
            List of MarketOpportunity objects
        """
        logger.info("finding_opportunities_from_markets", num_markets=len(markets))

        if not markets:
            logger.warning("no_markets_provided")
            return []

        try:
            # Find relevant news for each market
            results = await self.analyst.find_news_for_markets(
                markets=markets,
                min_relevance=min_relevance,
            )

            # Convert to opportunities
            opportunities = []
            for market, news_articles in results:
                if news_articles:
                    # Calculate average relevance as score
                    avg_relevance = sum(1.0 for _ in news_articles) / len(news_articles)

                    opportunity = MarketOpportunity(
                        market=market,
                        relevance_score=avg_relevance,
                        news_context=[article.id for article in news_articles],
                        metadata={
                            "news_count": len(news_articles),
                            "method": "market_to_news",
                        },
                    )
                    opportunities.append(opportunity)

            logger.info("market_opportunities_found", count=len(opportunities))
            return opportunities

        except Exception as e:
            logger.error("market_opportunity_error", error=str(e))
            return []

    async def refresh_and_find(
        self,
        lookback_hours: int = 24,
        min_relevance: float = 0.5,
        top_k: int = 10,
    ) -> List[MarketOpportunity]:
        """Refresh markets and find opportunities.

        This is a convenience method that fetches active markets
        and finds opportunities based on current news.

        Args:
            lookback_hours: Used for fetching recent news if needed
            min_relevance: Minimum relevance score threshold
            top_k: Maximum number of opportunities to return

        Returns:
            List of MarketOpportunity objects
        """
        logger.info("refreshing_and_finding_opportunities")

        try:
            # Fetch active markets
            async with self.market_intel:
                markets = await self.market_intel.get_active_markets(limit=100)

            # Find opportunities from markets
            opportunities = await self.find_from_markets(
                markets=markets,
                min_relevance=min_relevance,
            )

            # Rank and return top k
            ranked = self.analyst.rank_opportunities(opportunities)
            return ranked[:top_k]

        except Exception as e:
            logger.error("refresh_and_find_error", error=str(e))
            return []
