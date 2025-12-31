"""Analyst Agent - Correlates news events with relevant markets."""

from typing import List, Tuple

from ..models.market import Market, MarketOpportunity
from ..models.news import NewsArticle
from ..rag.vector_store import vector_store
from ..utils.llm import llm_client
from ..utils.logger import get_logger
from ..utils.prompts import build_news_context

logger = get_logger(__name__)


class AnalystAgent:
    """Agent responsible for analyzing news-market correlations."""

    def __init__(self):
        """Initialize Analyst Agent."""
        logger.info("analyst_agent_initialized")

    async def analyze_news_market_correlation(
        self,
        news_article: NewsArticle,
        markets: List[Market],
        top_k: int = 5,
    ) -> List[MarketOpportunity]:
        """Analyze how a news article correlates with markets.

        Args:
            news_article: NewsArticle object
            markets: List of Market objects to analyze
            top_k: Return top K most relevant markets

        Returns:
            List of MarketOpportunity objects ranked by relevance
        """
        logger.info(
            "analyzing_news_market_correlation",
            article_id=news_article.id,
            num_markets=len(markets),
        )

        opportunities = []

        for market in markets:
            # Use LLM to analyze relevance
            relevance_data = await llm_client.analyze_news_relevance(
                news_summary=f"{news_article.title}\n\n{news_article.description or ''}",
                market_question=market.question,
            )

            relevance_score = relevance_data.get("relevance", 0.0)

            # Only include if relevance meets threshold
            if relevance_score >= 0.3:
                opportunity = MarketOpportunity(
                    market=market,
                    relevance_score=relevance_score,
                    news_context=[news_article.id],
                    metadata={
                        "impact_direction": relevance_data.get("impact", "unclear"),
                        "explanation": relevance_data.get("explanation", ""),
                    },
                )
                opportunities.append(opportunity)

        # Sort by relevance
        opportunities.sort(key=lambda o: o.relevance_score, reverse=True)

        logger.info(
            "correlation_analysis_complete",
            relevant_markets=len(opportunities),
            top_relevance=(
                opportunities[0].relevance_score if opportunities else 0
            ),
        )

        return opportunities[:top_k]

    async def find_opportunities_from_news(
        self,
        news_articles: List[NewsArticle],
        min_relevance: float = 0.5,
    ) -> List[MarketOpportunity]:
        """Find market opportunities based on news articles.

        Args:
            news_articles: List of news articles
            min_relevance: Minimum relevance score

        Returns:
            List of MarketOpportunity objects
        """
        logger.info(
            "finding_opportunities_from_news",
            num_articles=len(news_articles),
        )

        all_opportunities = []

        for article in news_articles:
            # Use RAG to find related markets
            related_markets = vector_store.find_markets_for_news(
                article,
                top_k=10,
                min_relevance=min_relevance,
            )

            for market_data in related_markets:
                # Create opportunity
                opportunity = MarketOpportunity(
                    market=Market(**market_data["metadata"]),
                    relevance_score=market_data["relevance_score"],
                    news_context=[article.id],
                    metadata={
                        "news_title": article.title,
                        "news_source": article.source.value,
                        "published_at": article.published_at.isoformat(),
                    },
                )
                all_opportunities.append(opportunity)

        # Consolidate opportunities (same market, multiple news articles)
        consolidated = self._consolidate_opportunities(all_opportunities)

        # Sort by relevance
        consolidated.sort(key=lambda o: o.relevance_score, reverse=True)

        logger.info(
            "opportunities_from_news_found",
            total=len(all_opportunities),
            consolidated=len(consolidated),
        )

        return consolidated

    async def find_news_for_markets(
        self,
        markets: List[Market],
        min_relevance: float = 0.5,
    ) -> List[Tuple[Market, List[NewsArticle]]]:
        """Find relevant news for each market.

        Args:
            markets: List of markets
            min_relevance: Minimum relevance score

        Returns:
            List of tuples (Market, relevant news articles)
        """
        logger.info("finding_news_for_markets", num_markets=len(markets))

        results = []

        for market in markets:
            # Use RAG to find relevant news
            relevant_news_data = vector_store.find_news_for_market(
                market,
                top_k=10,
                min_relevance=min_relevance,
            )

            # Reconstruct NewsArticle objects from metadata
            news_articles = []
            for news_data in relevant_news_data:
                metadata = news_data["metadata"]
                # Create minimal NewsArticle (in production, fetch full data)
                article = NewsArticle(
                    id=news_data["id"],
                    url=metadata["url"],
                    source=metadata["source"],
                    source_name=metadata["source_name"],
                    title=metadata["title"],
                    published_at=metadata["published_at"],
                    relevance_score=news_data["relevance_score"],
                )
                news_articles.append(article)

            if news_articles:
                results.append((market, news_articles))

        logger.info(
            "news_for_markets_found",
            markets_with_news=len(results),
        )

        return results

    def _consolidate_opportunities(
        self,
        opportunities: List[MarketOpportunity],
    ) -> List[MarketOpportunity]:
        """Consolidate opportunities for the same market.

        Args:
            opportunities: List of opportunities

        Returns:
            Consolidated list
        """
        market_opps = {}

        for opp in opportunities:
            market_id = opp.market.id

            if market_id not in market_opps:
                market_opps[market_id] = opp
            else:
                # Merge news context
                existing = market_opps[market_id]
                existing.news_context.extend(opp.news_context)
                # Average relevance scores
                existing.relevance_score = (
                    existing.relevance_score + opp.relevance_score
                ) / 2

        return list(market_opps.values())

    async def evaluate_market_impact(
        self,
        news_article: NewsArticle,
        market: Market,
    ) -> dict:
        """Evaluate how news impacts a specific market.

        Args:
            news_article: NewsArticle object
            market: Market object

        Returns:
            Dict with impact analysis
        """
        logger.info(
            "evaluating_market_impact",
            article=news_article.title[:50],
            market=market.question[:50],
        )

        # Use LLM for detailed impact analysis
        result = await llm_client.analyze_news_relevance(
            news_summary=(
                f"Title: {news_article.title}\n"
                f"Source: {news_article.source_name}\n"
                f"Published: {news_article.published_at}\n"
                f"Content: {news_article.description or ''}"
            ),
            market_question=market.question,
        )

        impact = {
            "relevance_score": result.get("relevance", 0.0),
            "impact_direction": result.get("impact", "unclear"),
            "explanation": result.get("explanation", ""),
            "should_update_probability": result.get("relevance", 0) > 0.6,
        }

        logger.debug("market_impact_evaluated", **impact)

        return impact

    async def rank_opportunities(
        self,
        opportunities: List[MarketOpportunity],
    ) -> List[MarketOpportunity]:
        """Rank opportunities by multiple factors.

        Args:
            opportunities: List of opportunities

        Returns:
            Sorted list of opportunities
        """
        logger.info("ranking_opportunities", count=len(opportunities))

        # Score each opportunity
        for opp in opportunities:
            score = self._calculate_opportunity_score(opp)
            opp.metadata["composite_score"] = score

        # Sort by composite score
        opportunities.sort(
            key=lambda o: o.metadata.get("composite_score", 0),
            reverse=True,
        )

        logger.info("opportunities_ranked")

        return opportunities

    def _calculate_opportunity_score(self, opp: MarketOpportunity) -> float:
        """Calculate composite opportunity score.

        Args:
            opp: MarketOpportunity object

        Returns:
            Composite score (0-1)
        """
        # Factors:
        # 1. Relevance score (0-1)
        # 2. Market liquidity (normalized)
        # 3. News recency (normalized)
        # 4. Number of news articles

        relevance_weight = 0.4
        liquidity_weight = 0.3
        recency_weight = 0.2
        volume_weight = 0.1

        # Relevance score
        relevance_score = opp.relevance_score

        # Liquidity score (log scale, normalized to 0-1)
        import math

        liquidity = float(opp.market.liquidity)
        liquidity_score = min(1.0, math.log10(max(1, liquidity)) / 6)

        # Recency score (assume recent news, score = 1 for now)
        recency_score = 1.0

        # Volume score
        volume = float(opp.market.volume_24h)
        volume_score = min(1.0, math.log10(max(1, volume)) / 6)

        composite_score = (
            relevance_score * relevance_weight
            + liquidity_score * liquidity_weight
            + recency_score * recency_weight
            + volume_score * volume_weight
        )

        return composite_score
