"""Tests for Pydantic data models."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models.market import Market, MarketStatus, OrderSide
from src.models.news import NewsSource, SentimentScore
from src.models.trade import (
    Order,
    Prediction,
    Portfolio,
    ProposedTrade,
    Trade,
    TradeDirection,
    TradeStatus,
)


def test_market_model_valid(sample_market):
    """Test valid market model creation."""
    assert sample_market.id == "market_btc_100k"
    assert sample_market.is_active is True
    assert sample_market.implied_probability_yes == float(sample_market.yes_price)


def test_market_model_time_to_resolution(sample_market):
    """Test time to resolution calculation."""
    hours = sample_market.time_to_resolution_hours
    assert hours >= 0


def test_market_model_invalid_price():
    """Test market model rejects invalid prices."""
    with pytest.raises(ValidationError):
        Market(
            id="test",
            question="Test?",
            category="Test",
            status=MarketStatus.ACTIVE,
            start_date=datetime.now(),
            end_date=datetime.now(),
            liquidity=Decimal("1000"),
            volume=Decimal("1000"),
            yes_price=Decimal("1.5"),  # Invalid: > 1
            no_price=Decimal("0.5"),
            spread=Decimal("0.01"),
        )


def test_news_article_model_valid(sample_news_articles):
    """Test valid news article model."""
    article = sample_news_articles[0]

    assert article.id == "news_btc_surge"
    assert article.source == NewsSource.NEWSAPI
    assert article.is_recent(hours=24 * 365)  # Should be recent for test


def test_news_article_age_calculation(sample_news_articles):
    """Test article age calculation."""
    article = sample_news_articles[0]
    age = article.age_hours

    assert age >= 0


def test_prediction_model_valid(sample_prediction):
    """Test valid prediction model."""
    assert 0 <= sample_prediction.predicted_probability <= 1
    assert 1 <= sample_prediction.confidence <= 10
    assert sample_prediction.has_edge(min_edge=0.05)


def test_prediction_model_direction(sample_prediction):
    """Test prediction direction calculation."""
    direction = sample_prediction.direction

    if sample_prediction.predicted_probability > sample_prediction.current_market_price:
        assert direction == TradeDirection.LONG
    else:
        assert direction == TradeDirection.SHORT


def test_prediction_invalid_confidence():
    """Test prediction rejects invalid confidence."""
    with pytest.raises(ValidationError):
        Prediction(
            market_id="test",
            predicted_probability=Decimal("0.6"),
            confidence=11,  # Invalid: > 10
            reasoning="Test",
            key_factors=[],
            current_market_price=Decimal("0.5"),
            edge=Decimal("0.1"),
            expected_value=Decimal("100"),
            model_name="test",
        )


def test_portfolio_model_valid(sample_portfolio):
    """Test valid portfolio model."""
    assert sample_portfolio.balance == Decimal("10000")
    assert sample_portfolio.win_rate == 0  # No trades yet
    assert sample_portfolio.roi == 0


def test_portfolio_win_rate_calculation():
    """Test portfolio win rate calculation."""
    portfolio = Portfolio(
        balance=Decimal("10000"),
        initial_balance=Decimal("10000"),
        total_trades=10,
        winning_trades=7,
        losing_trades=3,
    )

    assert portfolio.win_rate == 70.0


def test_portfolio_roi_calculation():
    """Test portfolio ROI calculation."""
    portfolio = Portfolio(
        balance=Decimal("12000"),
        initial_balance=Decimal("10000"),
        total_pnl=Decimal("2000"),
    )

    assert portfolio.roi == 20.0


def test_portfolio_available_balance():
    """Test available balance calculation."""
    from src.models.market import OrderSide

    portfolio = Portfolio(
        balance=Decimal("10000"),
        initial_balance=Decimal("10000"),
    )

    # Add open trade
    trade = Trade(
        id="trade1",
        order_id="order1",
        market_id="market1",
        side=OrderSide.YES,
        direction=TradeDirection.LONG,
        entry_price=Decimal("0.5"),
        size=Decimal("100"),
        cost=Decimal("1000"),
        is_paper_trade=True,
    )

    portfolio.open_trades.append(trade)

    available = portfolio.available_balance
    assert available == Decimal("9000")  # 10000 - 1000


def test_trade_model_pnl_update():
    """Test trade P&L update."""
    trade = Trade(
        id="trade1",
        order_id="order1",
        market_id="market1",
        side=OrderSide.YES,
        direction=TradeDirection.LONG,
        entry_price=Decimal("0.50"),
        size=Decimal("100"),
        cost=Decimal("50"),
        is_paper_trade=True,
    )

    # Update with new price
    trade.update_pnl(Decimal("0.60"))

    assert trade.current_price == Decimal("0.60")
    assert trade.pnl == Decimal("10")  # (0.60 - 0.50) * 100
    assert trade.pnl_percentage == 20.0  # 10/50 * 100


def test_trade_hold_time_calculation():
    """Test trade hold time calculation."""
    trade = Trade(
        id="trade1",
        order_id="order1",
        market_id="market1",
        side=OrderSide.YES,
        direction=TradeDirection.LONG,
        entry_price=Decimal("0.50"),
        size=Decimal("100"),
        cost=Decimal("50"),
        is_paper_trade=True,
    )

    hold_time = trade.hold_time_hours
    assert hold_time >= 0


def test_order_model_fill_percentage():
    """Test order fill percentage calculation."""
    order = Order(
        market_id="market1",
        side=OrderSide.YES,
        price=Decimal("0.50"),
        size=Decimal("100"),
        filled_size=Decimal("50"),
    )

    assert order.fill_percentage == 50.0
    assert order.is_filled is False


def test_order_model_fully_filled():
    """Test fully filled order."""
    order = Order(
        market_id="market1",
        side=OrderSide.YES,
        price=Decimal("0.50"),
        size=Decimal("100"),
        filled_size=Decimal("100"),
        status=TradeStatus.FILLED,
    )

    assert order.is_filled is True
    assert order.fill_percentage == 100.0


def test_proposed_trade_model():
    """Test proposed trade model."""
    from src.models.market import Market, MarketStatus

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

    prediction = Prediction(
        market_id="market1",
        predicted_probability=Decimal("0.6"),
        confidence=7,
        reasoning="Test",
        key_factors=[],
        current_market_price=Decimal("0.5"),
        edge=Decimal("0.1"),
        expected_value=Decimal("100"),
        model_name="test",
    )

    proposed = ProposedTrade(
        market=market,
        prediction=prediction,
        side=OrderSide.YES,
        direction=TradeDirection.LONG,
        size=Decimal("100"),
    )

    assert proposed.market.id == "market1"
    assert proposed.direction == TradeDirection.LONG


def test_sentiment_score_enum():
    """Test sentiment score enumeration."""
    assert SentimentScore.POSITIVE == "positive"
    assert SentimentScore.NEGATIVE == "negative"
    assert SentimentScore.NEUTRAL == "neutral"


def test_market_status_enum():
    """Test market status enumeration."""
    assert MarketStatus.ACTIVE == "active"
    assert MarketStatus.CLOSED == "closed"
    assert MarketStatus.RESOLVED == "resolved"
