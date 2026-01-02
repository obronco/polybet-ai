"""Tests for Forecasting Agent."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.forecaster import ForecastingAgent


@pytest.fixture
def forecaster():
    """Create forecaster with mocked LLM."""
    with patch("src.agents.forecaster.llm_client") as mock_llm:
        # Mock the predict_market_outcome method
        mock_llm.predict_market_outcome = AsyncMock(
            return_value={
                "probability": 0.65,
                "confidence": 7,
                "reasoning": "Strong technical indicators suggest upward momentum",
                "key_factors": [
                    "institutional_adoption",
                    "technical_analysis",
                    "market_sentiment",
                ],
            }
        )
        agent = ForecastingAgent(model="gpt-4-turbo", temperature=0.7)
        yield agent


@pytest.mark.asyncio
async def test_predict_outcome(forecaster, sample_market, sample_news_articles):
    """Test market outcome prediction."""
    prediction = await forecaster.predict_outcome(
        market=sample_market,
        news_context=sample_news_articles,
    )

    assert prediction.market_id == sample_market.id
    assert 0 <= prediction.predicted_probability <= 1
    assert 1 <= prediction.confidence <= 10
    assert prediction.reasoning is not None
    assert len(prediction.key_factors) > 0
    assert prediction.edge == prediction.predicted_probability - sample_market.yes_price


@pytest.mark.asyncio
async def test_predict_outcome_no_news(forecaster, sample_market):
    """Test prediction without news context."""
    prediction = await forecaster.predict_outcome(
        market=sample_market,
        news_context=None,
    )

    assert prediction.market_id == sample_market.id
    assert prediction.predicted_probability > 0


@pytest.mark.asyncio
async def test_batch_predict(forecaster, sample_market):
    """Test batch prediction for multiple markets."""
    markets = [sample_market]

    predictions = await forecaster.batch_predict(markets)

    assert len(predictions) == 1
    assert predictions[0].market_id == sample_market.id


@pytest.mark.asyncio
async def test_compare_to_market(forecaster, sample_prediction):
    """Test comparing prediction to market price."""
    analysis = await forecaster.compare_to_market(
        prediction=sample_prediction,
        min_edge=0.05,
    )

    assert "has_edge" in analysis
    assert "edge" in analysis
    assert "direction" in analysis
    assert "recommendation" in analysis


@pytest.mark.asyncio
async def test_evaluate_confidence(forecaster, sample_prediction):
    """Test confidence evaluation."""
    evaluation = await forecaster.evaluate_confidence(
        prediction=sample_prediction,
        news_quality=0.8,
    )

    assert "original_confidence" in evaluation
    assert "adjusted_confidence" in evaluation
    assert "confidence_level" in evaluation
    assert "should_trade" in evaluation


def test_get_confidence_label(forecaster):
    """Test confidence level labeling."""
    assert forecaster._get_confidence_label(10) == "very_high"
    assert forecaster._get_confidence_label(8) == "high"
    assert forecaster._get_confidence_label(6) == "medium"
    assert forecaster._get_confidence_label(4) == "low"
    assert forecaster._get_confidence_label(2) == "very_low"


@pytest.mark.asyncio
async def test_update_prediction(
    forecaster, sample_prediction, sample_market, sample_news_articles
):
    """Test updating prediction with new information."""
    updated = await forecaster.update_prediction(
        original_prediction=sample_prediction,
        new_news=sample_news_articles,
        market=sample_market,
    )

    assert updated.market_id == sample_market.id
    # Updated prediction should exist
    assert updated.predicted_probability >= 0


@pytest.mark.asyncio
async def test_calibrate_prediction(forecaster, sample_prediction):
    """Test prediction calibration."""
    # Test with good historical accuracy
    calibrated = await forecaster.calibrate_prediction(
        prediction=sample_prediction,
        historical_accuracy=0.9,
    )

    # Confidence should be adjusted based on accuracy
    assert calibrated.confidence >= 1


@pytest.mark.asyncio
async def test_prediction_edge_calculation(forecaster, sample_market):
    """Test that edge is calculated correctly."""
    prediction = await forecaster.predict_outcome(market=sample_market)

    # Edge should be predicted_prob - market_price
    expected_edge = prediction.predicted_probability - sample_market.yes_price
    assert abs(prediction.edge - expected_edge) < 0.001  # Within rounding
