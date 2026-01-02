"""Trading Agent - Executes trades on Polymarket."""

from decimal import Decimal
from typing import Optional

from ..models.market import Market, OrderSide
from ..models.trade import (
    Prediction,
    ProposedTrade,
    RiskAssessment,
    Trade,
    TradeDirection,
)
from ..services.portfolio_service import PortfolioService
from ..strategies.trade_execution import (
    PaperTradingStrategy,
    RealTradingStrategy,
    TradeExecutionStrategy,
)
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TradingAgent:
    """Agent responsible for executing trades."""

    def __init__(
        self,
        paper_trading: bool = True,
        execution_strategy: Optional[TradeExecutionStrategy] = None,
        portfolio_service: Optional[PortfolioService] = None,
    ):
        """Initialize Trading Agent.

        Args:
            paper_trading: Whether to use paper trading mode (ignored if execution_strategy provided)
            execution_strategy: Trade execution strategy (creates default based on paper_trading if None)
            portfolio_service: Portfolio service instance (creates default if None)
        """
        # Use injected execution strategy or create default
        if execution_strategy is None:
            paper_trading = paper_trading or config.settings.paper_trading_mode
            if paper_trading:
                self.execution_strategy = PaperTradingStrategy()
            else:
                self.execution_strategy = RealTradingStrategy()
        else:
            self.execution_strategy = execution_strategy

        # Backwards compatibility
        self.paper_trading = isinstance(self.execution_strategy, PaperTradingStrategy)

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
            execution_strategy=type(self.execution_strategy).__name__,
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

        # Execute trade using strategy
        trade = await self.execution_strategy.execute(proposed_trade)

        # Add to portfolio
        if trade:
            self.portfolio_service.add_trade(trade)

        return trade

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
