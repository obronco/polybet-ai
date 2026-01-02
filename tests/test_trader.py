"""Tests for Trading Agent."""

from decimal import Decimal

import pytest

from src.agents.trader import TradingAgent
from src.models.trade import RiskAssessment


@pytest.fixture
def trader():
    """Create trading agent in paper trading mode."""
    return TradingAgent(paper_trading=True)


@pytest.fixture
def approved_risk_assessment():
    """Create an approved risk assessment."""
    return RiskAssessment(
        approved=True,
        risk_score=0.3,
        checks_passed=["edge_sufficient", "confidence_acceptable"],
        checks_failed=[],
        warnings=[],
        recommended_size=Decimal("300"),
        max_size=Decimal("500"),
        kelly_size=Decimal("400"),
    )


@pytest.mark.asyncio
async def test_execute_paper_trade(
    trader, sample_prediction, approved_risk_assessment, sample_market
):
    """Test executing paper trade."""
    trade = await trader.execute_trade(
        prediction=sample_prediction,
        risk_assessment=approved_risk_assessment,
        market=sample_market,
    )

    assert trade is not None
    assert trade.is_paper_trade is True
    assert trade.market_id == sample_market.id
    assert trade.size == approved_risk_assessment.recommended_size
    assert trade.entry_price > 0


@pytest.mark.asyncio
async def test_execute_trade_rejected(trader, sample_prediction, sample_market):
    """Test trade rejection when risk assessment fails."""
    rejected_assessment = RiskAssessment(
        approved=False,
        risk_score=0.9,
        checks_passed=[],
        checks_failed=["edge_too_low"],
        warnings=["High risk trade"],
        recommended_size=Decimal("0"),
        max_size=Decimal("300"),
    )

    trade = await trader.execute_trade(
        prediction=sample_prediction,
        risk_assessment=rejected_assessment,
        market=sample_market,
    )

    assert trade is None


@pytest.mark.asyncio
async def test_update_open_positions(
    trader, sample_prediction, approved_risk_assessment, sample_market
):
    """Test updating P&L for open positions."""
    # Execute a trade first
    _ = await trader.execute_trade(
        prediction=sample_prediction,
        risk_assessment=approved_risk_assessment,
        market=sample_market,
    )

    assert len(trader.portfolio.open_trades) == 1

    # Update positions with new market data
    sample_market.yes_price = Decimal("0.50")  # Price moved up
    markets = {sample_market.id: sample_market}

    await trader.update_open_positions(markets)

    # P&L should be updated
    assert trader.portfolio.open_trades[0].current_price == Decimal("0.50")
    assert trader.portfolio.open_trades[0].pnl is not None


@pytest.mark.asyncio
async def test_close_position(
    trader, sample_prediction, approved_risk_assessment, sample_market
):
    """Test closing a position."""
    # Execute trade
    trade = await trader.execute_trade(
        prediction=sample_prediction,
        risk_assessment=approved_risk_assessment,
        market=sample_market,
    )

    # Close it
    exit_price = Decimal("0.55")
    closed_trade = await trader.close_position(
        trade=trade,
        exit_price=exit_price,
        reason="take_profit",
    )

    assert closed_trade.closed is True
    assert closed_trade.exit_price == exit_price
    assert len(trader.portfolio.open_trades) == 0
    assert len(trader.portfolio.closed_trades) == 1


@pytest.mark.asyncio
async def test_apply_exit_rules_stop_loss(
    trader, sample_prediction, approved_risk_assessment, sample_market
):
    """Test stop loss exit rule."""
    # Execute trade
    await trader.execute_trade(
        prediction=sample_prediction,
        risk_assessment=approved_risk_assessment,
        market=sample_market,
    )

    # Price drops significantly
    sample_market.yes_price = Decimal("0.20")  # Big loss
    markets = {sample_market.id: sample_market}

    await trader.update_open_positions(markets)
    closed_count = await trader.apply_exit_rules(markets)

    # Should trigger stop loss
    assert closed_count > 0
    assert len(trader.portfolio.open_trades) == 0


@pytest.mark.asyncio
async def test_apply_exit_rules_take_profit(
    trader, sample_prediction, approved_risk_assessment, sample_market
):
    """Test take profit exit rule."""
    # Execute trade
    await trader.execute_trade(
        prediction=sample_prediction,
        risk_assessment=approved_risk_assessment,
        market=sample_market,
    )

    # Price increases significantly
    sample_market.yes_price = Decimal("0.90")  # Big gain
    markets = {sample_market.id: sample_market}

    await trader.update_open_positions(markets)
    closed_count = await trader.apply_exit_rules(markets)

    # Should trigger take profit
    assert closed_count > 0


def test_get_portfolio_summary(trader):
    """Test getting portfolio summary."""
    summary = trader.get_portfolio_summary()

    assert "balance" in summary
    assert "total_pnl" in summary
    assert "roi" in summary
    assert "win_rate" in summary
    assert "total_trades" in summary


@pytest.mark.asyncio
async def test_portfolio_balance_update(
    trader, sample_prediction, approved_risk_assessment, sample_market
):
    """Test portfolio balance updates after trade."""
    initial_balance = trader.portfolio.balance

    # Execute and close profitable trade
    trade = await trader.execute_trade(
        prediction=sample_prediction,
        risk_assessment=approved_risk_assessment,
        market=sample_market,
    )

    # Close with profit
    exit_price = trade.entry_price + Decimal("0.10")
    await trader.close_position(trade, exit_price, "manual")

    # Balance should increase
    assert trader.portfolio.balance > initial_balance


@pytest.mark.asyncio
async def test_multiple_positions(
    trader, sample_prediction, approved_risk_assessment, sample_market
):
    """Test managing multiple open positions."""
    # Execute multiple trades
    for i in range(3):
        sample_market.id = f"market_{i}"
        await trader.execute_trade(
            prediction=sample_prediction,
            risk_assessment=approved_risk_assessment,
            market=sample_market,
        )

    assert len(trader.portfolio.open_trades) == 3
    assert trader.portfolio.total_trades == 3


def test_paper_trade_simulation(trader):
    """Test that paper trading is properly flagged."""
    assert trader.paper_trading is True
    assert trader.portfolio.balance == Decimal("10000")  # Default paper balance
