"""Tests for Analyst Agent."""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.analyst import AnalystAgent


@pytest.fixture
def analyst():
    """Create analyst agent with mocked dependencies."""
    return AnalystAgent()


@pytest.fixture
def mock_vector_store_results():
    """Mock vector store search results."""
    return [
        {
            "id": "market_btc_100k",
            "hybrid_score": 0.85,
            "relevance_score": 0.85,
            "metadata": {
                "type": "market",
                "market_id": "market_btc_100k",
                "category": "Crypto",
                "status": "active",
                "yes_price": 0.45,
                "liquidity": 50000,
                "volume_24h": 5000,
                "end_date": "2025-12-31T23:59:59Z",
                "question": "Will Bitcoin reach $100k by end of 2025?",
            },
        },
        {
            "id": "market_eth_upgrade",
            "hybrid_score": 0.72,
            "relevance_score": 0.72,
            "metadata": {
                "type": "market",
                "market_id": "market_eth_upgrade",
                "category": "Crypto",
                "status": "active",
                "yes_price": 0.60,
                "liquidity": 30000,
                "volume_24h": 3000,
                "end_date": "2025-06-30T23:59:59Z",
                "question": "Will Ethereum upgrade succeed?",
            },
        },
    ]


@pytest.mark.asyncio
async def test_analyze_news_market_correlation(analyst, sample_news_articles, sample_market):
    """Test news-market correlation analysis."""
    with patch("src.agents.analyst.llm_client") as mock_llm:
        mock_llm.analyze_news_relevance = MagicMock(
            return_value={
                "relevance": 0.8,
                "impact": "positive",
                "explanation": "Strongly related to Bitcoin price",
            }
        )

        opportunities = await analyst.analyze_news_market_correlation(
            news_article=sample_news_articles[0],
            markets=[sample_market],
            top_k=5,
        )

        assert len(opportunities) > 0
        assert opportunities[0].market.id == sample_market.id
        assert opportunities[0].relevance_score > 0


@pytest.mark.asyncio
async def test_find_opportunities_from_news(analyst, sample_news_articles, mock_vector_store_results):
    """Test finding opportunities from news articles."""
    with patch("src.agents.analyst.vector_store") as mock_vs:
        mock_vs.hybrid_find_markets_for_news.return_value = mock_vector_store_results

        opportunities = await analyst.find_opportunities_from_news(
            news_articles=sample_news_articles,
            min_relevance=0.5,
        )

        assert len(opportunities) > 0
        # Should use hybrid search
        mock_vs.hybrid_find_markets_for_news.assert_called()


@pytest.mark.asyncio
async def test_find_opportunities_filters_low_relevance(analyst, sample_news_articles):
    """Test filtering low relevance opportunities."""
    with patch("src.agents.analyst.vector_store") as mock_vs:
        low_relevance_results = [
            {
                "id": "market1",
                "hybrid_score": 0.3,  # Below threshold
                "metadata": {
                    "type": "market",
                    "market_id": "market1",
                    "category": "Test",
                    "question": "Test?",
                    "status": "active",
                    "yes_price": 0.5,
                    "liquidity": 1000,
                    "volume_24h": 100,
                    "end_date": "2025-12-31T00:00:00Z",
                },
            }
        ]
        mock_vs.hybrid_find_markets_for_news.return_value = low_relevance_results

        opportunities = await analyst.find_opportunities_from_news(
            news_articles=sample_news_articles,
            min_relevance=0.5,  # Higher threshold
        )

        # Should filter out low relevance
        assert len(opportunities) == 0


@pytest.mark.asyncio
async def test_find_news_for_markets(analyst, sample_market):
    """Test finding news for markets."""
    with patch("src.agents.analyst.vector_store") as mock_vs:
        mock_news_results = [
            {
                "id": "news_btc_surge",
                "hybrid_score": 0.88,
                "metadata": {
                    "type": "news",
                    "source": "newsapi",
                    "source_name": "CryptoNews",
                    "url": "https://example.com/news",
                    "published_at": "2024-01-15T10:00:00Z",
                    "title": "Bitcoin Surges",
                },
            }
        ]
        mock_vs.hybrid_find_news_for_market.return_value = mock_news_results

        results = await analyst.find_news_for_markets(
            markets=[sample_market],
            min_relevance=0.5,
        )

        assert len(results) > 0
        market, news_articles = results[0]
        assert market.id == sample_market.id
        assert len(news_articles) > 0


