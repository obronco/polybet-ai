"""Trading Agent - Executes trades on Polymarket."""

import os
from datetime import datetime
from decimal import Decimal
from typing import Optional

from ..api.polymarket import PolymarketClient
from ..models.market import Market, OrderSide
from ..models.trade import (
    Portfolio,
    Prediction,
    ProposedTrade,
    RiskAssessment,
    Trade,
    TradeDirection,
)
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TradingAgent:
    """Agent responsible for executing trades."""

    def __init__(self, paper_trading: bool = True):
        """Initialize Trading Agent.

        Args:
            paper_trading: Whether to use paper trading mode
        """
        self.paper_trading = paper_trading or config.settings.paper_trading_mode
        self.polymarket_client = None

        if not self.paper_trading:
            # CRITICAL SAFETY CHECK: Real trading mode
            logger.critical(
                "🚨 REAL TRADING MODE ENABLED - ACTUAL FUNDS AT RISK 🚨",
                wallet_address=config.settings.polygon_wallet_address
            )

            # Require explicit confirmation via environment variable
            if not os.getenv("I_CONFIRM_REAL_TRADING"):
                raise RuntimeError(
                    "Real trading requires I_CONFIRM_REAL_TRADING=true environment variable. "
                    "This is a safety mechanism to prevent accidental real trades. "
                    "Set this environment variable ONLY if you understand the risks."
                )

            self.polymarket_client = PolymarketClient()

        self.portfolio = Portfolio(
            balance=Decimal(
                str(config.risk_config.get("paper_trading", {}).get("initial_balance", 10000))
            ),
            initial_balance=Decimal(
                str(config.risk_config.get("paper_trading", {}).get("initial_balance", 10000))
            ),
        )

        logger.info(
            "trading_agent_initialized",
            paper_trading=self.paper_trading,
            initial_balance=float(self.portfolio.balance),
        )

    async def execute_trade(
        self,
        prediction: Prediction,
        risk_assessment: RiskAssessment,
        market: Market,
    ) -> Optional[Trade]:
        """Execute a trade based on prediction and risk assessment.

        Args:
            prediction: AI prediction
            risk_assessment: Risk assessment
            market: Market to trade

        Returns:
            Trade object if executed, None if rejected
        """
        if not risk_assessment.approved:
            logger.warning(
                "trade_rejected",
                market_id=market.id,
                reason="risk_assessment_failed",
            )
            return None

        logger.info(
            "executing_trade",
            market_id=market.id,
            size=float(risk_assessment.recommended_size),
            paper_trading=self.paper_trading,
        )

        # Create proposed trade
        proposed_trade = ProposedTrade(
            market=market,
            prediction=prediction,
            risk_assessment=risk_assessment,
            side=OrderSide.YES if prediction.direction == TradeDirection.LONG else OrderSide.NO,
            direction=prediction.direction,
            size=risk_assessment.recommended_size,
        )

        # Execute trade
        if self.paper_trading:
            trade = await self._execute_paper_trade(proposed_trade)
        else:
            trade = await self._execute_real_trade(proposed_trade)

        # Update portfolio
        if trade:
            self.portfolio.open_trades.append(trade)
            self.portfolio.total_trades += 1
            self.portfolio.updated_at = datetime.now()

        return trade

    async def _execute_paper_trade(self, proposed_trade: ProposedTrade) -> Trade:
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

    async def _execute_real_trade(self, proposed_trade: ProposedTrade) -> Optional[Trade]:
        """Execute a real trade on Polymarket.

        Args:
            proposed_trade: Proposed trade

        Returns:
            Trade object if successful, None if failed
        """
        if not self.polymarket_client:
            logger.error("polymarket_client_not_initialized")
            return None

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

    async def update_open_positions(self, markets: dict) -> None:
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

    async def close_position(
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

    async def apply_exit_rules(self, markets: dict) -> int:
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
                market.yes_price
                if trade.side == OrderSide.YES
                else market.no_price
            )

            # Update P&L
            trade.update_pnl(current_price)

            if not trade.pnl_percentage:
                continue

            # Check stop loss
            if trade.pnl_percentage <= -stop_loss_pct * 100:
                await self.close_position(
                    trade, current_price, "stop_loss_triggered"
                )
                closed_count += 1

            # Check take profit
            elif trade.pnl_percentage >= take_profit_pct * 100:
                await self.close_position(
                    trade, current_price, "take_profit_triggered"
                )
                closed_count += 1

        if closed_count > 0:
            logger.info("exit_rules_applied", positions_closed=closed_count)

        return closed_count

    def get_portfolio_summary(self) -> dict:
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
