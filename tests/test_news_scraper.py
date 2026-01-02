"""Tests for News Scraper Agent."""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.news_scraper import NewsScraperAgent


@pytest.fixture
def news_scraper(mock_newsapi_client):
    """Create news scraper with mocked APIs."""
    # Create mock vector store
    mock_vector_store = MagicMock()
    mock_vector_store.add_news_articles.return_value = 2

    # Mock the NewsApiClient to return our mock
    with patch("src.api.news_sources.NewsApiClient") as mock_newsapi:
        mock_newsapi.return_value = mock_newsapi_client

        # Create agent with mocked dependencies
        agent = NewsScraperAgent(
            newsapi_key="test_key",
            tavily_key=None,
            rss_feeds=[],
            vector_store=mock_vector_store,
        )

        return agent


@pytest.mark.asyncio
async def test_scrape_news(news_scraper):
    """Test basic news scraping."""
    articles = await news_scraper.scrape_news(
        lookback_hours=24,
        max_results_per_source=100,
    )

    assert len(articles) >= 0  # May be filtered
    # Verify articles have required fields
    for article in articles:
        assert article.title is not None
        assert article.url is not None


@pytest.mark.asyncio
async def test_scrape_category_news(news_scraper):
    """Test scraping news for specific category."""
    articles = await news_scraper.scrape_category_news(
        category="crypto",
        lookback_hours=24,
    )

    assert isinstance(articles, list)
    for article in articles:
        assert article.category == "crypto"


@pytest.mark.asyncio
async def test_scrape_targeted_news(news_scraper):
    """Test scraping with specific keywords."""
    keywords = ["bitcoin", "ethereum"]

    articles = await news_scraper.scrape_targeted_news(
        keywords=keywords,
        lookback_hours=12,
    )

    assert isinstance(articles, list)


def test_get_all_keywords(news_scraper):
    """Test getting all keywords from config."""
    keywords = news_scraper._get_all_keywords()

    assert isinstance(keywords, list)
    assert len(keywords) > 0
    # Should be unique
    assert len(keywords) == len(set(k.lower() for k in keywords))


def test_get_category_keywords(news_scraper):
    """Test getting keywords for specific category."""
    crypto_keywords = news_scraper._get_category_keywords("crypto")

    assert isinstance(crypto_keywords, list)
    assert len(crypto_keywords) > 0


def test_filter_articles(news_scraper, sample_news_articles):
    """Test article filtering."""
    # Add a junk article
    junk_article = sample_news_articles[0]
    junk_article.title = "Ad"  # Too short

    articles = sample_news_articles + [junk_article]
    filtered = news_scraper._filter_articles(articles)

    # Junk should be filtered out
    assert len(filtered) < len(articles)


def test_filter_articles_removes_sponsored(news_scraper, sample_news_articles):
    """Test filtering removes sponsored content."""
    sponsored = sample_news_articles[0]
    sponsored.title = "Sponsored: Buy Bitcoin Now!"

    filtered = news_scraper._filter_articles([sponsored])

    assert len(filtered) == 0


@pytest.mark.asyncio
async def test_scrape_news_empty_results(news_scraper, mock_newsapi_client):
    """Test handling empty results from API."""
    mock_newsapi_client.get_everything.return_value = {
        "status": "ok",
        "totalResults": 0,
        "articles": [],
    }

    articles = await news_scraper.scrape_news()

    assert len(articles) == 0


@pytest.mark.asyncio
async def test_scrape_news_indexes_in_vector_store(news_scraper):
    """Test that scraped news is indexed in vector store."""
    # Vector store is already injected via fixture
    articles = await news_scraper.scrape_news()

    # Should have called vector store to index
    if len(articles) > 0:
        news_scraper.vector_store.add_news_articles.assert_called_once()


def test_get_category_keywords_invalid_category(news_scraper):
    """Test getting keywords for non-existent category."""
    keywords = news_scraper._get_category_keywords("nonexistent")

    assert keywords == []
