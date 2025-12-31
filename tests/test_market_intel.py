"""Tests for Market Intelligence Agent."""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.agents.market_intel import MarketIntelligenceAgent


@pytest_asyncio.fixture
async def market_intel(mock_gamma_client):
    """Create market intelligence agent with mocked Gamma client."""
    with patch("src.agents.market_intel.GammaClient") as mock_gamma:
        mock_gamma.return_value = mock_gamma_client

        agent = MarketIntelligenceAgent()
        agent.gamma_client = mock_gamma_client

        yield agent


@pytest.mark.asyncio
async def test_get_active_markets(market_intel):
    """Test fetching active markets."""
    async with market_intel:
        markets = await market_intel.get_active_markets(limit=100)

        assert len(markets) > 0
        for market in markets:
            assert market.is_active


@pytest.mark.asyncio
async def test_get_markets_by_category(market_intel):
    """Test fetching markets by category."""
    async with market_intel:
        markets = await market_intel.get_markets_by_category(
            category="Crypto",
            limit=50,
        )

        assert isinstance(markets, list)
        for market in markets:
            assert market.category == "Crypto"


@pytest.mark.asyncio
async def test_search_markets(market_intel, mock_gamma_client):
    """Test searching markets by query."""
    mock_gamma_client.search_markets = AsyncMock(
        return_value=mock_gamma_client.get_markets.return_value
    )

    async with market_intel:
        markets = await market_intel.search_markets(
            query="Bitcoin",
            limit=20,
        )

        assert isinstance(markets, list)
        mock_gamma_client.search_markets.assert_called_once()


@pytest.mark.asyncio
async def test_get_market_details(market_intel):
    """Test getting market details."""
    async with market_intel:
        market = await market_intel.get_market_details("market_btc_100k")

        assert market is not None
        assert market.id == "market_btc_100k"


@pytest.mark.asyncio
async def test_get_market_details_not_found(market_intel, mock_gamma_client):
    """Test handling market not found."""
    mock_gamma_client.get_market = AsyncMock(return_value=None)

    async with market_intel:
        market = await market_intel.get_market_details("nonexistent")

        assert market is None


def test_filter_markets(market_intel, sample_market):
    """Test market filtering logic."""
    from decimal import Decimal

    markets = [sample_market]

    # Should pass filters
    filtered = market_intel._filter_markets(markets)
    assert len(filtered) == 1

    # Test liquidity filter
    sample_market.liquidity = Decimal("100")  # Too low
    filtered = market_intel._filter_markets([sample_market])
    assert len(filtered) == 0


def test_filter_markets_spread(market_intel, sample_market):
    """Test spread filtering."""
    from decimal import Decimal

    sample_market.spread = Decimal("0.10")  # Too high (10%)

    filtered = market_intel._filter_markets([sample_market])
    assert len(filtered) == 0


def test_filter_markets_time_to_resolution(market_intel, sample_market):
    """Test time to resolution filtering."""
    # Market should be within time bounds
    filtered = market_intel._filter_markets([sample_market])
    assert len(filtered) == 1


@pytest.mark.asyncio
async def test_find_opportunities(market_intel):
    """Test finding trading opportunities."""
    async with market_intel:
        opportunities = await market_intel.find_opportunities()

        assert isinstance(opportunities, list)
        for opp in opportunities:
            assert opp.market is not None
            assert opp.relevance_score >= 0


@pytest.mark.asyncio
async def test_get_trending_markets(market_intel):
    """Test getting trending markets."""
    async with market_intel:
        markets = await market_intel.get_trending_markets(limit=20)

        assert isinstance(markets, list)
        # Should be sorted by volume
        if len(markets) > 1:
            assert markets[0].volume_24h >= markets[-1].volume_24h


@pytest.mark.asyncio
async def test_get_high_liquidity_markets(market_intel):
    """Test getting high liquidity markets."""
    async with market_intel:
        markets = await market_intel.get_high_liquidity_markets(limit=20)

        assert isinstance(markets, list)
        # Should be sorted by liquidity
        if len(markets) > 1:
            assert markets[0].liquidity >= markets[-1].liquidity


@pytest.mark.asyncio
async def test_refresh_market_index(market_intel):
    """Test refreshing market index."""
    with patch("src.agents.market_intel.vector_store") as mock_vs:
        mock_vs.add_markets.return_value = 10

        async with market_intel:
            count = await market_intel.refresh_market_index()

            assert count >= 0
            mock_vs.add_markets.assert_called_once()


def test_get_market_summary(market_intel, sample_market):
    """Test getting market summary."""
    summary = market_intel.get_market_summary(sample_market)

    assert isinstance(summary, str)
    assert sample_market.question in summary
    assert sample_market.category in summary
