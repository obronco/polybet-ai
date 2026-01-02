"""Market filtering strategies using the Chain of Responsibility pattern."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List

from ..models.market import Market
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MarketFilter(ABC):
    """Abstract base class for market filters."""

    @abstractmethod
    def filter(self, market: Market) -> bool:
        """Determine if market passes this filter.

        Args:
            market: Market to evaluate

        Returns:
            True if market passes filter, False otherwise
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get human-readable description of this filter.

        Returns:
            Filter description
        """
        pass


class ActiveMarketFilter(MarketFilter):
    """Filter for active markets only."""

    def filter(self, market: Market) -> bool:
        """Check if market is active."""
        return market.is_active

    def get_description(self) -> str:
        return "Market must be active"


class LiquidityFilter(MarketFilter):
    """Filter markets by minimum liquidity."""

    def __init__(self, min_liquidity: Decimal):
        """Initialize liquidity filter.

        Args:
            min_liquidity: Minimum required liquidity in USD
        """
        self.min_liquidity = min_liquidity

    def filter(self, market: Market) -> bool:
        """Check if market meets minimum liquidity."""
        return market.liquidity >= self.min_liquidity

    def get_description(self) -> str:
        return f"Liquidity >= ${float(self.min_liquidity):,.0f}"


class VolumeFilter(MarketFilter):
    """Filter markets by minimum 24h volume."""

    def __init__(self, min_volume_24h: Decimal):
        """Initialize volume filter.

        Args:
            min_volume_24h: Minimum required 24h volume in USD
        """
        self.min_volume_24h = min_volume_24h

    def filter(self, market: Market) -> bool:
        """Check if market meets minimum volume."""
        return market.volume_24h >= self.min_volume_24h

    def get_description(self) -> str:
        return f"24h Volume >= ${float(self.min_volume_24h):,.0f}"


class SpreadFilter(MarketFilter):
    """Filter markets by maximum spread."""

    def __init__(self, max_spread: Decimal):
        """Initialize spread filter.

        Args:
            max_spread: Maximum allowed spread (0-1)
        """
        self.max_spread = max_spread

    def filter(self, market: Market) -> bool:
        """Check if market spread is within limit."""
        return market.spread <= self.max_spread

    def get_description(self) -> str:
        return f"Spread <= {float(self.max_spread):.1%}"


class TimeToResolutionFilter(MarketFilter):
    """Filter markets by time to resolution range."""

    def __init__(self, min_hours: int, max_hours: int):
        """Initialize time to resolution filter.

        Args:
            min_hours: Minimum hours until resolution
            max_hours: Maximum hours until resolution
        """
        self.min_hours = min_hours
        self.max_hours = max_hours

    def filter(self, market: Market) -> bool:
        """Check if time to resolution is in range."""
        time_to_res = market.time_to_resolution_hours
        return self.min_hours <= time_to_res <= self.max_hours

    def get_description(self) -> str:
        return f"Time to resolution: {self.min_hours}-{self.max_hours} hours"


class CategoryFilter(MarketFilter):
    """Filter markets by allowed categories."""

    def __init__(self, allowed_categories: List[str]):
        """Initialize category filter.

        Args:
            allowed_categories: List of allowed category names
        """
        self.allowed_categories = allowed_categories

    def filter(self, market: Market) -> bool:
        """Check if market category is allowed."""
        if not self.allowed_categories:
            return True  # No restriction if list is empty
        return market.category in self.allowed_categories

    def get_description(self) -> str:
        if not self.allowed_categories:
            return "All categories allowed"
        return f"Categories: {', '.join(self.allowed_categories)}"


class ExcludeTermsFilter(MarketFilter):
    """Filter out markets containing specific terms."""

    def __init__(self, exclude_terms: List[str]):
        """Initialize exclude terms filter.

        Args:
            exclude_terms: List of terms to exclude
        """
        self.exclude_terms = [term.lower() for term in exclude_terms]

    def filter(self, market: Market) -> bool:
        """Check if market question contains excluded terms."""
        if not self.exclude_terms:
            return True  # No exclusions if list is empty

        question_lower = market.question.lower()
        return not any(term in question_lower for term in self.exclude_terms)

    def get_description(self) -> str:
        if not self.exclude_terms:
            return "No excluded terms"
        return f"Excludes: {', '.join(self.exclude_terms)}"


class MarketFilterChain:
    """Chain of filters to apply to markets."""

    def __init__(self, filters: List[MarketFilter]):
        """Initialize filter chain.

        Args:
            filters: List of filters to apply in sequence
        """
        self.filters = filters

    def filter_markets(self, markets: List[Market]) -> List[Market]:
        """Apply all filters in the chain to markets.

        Args:
            markets: List of markets to filter

        Returns:
            Filtered list of markets
        """
        filtered = []
        filter_stats = {f.get_description(): 0 for f in self.filters}
        filter_stats["total_input"] = len(markets)

        for market in markets:
            passed = True
            for filter_obj in self.filters:
                if not filter_obj.filter(market):
                    filter_stats[filter_obj.get_description()] += 1
                    passed = False
                    break

            if passed:
                filtered.append(market)

        filter_stats["total_output"] = len(filtered)
        filter_stats["total_filtered"] = len(markets) - len(filtered)

        logger.debug("market_filtering_complete", **filter_stats)

        return filtered

    def add_filter(self, filter_obj: MarketFilter) -> None:
        """Add a filter to the chain.

        Args:
            filter_obj: Filter to add
        """
        self.filters.append(filter_obj)

    def get_filter_descriptions(self) -> List[str]:
        """Get descriptions of all filters in the chain.

        Returns:
            List of filter descriptions
        """
        return [f.get_description() for f in self.filters]


def create_filter_chain_from_config(config: dict) -> MarketFilterChain:
    """Create a filter chain from configuration dict.

    Args:
        config: Configuration dictionary with filter parameters

    Returns:
        Configured MarketFilterChain
    """
    filters = []

    # Always filter for active markets
    filters.append(ActiveMarketFilter())

    # Liquidity filter
    if config.get("min_liquidity_usd", 0) > 0:
        min_liquidity = Decimal(str(config["min_liquidity_usd"]))
        filters.append(LiquidityFilter(min_liquidity))

    # Volume filter
    if config.get("min_volume_24h_usd", 0) > 0:
        min_volume = Decimal(str(config["min_volume_24h_usd"]))
        filters.append(VolumeFilter(min_volume))

    # Spread filter
    if "max_spread" in config:
        max_spread = Decimal(str(config["max_spread"]))
        filters.append(SpreadFilter(max_spread))

    # Time to resolution filter
    min_hours = config.get("min_time_to_resolution_hours", 0)
    max_hours = config.get("max_time_to_resolution_hours", 999999)
    if min_hours > 0 or max_hours < 999999:
        filters.append(TimeToResolutionFilter(min_hours, max_hours))

    # Category filter
    allowed_categories = config.get("categories", [])
    if allowed_categories:
        filters.append(CategoryFilter(allowed_categories))

    # Exclude terms filter
    exclude_terms = config.get("exclude_markets_containing", [])
    if exclude_terms:
        filters.append(ExcludeTermsFilter(exclude_terms))

    chain = MarketFilterChain(filters)

    logger.info(
        "filter_chain_created",
        num_filters=len(filters),
        filters=chain.get_filter_descriptions(),
    )

    return chain
