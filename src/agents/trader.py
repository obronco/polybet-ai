"""Trading Agent - Executes trades on Polymarket."""

import os
from datetime import datetime
from decimal import Decimal
from typing import Optional

from ..api.polymarket import PolymarketClient
from ..models.market import Market, OrderSide
from ..models.trade import (
    Prediction,
    ProposedTrade,
    RiskAssessment,
    Trade,
    TradeDirection,
)
from ..services.portfolio_service import PortfolioService
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TradingAgent:
    """Agent responsible for executing trades."""

    def __init__(
        self,
        paper_trading: bool = True,
        polymarket_client: Optional[PolymarketClient] = None,
        portfolio_service: Optional[PortfolioService] = None,
    ):
        """Initialize Trading Agent.

        Args:
            paper_trading: Whether to use paper trading mode
            polymarket_client: Polymarket client instance (creates default if needed for real trading)
            portfolio_service: Portfolio service instance (creates default if None)
        """
        self.paper_trading = paper_trading or config.settings.paper_trading_mode

        if not self.paper_trading:
            # CRITICAL SAFETY CHECK: Real trading mode
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
        else:
            self.polymarket_client = polymarket_client  # May be None for paper trading

        # Use injected portfolio service or create default
        if portfolio_service is None:
            initial_balance = Decimal(
                str(
                    config.risk_config.get("paper_trading", {}).get(
                        "initial_balance", 10000
                    )
                )
            )
            self.portfolio_service = PortfolioService(initial_balance=initial_balance)
        else:
            self.portfolio_service = portfolio_service

        # Backwards compatibility: expose portfolio attribute
        self.portfolio = self.portfolio_service.portfolio

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
            side=OrderSide.YES
            if prediction.direction == TradeDirection.LONG
            else OrderSide.NO,
            direction=prediction.direction,
            size=risk_assessment.recommended_size,
        )

        # Execute trade
        if self.paper_trading:
            trade = await self._execute_paper_trade(proposed_trade)
        else:
            trade = await self._execute_real_trade(proposed_trade)

        # Add to portfolio
        if trade:
            self.portfolio_service.add_trade(trade)

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

    async def _execute_real_trade(
        self, proposed_trade: ProposedTrade
    ) -> Optional[Trade]:
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

        Delegates to portfolio service.

        Args:
            markets: Dict mapping market_id to current Market data
        """
        self.portfolio_service.update_open_positions(markets)

    async def close_position(
        self,
        trade: Trade,
        exit_price: Decimal,
        reason: str = "manual_close",
    ) -> Trade:
        """Close an open position.

        Delegates to portfolio service.

        Args:
            trade: Trade to close
            exit_price: Exit price
            reason: Reason for closing

        Returns:
            Updated Trade object
        """
        return self.portfolio_service.close_position(trade, exit_price, reason)

    async def apply_exit_rules(self, markets: dict) -> int:
        """Apply exit rules to open positions.

        Delegates to portfolio service.

        Args:
            markets: Dict of current market data

        Returns:
            Number of positions closed
        """
        return self.portfolio_service.apply_exit_rules(markets)

    def get_portfolio_summary(self) -> dict:
        """Get portfolio summary.

        Delegates to portfolio service.

        Returns:
            Dict with portfolio statistics
        """
        return self.portfolio_service.get_summary()