@pytest.mark.asyncio
async def test_evaluate_market_impact(analyst, sample_news_articles, sample_market):
    """Test evaluating market impact of news."""
    with patch("src.agents.analyst.llm_client") as mock_llm:
        mock_llm.analyze_news_relevance = MagicMock(
            return_value={
                "relevance": 0.85,
                "impact": "positive",
                "explanation": "Bitcoin surge is bullish for BTC $100k prediction",
            }
        )

        impact = await analyst.evaluate_market_impact(
            news_article=sample_news_articles[0],
            market=sample_market,
        )

        assert "relevance_score" in impact
        assert "impact_direction" in impact
        assert "explanation" in impact
        assert impact["relevance_score"] > 0


def test_consolidate_opportunities(analyst):
    """Test consolidating opportunities for same market."""
    from src.models.market import Market, MarketOpportunity, MarketStatus
    from datetime import datetime
    from decimal import Decimal

    market = Market(
        id="market1",
        question="Test?",
        category="Test",
        status=MarketStatus.ACTIVE,
        start_date=datetime.now(),
        end_date=datetime.now(),
        liquidity=Decimal("1000"),
        volume=Decimal("1000"),
        yes_price=Decimal("0.5"),
        no_price=Decimal("0.5"),
        spread=Decimal("0.01"),
    )

    # Multiple opportunities for same market
    opps = [
        MarketOpportunity(
            market=market,
            relevance_score=0.8,
            news_context=["news1"],
        ),
        MarketOpportunity(
            market=market,
            relevance_score=0.6,
            news_context=["news2"],
        ),
    ]

    consolidated = analyst._consolidate_opportunities(opps)

    # Should merge into one
    assert len(consolidated) == 1
    # Should combine news context
    assert len(consolidated[0].news_context) == 2
    # Should average relevance
    assert 0.6 <= consolidated[0].relevance_score <= 0.8


@pytest.mark.asyncio
async def test_rank_opportunities(analyst):
    """Test ranking opportunities."""
    from src.models.market import Market, MarketOpportunity, MarketStatus
    from datetime import datetime
    from decimal import Decimal

    market_high = Market(
        id="market1",
        question="High liquidity market",
        category="Test",
        status=MarketStatus.ACTIVE,
        start_date=datetime.now(),
        end_date=datetime.now(),
        liquidity=Decimal("100000"),  # High liquidity
        volume=Decimal("50000"),
        volume_24h=Decimal("5000"),
        yes_price=Decimal("0.5"),
        no_price=Decimal("0.5"),
        spread=Decimal("0.01"),
    )

    market_low = Market(
        id="market2",
        question="Low liquidity market",
        category="Test",
        status=MarketStatus.ACTIVE,
        start_date=datetime.now(),
        end_date=datetime.now(),
        liquidity=Decimal("1000"),  # Low liquidity
        volume=Decimal("500"),
        volume_24h=Decimal("50"),
        yes_price=Decimal("0.5"),
        no_price=Decimal("0.5"),
        spread=Decimal("0.01"),
    )

    opps = [
        MarketOpportunity(market=market_low, relevance_score=0.8),
        MarketOpportunity(market=market_high, relevance_score=0.7),
    ]

    ranked = await analyst.rank_opportunities(opps)

    # Should rank by composite score (relevance + liquidity + other factors)
    assert len(ranked) == 2
    # All should have composite scores
    for opp in ranked:
        assert "composite_score" in opp.metadata


def test_calculate_opportunity_score(analyst):
    """Test opportunity score calculation."""
    from src.models.market import Market, MarketOpportunity, MarketStatus
    from datetime import datetime
    from decimal import Decimal

    market = Market(
        id="market1",
        question="Test",
        category="Test",
        status=MarketStatus.ACTIVE,
        start_date=datetime.now(),
        end_date=datetime.now(),
        liquidity=Decimal("50000"),
        volume=Decimal("100000"),
        volume_24h=Decimal("5000"),
        yes_price=Decimal("0.5"),
        no_price=Decimal("0.5"),
        spread=Decimal("0.01"),
    )

    opp = MarketOpportunity(market=market, relevance_score=0.8)

    score = analyst._calculate_opportunity_score(opp)

    assert 0 <= score <= 1
    # Higher relevance should contribute to higher score
    assert score > 0
