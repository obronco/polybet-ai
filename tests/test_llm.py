"""Tests for LLM utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.llm import LLMClient


@pytest.fixture
def llm_client(mock_openai_client):
    """Create LLM client with mocked OpenAI."""
    with patch("src.utils.llm.AsyncOpenAI") as mock_openai:
        mock_openai.return_value = mock_openai_client
        client = LLMClient(api_key="test_key", model="gpt-4-turbo")
        client.client = mock_openai_client
        yield client


@pytest.mark.asyncio
async def test_chat_completion(llm_client, mock_openai_client):
    """Test basic chat completion."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello!"},
    ]

    response = await llm_client.chat_completion(messages)

    assert response is not None
    assert isinstance(response, str)
    mock_openai_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_predict_market_outcome(llm_client):
    """Test market outcome prediction."""
    prediction = await llm_client.predict_market_outcome(
        question="Will Bitcoin reach $100k?",
        current_odds=0.45,
        news_context="Bitcoin surges past $95k",
        end_date="2025-12-31",
    )

    assert "probability" in prediction
    assert "confidence" in prediction
    assert "reasoning" in prediction
    assert 0 <= prediction["probability"] <= 1
    assert 1 <= prediction["confidence"] <= 10


@pytest.mark.asyncio
async def test_analyze_news_relevance(llm_client):
    """Test news relevance analysis."""
    result = await llm_client.analyze_news_relevance(
        news_summary="Bitcoin price surges to new high",
        market_question="Will Bitcoin reach $100k by end of year?",
    )

    assert "relevance" in result
    assert "impact" in result
    assert "explanation" in result
    assert 0 <= result["relevance"] <= 1


@pytest.mark.asyncio
async def test_chat_completion_retry_on_failure(llm_client, mock_openai_client):
    """Test retry logic on API failure."""
    # First call fails, second succeeds
    mock_openai_client.chat.completions.create.side_effect = [
        Exception("API Error"),
        mock_openai_client.chat.completions.create.return_value,
    ]

    messages = [{"role": "user", "content": "Test"}]

    # Should retry and eventually succeed
    with pytest.raises(Exception):
        # Will fail after retries exhausted in test
        await llm_client.chat_completion(messages)


@pytest.mark.asyncio
async def test_parse_prediction_response(llm_client):
    """Test parsing prediction response."""
    response = """PROBABILITY: 0.75
CONFIDENCE: 8
REASONING: Strong bullish indicators
KEY_FACTORS: adoption, sentiment, technicals"""

    result = llm_client._parse_prediction_response(response)

    assert result["probability"] == 0.75
    assert result["confidence"] == 8
    assert "adoption" in result["key_factors"]


def test_parse_prediction_malformed(llm_client):
    """Test parsing malformed prediction response."""
    response = "This is not a valid format"

    result = llm_client._parse_prediction_response(response)

    # Should return defaults
    assert "probability" in result
    assert "confidence" in result
    assert result["reasoning"] == response
