"""Portfolio Service - Manages portfolio state and positions."""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from ..models.market import Market, OrderSide
from ..models.trade import Portfolio, Trade
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PortfolioService:
    """Manages portfolio state and position lifecycle."""

    def __init__(self, initial_balance: Decimal):
        """Initialize Portfolio Service.

        Args:
            initial_balance: Starting balance for the portfolio
        """
        self.portfolio = Portfolio(
            balance=initial_balance,
            initial_balance=initial_balance,
        )

        logger.info(
            "portfolio_service_initialized",
            initial_balance=float(initial_balance),
        )

    def update_open_positions(self, markets: Dict[str, Market]) -> None:
        """Update P&L for open positions.

        Args:
            markets: Dict mapping market_id to current Market data
        """
        logger.debug("updating_open_positions", count=len(self.portfolio.open_trades))

        total_pnl = Decimal(0)

        for trade in self.portfolio.open_trades:
            if trade.closed:
                continue

            # Get current market price
            market = markets.get(trade.market_id)
            if not market:
                continue

            # Update trade P&L
            if trade.side == OrderSide.YES:
                current_price = market.yes_price
            else:
                current_price = market.no_price

            trade.update_pnl(current_price)
            total_pnl += trade.pnl

        self.portfolio.total_pnl = total_pnl
        self.portfolio.updated_at = datetime.now()

        logger.debug("positions_updated", total_pnl=float(total_pnl))

    def add_trade(self, trade: Trade) -> None:
        """Add a new trade to the portfolio.

        Args:
            trade: Trade to add
        """
        self.portfolio.open_trades.append(trade)
        self.portfolio.total_trades += 1
        self.portfolio.updated_at = datetime.now()

        logger.debug(
            "trade_added_to_portfolio",
            trade_id=trade.id,
            total_trades=self.portfolio.total_trades,
        )

    def close_position(
        self,
        trade: Trade,
        exit_price: Decimal,
        reason: str = "manual_close",
    ) -> Trade:
        """Close an open position.

        Args:
            trade: Trade to close
            exit_price: Exit price
            reason: Reason for closing

        Returns:
            Updated Trade object
        """
        logger.info(
            "closing_position",
            trade_id=trade.id,
            exit_price=float(exit_price),
            reason=reason,
        )

        # Update trade
        trade.exit_price = exit_price
        trade.exit_at = datetime.now()
        trade.closed = True
        trade.update_pnl(exit_price)
        trade.notes += f"\nClosed: {reason}"

        # Update portfolio
        self.portfolio.open_trades.remove(trade)
        self.portfolio.closed_trades.append(trade)

        if trade.is_profitable:
            self.portfolio.winning_trades += 1
        else:
            self.portfolio.losing_trades += 1

        # Update balance
        self.portfolio.balance += trade.pnl

        logger.info(
            "position_closed",
            trade_id=trade.id,
            pnl=float(trade.pnl),
            new_balance=float(self.portfolio.balance),
        )

        return trade

    def apply_exit_rules(self, markets: Dict[str, Market]) -> int:
        """Apply exit rules to open positions.

        Args:
            markets: Dict of current market data

        Returns:
            Number of positions closed
        """
        exit_rules = config.risk_config.get("exit_rules", {})
        if not exit_rules.get("use_stop_loss", False):
            return 0

        stop_loss_pct = Decimal(str(exit_rules.get("stop_loss_pct", 0.5)))
        take_profit_pct = Decimal(str(exit_rules.get("take_profit_pct", 0.8)))

        closed_count = 0

        for trade in list(self.portfolio.open_trades):
            if trade.closed:
                continue

            market = markets.get(trade.market_id)
            if not market:
                continue

            # Get current price
            current_price = (
                market.yes_price if trade.side == OrderSide.YES else market.no_price
            )

            # Update P&L
            trade.update_pnl(current_price)

            if not trade.pnl_percentage:
                continue

            # Check stop loss
            if trade.pnl_percentage <= -stop_loss_pct * 100:
                self.close_position(trade, current_price, "stop_loss_triggered")
                closed_count += 1

            # Check take profit
            elif trade.pnl_percentage >= take_profit_pct * 100:
                self.close_position(trade, current_price, "take_profit_triggered")
                closed_count += 1

        if closed_count > 0:
            logger.info("exit_rules_applied", positions_closed=closed_count)

        return closed_count

    def get_summary(self) -> dict:
        """Get portfolio summary.

        Returns:
            Dict with portfolio statistics
        """
        return {
            "balance": float(self.portfolio.balance),
            "total_pnl": float(self.portfolio.total_pnl),
            "roi": self.portfolio.roi,
            "total_trades": self.portfolio.total_trades,
            "open_positions": len(self.portfolio.open_trades),
            "winning_trades": self.portfolio.winning_trades,
            "losing_trades": self.portfolio.losing_trades,
            "win_rate": self.portfolio.win_rate,
            "available_balance": float(self.portfolio.available_balance),
        }

    def get_open_trades(self) -> List[Trade]:
        """Get all open trades.

        Returns:
            List of open Trade objects
        """
        return self.portfolio.open_trades

    def get_closed_trades(self) -> List[Trade]:
        """Get all closed trades.

        Returns:
            List of closed Trade objects
        """
        return self.portfolio.closed_trades

    def get_balance(self) -> Decimal:
        """Get current portfolio balance.

        Returns:
            Current balance
        """
        return self.portfolio.balance

    def get_available_balance(self) -> Decimal:
        """Get available balance for new trades.

        Returns:
            Available balance
        """
        return self.portfolio.available_balance
