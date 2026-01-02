"""Tests for Risk Manager Agent."""

from decimal import Decimal
from datetime import datetime

import pytest

from src.agents.risk_manager import RiskManagerAgent
from src.models.market import Market, MarketStatus
from src.models.trade import Prediction, Portfolio


@pytest.fixture
def risk_manager():
    """Create a risk manager instance."""
    return RiskManagerAgent()


@pytest.fixture
def sample_market():
    """Create a sample market."""
    return Market(
        id="test_market_1",
        question="Will BTC reach $100k by end of 2025?",
        description="Bitcoin price prediction",
        category="Crypto",
        tags=["bitcoin", "crypto"],
        status=MarketStatus.ACTIVE,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2025, 12, 31),
        liquidity=Decimal("50000"),
        volume=Decimal("100000"),
        volume_24h=Decimal("5000"),
        num_traders=100,
        yes_price=Decimal("0.45"),
        no_price=Decimal("0.55"),
        spread=Decimal("0.02"),
    )


@pytest.fixture
def sample_prediction(sample_market):
    """Create a sample prediction."""
    return Prediction(
        market_id=sample_market.id,
        predicted_probability=Decimal("0.55"),
        confidence=7,
        reasoning="Strong technical indicators and institutional adoption",
        key_factors=["institutional_adoption", "technical_analysis"],
        current_market_price=sample_market.yes_price,
        edge=Decimal("0.10"),  # 10% edge
        expected_value=Decimal("100"),
        model_name="gpt-4-turbo",
        temperature=0.7,
    )


@pytest.fixture
def sample_portfolio():
    """Create a sample portfolio."""
    return Portfolio(
        balance=Decimal("10000"),
        initial_balance=Decimal("10000"),
        total_pnl=Decimal("0"),
        daily_pnl=Decimal("0"),
    )


def test_validate_trade_approved(
    risk_manager, sample_prediction, sample_market, sample_portfolio
):
    """Test trade validation with valid trade."""
    import asyncio

    async def run_test():
        assessment = await risk_manager.validate_trade(
            prediction=sample_prediction,
            market=sample_market,
            portfolio=sample_portfolio,
        )

        assert assessment.approved is True
        assert assessment.recommended_size > 0
        assert len(assessment.checks_passed) > 0
        assert len(assessment.checks_failed) == 0

    asyncio.run(run_test())


def test_validate_trade_low_confidence(
    risk_manager, sample_prediction, sample_market, sample_portfolio
):
    """Test trade rejection due to low confidence."""
    import asyncio

    # Set low confidence
    sample_prediction.confidence = 3

    async def run_test():
        assessment = await risk_manager.validate_trade(
            prediction=sample_prediction,
            market=sample_market,
            portfolio=sample_portfolio,
        )

        assert assessment.approved is False
        assert any("confidence" in check.lower() for check in assessment.checks_failed)

    asyncio.run(run_test())


def test_validate_trade_low_edge(
    risk_manager, sample_prediction, sample_market, sample_portfolio
):
    """Test trade rejection due to insufficient edge."""
    import asyncio

    # Set low edge
    sample_prediction.edge = Decimal("0.02")  # Only 2% edge

    async def run_test():
        assessment = await risk_manager.validate_trade(
            prediction=sample_prediction,
            market=sample_market,
            portfolio=sample_portfolio,
        )

        assert assessment.approved is False
        assert any("edge" in check.lower() for check in assessment.checks_failed)

    asyncio.run(run_test())


def test_kelly_criterion_calculation(risk_manager, sample_prediction, sample_portfolio):
    """Test Kelly Criterion position sizing."""
    kelly_size = risk_manager.position_sizer.calculate_kelly_size(
        prediction=sample_prediction,
        portfolio=sample_portfolio,
    )

    assert kelly_size > 0
    assert kelly_size <= sample_portfolio.balance


def test_circuit_breaker_trigger(risk_manager, sample_portfolio):
    """Test circuit breaker triggering on large loss."""
    # Set large daily loss
    sample_portfolio.daily_pnl = Decimal("-2000")  # 20% loss

    triggered = risk_manager.check_circuit_breaker(sample_portfolio)

    assert triggered is True
    assert risk_manager.circuit_breaker_active is True


def test_position_size_constraints(
    risk_manager, sample_prediction, sample_market, sample_portfolio
):
    """Test position sizing respects min/max constraints."""
    size = risk_manager.calculate_position_size(
        prediction=sample_prediction,
        portfolio=sample_portfolio,
        market=sample_market,
    )

    min_size = Decimal("10")  # From config
    max_size = Decimal("1000")  # From config

    assert size >= min_size
    assert size <= max_size
