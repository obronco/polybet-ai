"""Shared test fixtures and configuration."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.market import Market, MarketStatus
from src.models.news import NewsArticle, NewsSource
from src.models.trade import Prediction, Portfolio, TradeDirection


@pytest.fixture
def mock_openai_client(monkeypatch):
    """Mock OpenAI API client."""
    mock_client = AsyncMock()

    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """PROBABILITY: 0.65
CONFIDENCE: 7
REASONING: Strong technical indicators suggest upward momentum
KEY_FACTORS: institutional_adoption, technical_analysis, market_sentiment"""
    mock_response.usage.total_tokens = 150

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    return mock_client


@pytest.fixture
def mock_newsapi_client(monkeypatch):
    """Mock NewsAPI client."""
    mock_client = MagicMock()

    mock_client.get_everything.return_value = {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "source": {"name": "CryptoNews"},
                "author": "John Doe",
                "title": "Bitcoin Surges Past $95,000",
                "description": "Bitcoin reaches new highs amid institutional buying",
                "url": "https://example.com/btc-surge",
                "urlToImage": "https://example.com/image.jpg",
                "publishedAt": "2024-01-15T10:00:00Z",
                "content": "Full article content here",
            },
            {
                "source": {"name": "FinanceToday"},
                "author": "Jane Smith",
                "title": "ETH 2.0 Staking Hits New Record",
                "description": "Ethereum staking reaches all-time high",
                "url": "https://example.com/eth-staking",
                "urlToImage": "https://example.com/eth.jpg",
                "publishedAt": "2024-01-15T11:00:00Z",
                "content": "Ethereum staking content",
            },
        ],
    }

    return mock_client


@pytest.fixture
def mock_gamma_client():
    """Mock Gamma API client."""
    mock_client = AsyncMock()

    # Mock market data
    mock_markets = [
        {
            "id": "market_btc_100k",
            "question": "Will Bitcoin reach $100k by end of 2025?",
            "description": "Prediction market for Bitcoin price",
            "category": "Crypto",
            "active": True,
            "startDate": "2024-01-01T00:00:00Z",
            "endDate": "2025-12-31T23:59:59Z",
            "liquidity": 50000,
            "volume": 100000,
            "volume24hr": 5000,
            "numTraders": 150,
            "outcomePrices": ["0.45", "0.55"],
        }
    ]

    mock_client.get_markets = AsyncMock(return_value=mock_markets)
    mock_client.get_market = AsyncMock(return_value=mock_markets[0])

    return mock_client


@pytest.fixture
def mock_chromadb_collection():
    """Mock ChromaDB collection."""
    mock_collection = MagicMock()

    # Mock query response
    mock_collection.query.return_value = {
        "ids": [["market_btc_100k", "market_eth_upgrade"]],
        "distances": [[0.15, 0.25]],
        "metadatas": [
            [
                {
                    "type": "market",
                    "market_id": "market_btc_100k",
                    "category": "Crypto",
                    "question": "Will Bitcoin reach $100k by end of 2025?",
                },
                {
                    "type": "market",
                    "market_id": "market_eth_upgrade",
                    "category": "Crypto",
                    "question": "Will Ethereum upgrade succeed?",
                },
            ]
        ],
        "documents": [
            [
                "Will Bitcoin reach $100k by end of 2025?",
                "Will Ethereum upgrade succeed?",
            ]
        ],
    }

    # Mock add/get
    mock_collection.add.return_value = None
    mock_collection.get.return_value = {
        "ids": ["market_btc_100k"],
        "metadatas": [{"type": "market"}],
    }

    return mock_collection


@pytest.fixture
def sample_market():
    """Create a sample market for testing."""
    return Market(
        id="market_btc_100k",
        question="Will Bitcoin reach $100k by end of 2025?",
        description="Bitcoin price prediction market",
        category="Crypto",
        tags=["bitcoin", "crypto", "price"],
        status=MarketStatus.ACTIVE,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2025, 12, 31),
        liquidity=Decimal("50000"),
        volume=Decimal("100000"),
        volume_24h=Decimal("5000"),
        num_traders=150,
        yes_price=Decimal("0.45"),
        no_price=Decimal("0.55"),
        spread=Decimal("0.02"),
    )


@pytest.fixture
def sample_news_articles():
    """Create sample news articles for testing."""
    return [
        NewsArticle(
            id="news_btc_surge",
            url="https://example.com/btc-surge",
            source=NewsSource.NEWSAPI,
            source_name="CryptoNews",
            title="Bitcoin Surges Past $95,000",
            description="Bitcoin reaches new highs amid institutional buying",
            content="Full article content about Bitcoin surge",
            author="John Doe",
            published_at=datetime.now(),
            category="crypto",
            tags=["bitcoin", "price", "surge"],
        ),
        NewsArticle(
            id="news_eth_staking",
            url="https://example.com/eth-staking",
            source=NewsSource.NEWSAPI,
            source_name="FinanceToday",
            title="ETH 2.0 Staking Hits New Record",
            description="Ethereum staking reaches all-time high",
            content="Ethereum staking article content",
            author="Jane Smith",
            published_at=datetime.now(),
            category="crypto",
            tags=["ethereum", "staking", "eth"],
        ),
    ]


@pytest.fixture
def sample_prediction(sample_market):
    """Create a sample prediction for testing."""
    return Prediction(
        market_id=sample_market.id,
        predicted_probability=Decimal("0.65"),
        confidence=7,
        reasoning="Strong technical indicators and institutional adoption",
        key_factors=["institutional_adoption", "technical_analysis", "sentiment"],
        current_market_price=sample_market.yes_price,
        edge=Decimal("0.20"),  # 20% edge
        expected_value=Decimal("200"),
        model_name="gpt-4-turbo",
        temperature=0.7,
    )


@pytest.fixture
def sample_portfolio():
    """Create a sample portfolio for testing."""
    return Portfolio(
        balance=Decimal("10000"),
        initial_balance=Decimal("10000"),
        total_pnl=Decimal("0"),
        daily_pnl=Decimal("0"),
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
    )


@pytest.fixture
def mock_bm25_index():
    """Mock BM25 index."""
    mock_index = MagicMock()

    mock_index.search_markets.return_value = [
        {"id": "market_btc_100k", "score": 0.85, "type": "market"},
        {"id": "market_eth_upgrade", "score": 0.65, "type": "market"},
    ]

    mock_index.search_news.return_value = [
        {"id": "news_btc_surge", "score": 0.92, "type": "news"},
        {"id": "news_eth_staking", "score": 0.75, "type": "news"},
    ]

    return mock_index


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # This prevents test pollution from global instances
    yield
    # Cleanup code here if needed
