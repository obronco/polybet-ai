"""Market Intelligence Agent - Retrieves and analyzes Polymarket data."""

from decimal import Decimal
from typing import List, Optional

from ..api.gamma import GammaClient
from ..models.market import Market, MarketOpportunity
from ..rag.vector_store import vector_store
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MarketIntelligenceAgent:
    """Agent responsible for retrieving and analyzing market data."""

    def __init__(self):
        """Initialize Market Intelligence Agent."""
        self.gamma_client = GammaClient()
        self.market_filters = config.get_market_filters()
        logger.info("market_intelligence_agent_initialized")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.gamma_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.gamma_client.__aexit__(exc_type, exc_val, exc_tb)

    async def get_active_markets(
        self,
        limit: int = 100,
        apply_filters: bool = True,
    ) -> List[Market]:
        """Get active markets from Polymarket.

        Args:
            limit: Maximum number of markets
            apply_filters: Whether to apply configured filters

        Returns:
            List of Market objects
        """
        logger.info("fetching_active_markets", limit=limit)

        # Fetch markets from Gamma API
        markets = await self.gamma_client.get_markets(
            limit=limit,
            active=True,
            closed=False,
        )

        # Apply filters if requested
        if apply_filters:
            markets = self._filter_markets(markets)

        # Sort by volume (most liquid first)
        markets.sort(key=lambda m: m.volume_24h, reverse=True)

        # Index markets in vector store for RAG
        if markets:
            vector_store.add_markets(markets)

        logger.info(
            "active_markets_fetched",
            total=len(markets),
        )

        return markets

    async def get_markets_by_category(
        self,
        category: str,
        limit: int = 50,
    ) -> List[Market]:
        """Get markets filtered by category.

        Args:
            category: Market category
            limit: Maximum number of markets

        Returns:
            List of Market objects
        """
        logger.info("fetching_category_markets", category=category)

        # Fetch all markets
        all_markets = await self.get_active_markets(limit=limit * 2)

        # Filter by category
        category_markets = [
            m for m in all_markets if m.category.lower() == category.lower()
        ]

        logger.info(
            "category_markets_fetched",
            category=category,
            count=len(category_markets),
        )

        return category_markets[:limit]

    async def search_markets(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Market]:
        """Search for markets matching a query.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching markets
        """
        logger.info("searching_markets", query=query)

        # Use Gamma API search
        markets = await self.gamma_client.search_markets(query, limit=limit)

        # Apply filters
        markets = self._filter_markets(markets)

        logger.info("market_search_complete", query=query, count=len(markets))

        return markets

    async def get_market_details(self, market_id: str) -> Optional[Market]:
        """Get detailed information about a specific market.

        Args:
            market_id: Market identifier

        Returns:
            Market object or None
        """
        logger.info("fetching_market_details", market_id=market_id)

        market = await self.gamma_client.get_market(market_id)

        if market:
            logger.debug("market_details_fetched", market_id=market_id)
        else:
            logger.warning("market_not_found", market_id=market_id)

        return market

    def _filter_markets(self, markets: List[Market]) -> List[Market]:
        """Filter markets based on configured criteria.

        Args:
            markets: List of markets to filter

        Returns:
            Filtered list of markets
        """
        filtered = []

        min_liquidity = Decimal(str(self.market_filters.get("min_liquidity_usd", 0)))
        min_volume_24h = Decimal(
            str(self.market_filters.get("min_volume_24h_usd", 0))
        )
        max_spread = Decimal(str(self.market_filters.get("max_spread", 1.0)))
        min_time_hours = self.market_filters.get("min_time_to_resolution_hours", 0)
        max_time_hours = self.market_filters.get(
            "max_time_to_resolution_hours", 999999
        )
        allowed_categories = self.market_filters.get("categories", [])
        exclude_terms = self.market_filters.get("exclude_markets_containing", [])

        for market in markets:
            # Check if market is active
            if not market.is_active:
                continue

            # Check liquidity
            if market.liquidity < min_liquidity:
                continue

            # Check 24h volume
            if market.volume_24h < min_volume_24h:
                continue

            # Check spread
            if market.spread > max_spread:
                continue

            # Check time to resolution
            time_to_resolution = market.time_to_resolution_hours
            if time_to_resolution < min_time_hours:
                continue
            if time_to_resolution > max_time_hours:
                continue

            # Check category
            if allowed_categories and market.category not in allowed_categories:
                continue

            # Check for excluded terms
            question_lower = market.question.lower()
            if any(term.lower() in question_lower for term in exclude_terms):
                continue

            filtered.append(market)

        logger.debug(
            "markets_filtered",
            original_count=len(markets),
            filtered_count=len(filtered),
        )

        return filtered

    async def find_opportunities(
        self,
        min_liquidity: Optional[Decimal] = None,
        min_edge_hint: Optional[float] = None,
    ) -> List[MarketOpportunity]:
        """Find potential trading opportunities.

        Args:
            min_liquidity: Minimum market liquidity
            min_edge_hint: Minimum suggested edge (for pre-filtering)

        Returns:
            List of MarketOpportunity objects
        """
        logger.info("finding_market_opportunities")

        # Get active markets
        markets = await self.get_active_markets(limit=100)

        opportunities = []
        for market in markets:
            # Additional liquidity filter if specified
            if min_liquidity and market.liquidity < min_liquidity:
                continue

            # Create opportunity object
            opportunity = MarketOpportunity(
                market=market,
                relevance_score=0.5,  # Will be updated by analyst
            )

            opportunities.append(opportunity)

        # Sort by liquidity and volume
        opportunities.sort(
            key=lambda o: (o.market.volume_24h + o.market.liquidity),
            reverse=True,
        )

        logger.info("opportunities_found", count=len(opportunities))

        return opportunities

    async def get_trending_markets(self, limit: int = 20) -> List[Market]:
        """Get trending markets (high recent volume).

        Args:
            limit: Maximum number of markets

        Returns:
            List of trending markets
        """
        logger.info("fetching_trending_markets", limit=limit)

        markets = await self.get_active_markets(limit=limit * 2)

        # Sort by 24h volume
        markets.sort(key=lambda m: m.volume_24h, reverse=True)

        trending = markets[:limit]

        logger.info("trending_markets_fetched", count=len(trending))

        return trending

    async def get_high_liquidity_markets(self, limit: int = 20) -> List[Market]:
        """Get markets with highest liquidity.

        Args:
            limit: Maximum number of markets

        Returns:
            List of high-liquidity markets
        """
        logger.info("fetching_high_liquidity_markets", limit=limit)

        markets = await self.get_active_markets(limit=limit * 2)

        # Sort by liquidity
        markets.sort(key=lambda m: m.liquidity, reverse=True)

        high_liquidity = markets[:limit]

        logger.info("high_liquidity_markets_fetched", count=len(high_liquidity))

        return high_liquidity

    async def refresh_market_index(self) -> int:
        """Refresh the vector store with latest markets.

        Returns:
            Number of markets indexed
        """
        logger.info("refreshing_market_index")

        markets = await self.get_active_markets(limit=500, apply_filters=False)

        count = vector_store.add_markets(markets)

        logger.info("market_index_refreshed", count=count)

        return count

    def get_market_summary(self, market: Market) -> str:
        """Get a text summary of a market.

        Args:
            market: Market object

        Returns:
            Formatted summary string
        """
        return f"""Market: {market.question}
Category: {market.category}
Status: {market.status.value}
YES Price: {market.yes_price:.2%}
Liquidity: ${market.liquidity:,.0f}
Volume (24h): ${market.volume_24h:,.0f}
Time to Resolution: {market.time_to_resolution_hours:.1f} hours
Spread: {market.spread:.2%}"""
