"""Position Manager - Manages open positions and applies exit rules."""

from decimal import Decimal
from typing import Dict, List, Optional

from ..agents.trader import TradingAgent
from ..models.market import Market
from ..models.trade import Trade
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PositionManager:
    """Manages portfolio positions and exit rules."""

    def __init__(self, trader: Optional[TradingAgent] = None):
        """Initialize Position Manager.

        Args:
            trader: Trading agent (creates default if None)
        """
        self.trader = trader or TradingAgent(paper_trading=True)
        logger.info("position_manager_initialized")

    async def update_and_exit(
        self,
        markets: Optional[Dict[str, Market]] = None,
    ) -> List[Trade]:
        """Update positions and apply exit rules.

        Args:
            markets: Dict mapping market_id to Market objects with current prices

        Returns:
            List of closed Trade objects
        """
        logger.info("updating_positions_and_exits")

        closed_trades = []

        try:
            if markets:
                # Update P&L for open positions
                self.trader.update_open_positions(markets)

                # Apply exit rules
                closed_count = await self.trader.apply_exit_rules(markets)

                if closed_count > 0:
                    logger.info("positions_closed_by_exit_rules", count=closed_count)

                # Get closed trades from portfolio
                closed_trades = [
                    trade
                    for trade in self.trader.portfolio.open_trades
                    if trade.status.value in ["closed", "exit"]
                ]

        except Exception as e:
            logger.error("position_update_error", error=str(e))

        return closed_trades

    async def close_position(
        self,
        trade: Trade,
        exit_price: Decimal,
        reason: str = "manual_close",
    ) -> Optional[Trade]:
        """Manually close a position.

        Args:
            trade: Trade to close
            exit_price: Exit price
            reason: Reason for closing

        Returns:
            Updated Trade object or None
        """
        logger.info("closing_position", trade_id=trade.id, reason=reason)

        try:
            closed_trade = await self.trader.close_position(
                trade=trade,
                exit_price=exit_price,
                reason=reason,
            )

            if closed_trade:
                logger.info(
                    "position_closed",
                    trade_id=closed_trade.id,
                    pnl=float(closed_trade.pnl) if closed_trade.pnl else 0,
                )

            return closed_trade

        except Exception as e:
            logger.error("close_position_error", trade_id=trade.id, error=str(e))
            return None

    def get_open_positions(self) -> List[Trade]:
        """Get all open positions.

        Returns:
            List of open Trade objects
        """
        return self.trader.portfolio.open_trades

    def get_position_count(self) -> int:
        """Get count of open positions.

        Returns:
            Number of open positions
        """
        return len(self.trader.portfolio.open_trades)

    def get_total_exposure(self) -> Decimal:
        """Get total capital exposed in open positions.

        Returns:
            Total exposure amount
        """
        total = Decimal("0")

        for trade in self.trader.portfolio.open_trades:
            total += trade.cost

        return total

    def get_available_balance(self) -> Decimal:
        """Get available balance for new trades.

        Returns:
            Available balance
        """
        return self.trader.portfolio.available_balance

    def get_portfolio_summary(self) -> dict:
        """Get comprehensive portfolio summary.

        Returns:
            Dict with portfolio statistics
        """
        summary = self.trader.get_portfolio_summary()

        # Add position-specific metrics
        summary["total_exposure"] = float(self.get_total_exposure())
        summary["exposure_pct"] = (
            float(self.get_total_exposure() / self.trader.portfolio.balance * 100)
            if self.trader.portfolio.balance > 0
            else 0
        )

        return summary

    def check_position_limits(self) -> bool:
        """Check if we can open more positions.

        Returns:
            True if we can open more positions
        """
        max_positions = self.trader.portfolio.max_positions or 10
        current_positions = self.get_position_count()

        can_open = current_positions < max_positions

        if not can_open:
            logger.warning(
                "position_limit_reached",
                current=current_positions,
                max=max_positions,
            )

        return can_open

    def get_position_by_market(self, market_id: str) -> Optional[Trade]:
        """Get open position for a specific market.

        Args:
            market_id: Market identifier

        Returns:
            Trade object if position exists, None otherwise
        """
        for trade in self.trader.portfolio.open_trades:
            if trade.market_id == market_id:
                return trade

        return None

    def has_position_in_market(self, market_id: str) -> bool:
        """Check if we have an open position in a market.

        Args:
            market_id: Market identifier

        Returns:
            True if position exists
        """
        return self.get_position_by_market(market_id) is not None

    async def close_all_positions(
        self,
        markets: Dict[str, Market],
        reason: str = "close_all",
    ) -> List[Trade]:
        """Close all open positions.

        Args:
            markets: Dict mapping market_id to Market objects
            reason: Reason for closing all

        Returns:
            List of closed Trade objects
        """
        logger.info("closing_all_positions", count=self.get_position_count())

        closed_trades = []

        for trade in self.get_open_positions():
            market = markets.get(trade.market_id)
            if not market:
                logger.warning(
                    "market_not_found_for_close",
                    market_id=trade.market_id,
                )
                continue

            # Get current price
            from ..models.trade import OrderSide

            exit_price = (
                market.yes_price if trade.side == OrderSide.YES else market.no_price
            )

            # Close position
            closed_trade = await self.close_position(trade, exit_price, reason)

            if closed_trade:
                closed_trades.append(closed_trade)

        logger.info("all_positions_closed", count=len(closed_trades))

        return closed_trades
