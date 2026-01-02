"""Trade execution strategies for different trading modes."""

import os
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional

from ..api.polymarket import PolymarketClient
from ..models.market import OrderSide
from ..models.trade import ProposedTrade, Trade
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TradeExecutionStrategy(ABC):
    """Abstract base class for trade execution strategies."""

    @abstractmethod
    async def execute(self, proposed_trade: ProposedTrade) -> Optional[Trade]:
        """Execute a trade based on the proposed trade.

        Args:
            proposed_trade: Proposed trade details

        Returns:
            Trade object if successful, None if failed
        """
        pass


class PaperTradingStrategy(TradeExecutionStrategy):
    """Simulated paper trading execution strategy."""

    async def execute(self, proposed_trade: ProposedTrade) -> Trade:
        """Execute a simulated paper trade.

        Args:
            proposed_trade: Proposed trade

        Returns:
            Trade object
        """
        market = proposed_trade.market
        size = proposed_trade.size
        side = proposed_trade.side

        # Determine entry price (simulate slippage)
        if side == OrderSide.YES:
            base_price = market.yes_price
            # Simulate slippage (0.5%)
            slippage = Decimal("0.005")
            entry_price = base_price * (1 + slippage)
        else:
            base_price = market.no_price
            slippage = Decimal("0.005")
            entry_price = base_price * (1 + slippage)

        # Ensure price is in valid range
        entry_price = max(Decimal("0.01"), min(Decimal("0.99"), entry_price))

        # Calculate cost (size * price + simulated fees)
        fee_rate = Decimal("0.02")  # 2% fee
        cost = size * entry_price * (1 + fee_rate)

        # Create trade record
        trade = Trade(
            id=f"paper_{market.id}_{datetime.now().timestamp()}",
            order_id=f"paper_order_{datetime.now().timestamp()}",
            market_id=market.id,
            side=side,
            direction=proposed_trade.direction,
            entry_price=entry_price,
            size=size,
            cost=cost,
            current_price=entry_price,
            pnl=Decimal(0),
            pnl_percentage=Decimal(0),
            prediction_id=proposed_trade.prediction.market_id,
            news_context=proposed_trade.prediction.news_context,
            is_paper_trade=True,
            notes=f"Paper trade based on prediction. Edge: {proposed_trade.prediction.edge:.2%}",
        )

        logger.info(
            "paper_trade_executed",
            trade_id=trade.id,
            market_id=market.id,
            entry_price=float(entry_price),
            size=float(size),
            cost=float(cost),
        )

        return trade


class RealTradingStrategy(TradeExecutionStrategy):
    """Real trading execution strategy using Polymarket API."""

    def __init__(self, polymarket_client: Optional[PolymarketClient] = None):
        """Initialize real trading strategy.

        Args:
            polymarket_client: Polymarket client for real trading
        """
        # CRITICAL SAFETY CHECK
        logger.critical(
            "🚨 REAL TRADING MODE ENABLED - ACTUAL FUNDS AT RISK 🚨",
            wallet_address=config.settings.polygon_wallet_address,
        )

        # Require explicit confirmation via environment variable
        if not os.getenv("I_CONFIRM_REAL_TRADING"):
            raise RuntimeError(
                "Real trading requires I_CONFIRM_REAL_TRADING=true environment variable. "
                "This is a safety mechanism to prevent accidental real trades. "
                "Set this environment variable ONLY if you understand the risks."
            )

        self.polymarket_client = polymarket_client or PolymarketClient()

    async def execute(self, proposed_trade: ProposedTrade) -> Optional[Trade]:
        """Execute a real trade on Polymarket.

        Args:
            proposed_trade: Proposed trade

        Returns:
            Trade object if successful, None if failed
        """
        market = proposed_trade.market
        size = proposed_trade.size
        side = proposed_trade.side
        max_slippage = proposed_trade.max_slippage

        try:
            # Get market token ID (would need to be derived from market data)
            token_id = market.id  # Placeholder

            # Execute market order with slippage protection
            order = self.polymarket_client.execute_market_order(
                token_id=token_id,
                size=size,
                side=side,
                max_slippage=max_slippage,
            )

            # Wait for order to fill (simplified)
            # In production, would poll order status

            # Create trade record (would get actual fill data)
            trade = Trade(
                id=f"trade_{market.id}_{datetime.now().timestamp()}",
                order_id=order.id or "unknown",
                market_id=market.id,
                side=side,
                direction=proposed_trade.direction,
                entry_price=order.price,
                size=size,
                cost=order.price * size,
                current_price=order.price,
                prediction_id=proposed_trade.prediction.market_id,
                news_context=proposed_trade.prediction.news_context,
                is_paper_trade=False,
            )

            logger.info(
                "real_trade_executed",
                trade_id=trade.id,
                market_id=market.id,
                order_id=order.id,
            )

            return trade

        except Exception as e:
            logger.error(
                "real_trade_execution_failed",
                market_id=market.id,
                error=str(e),
            )
            return None


class BacktestingStrategy(TradeExecutionStrategy):
    """Backtesting execution strategy using historical data."""

    def __init__(self, historical_prices: dict):
        """Initialize backtesting strategy.

        Args:
            historical_prices: Dict of historical prices by market_id and timestamp
        """
        self.historical_prices = historical_prices

    async def execute(self, proposed_trade: ProposedTrade) -> Trade:
        """Execute a simulated backtest trade using historical prices.

        Args:
            proposed_trade: Proposed trade

        Returns:
            Trade object
        """
        market = proposed_trade.market
        size = proposed_trade.size
        side = proposed_trade.side

        # Get historical price (in real implementation, would look up from historical data)
        # For now, use current market price as placeholder
        if side == OrderSide.YES:
            entry_price = market.yes_price
        else:
            entry_price = market.no_price

        # Calculate cost without fees for backtesting purity
        cost = size * entry_price

        # Create trade record
        trade = Trade(
            id=f"backtest_{market.id}_{datetime.now().timestamp()}",
            order_id=f"backtest_order_{datetime.now().timestamp()}",
            market_id=market.id,
            side=side,
            direction=proposed_trade.direction,
            entry_price=entry_price,
            size=size,
            cost=cost,
            current_price=entry_price,
            pnl=Decimal(0),
            pnl_percentage=Decimal(0),
            prediction_id=proposed_trade.prediction.market_id,
            news_context=proposed_trade.prediction.news_context,
            is_paper_trade=True,  # Mark as paper for portfolio tracking
            notes=f"Backtest trade. Edge: {proposed_trade.prediction.edge:.2%}",
        )

        logger.debug(
            "backtest_trade_executed",
            trade_id=trade.id,
            market_id=market.id,
            entry_price=float(entry_price),
        )

        return trade
