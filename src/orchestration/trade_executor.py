"""Trade Executor - Validates and executes trades."""

from typing import List, Optional

from ..agents.risk_manager import RiskManagerAgent
from ..agents.trader import TradingAgent
from ..models.market import Market
from ..models.trade import Prediction, ProposedTrade, RiskAssessment, Trade
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TradeExecutor:
    """Executes trades after risk validation."""

    def __init__(
        self,
        trader: Optional[TradingAgent] = None,
        risk_manager: Optional[RiskManagerAgent] = None,
    ):
        """Initialize Trade Executor.

        Args:
            trader: Trading agent (creates default if None)
            risk_manager: Risk manager agent (creates default if None)
        """
        self.trader = trader or TradingAgent(paper_trading=True)
        self.risk_manager = risk_manager or RiskManagerAgent()
        logger.info("trade_executor_initialized")

    async def execute_approved_trades(
        self,
        predictions: List[Prediction],
    ) -> List[Trade]:
        """Execute trades for approved predictions.

        Args:
            predictions: List of predictions to potentially trade

        Returns:
            List of executed Trade objects
        """
        logger.info("executing_approved_trades", num_predictions=len(predictions))

        if not predictions:
            logger.warning("no_predictions_to_execute")
            return []

        executed_trades = []

        for prediction in predictions:
            try:
                # Get market from prediction
                market = await self._get_market(prediction.market_id)
                if not market:
                    logger.warning("market_not_found", market_id=prediction.market_id)
                    continue

                # Validate trade with risk manager
                risk_assessment = self.risk_manager.validate_trade(
                    prediction=prediction,
                    market=market,
                    portfolio=self.trader.portfolio,
                )

                if not risk_assessment.approved:
                    logger.info(
                        "trade_rejected",
                        market_id=market.id,
                        reasons=risk_assessment.checks_failed,
                    )
                    continue

                # Execute trade
                trade = await self.trader.execute_trade(
                    prediction=prediction,
                    market=market,
                    risk_assessment=risk_assessment,
                )

                if trade:
                    executed_trades.append(trade)
                    logger.info(
                        "trade_executed",
                        trade_id=trade.id,
                        market_id=market.id,
                        size=float(trade.size),
                        direction=trade.direction.value,
                    )
                else:
                    logger.warning("trade_execution_failed", market_id=market.id)

            except Exception as e:
                logger.error(
                    "trade_execution_error",
                    market_id=prediction.market_id,
                    error=str(e),
                )
                continue

        logger.info(
            "trades_execution_complete",
            total_predictions=len(predictions),
            executed=len(executed_trades),
        )

        return executed_trades

    async def execute_single_trade(
        self,
        prediction: Prediction,
        market: Market,
    ) -> Optional[Trade]:
        """Execute a single trade.

        Args:
            prediction: Prediction for the trade
            market: Market to trade

        Returns:
            Trade object if successful, None otherwise
        """
        logger.info("executing_single_trade", market_id=market.id)

        try:
            # Validate with risk manager
            risk_assessment = self.risk_manager.validate_trade(
                prediction=prediction,
                market=market,
                portfolio=self.trader.portfolio,
            )

            if not risk_assessment.approved:
                logger.info(
                    "single_trade_rejected",
                    market_id=market.id,
                    reasons=risk_assessment.checks_failed,
                )
                return None

            # Execute trade
            trade = await self.trader.execute_trade(
                prediction=prediction,
                market=market,
                risk_assessment=risk_assessment,
            )

            if trade:
                logger.info("single_trade_executed", trade_id=trade.id)
            else:
                logger.warning("single_trade_failed", market_id=market.id)

            return trade

        except Exception as e:
            logger.error("single_trade_error", market_id=market.id, error=str(e))
            return None

    def get_risk_assessment(
        self,
        prediction: Prediction,
        market: Market,
    ) -> RiskAssessment:
        """Get risk assessment for a prediction without executing.

        Args:
            prediction: Prediction to assess
            market: Market for the prediction

        Returns:
            RiskAssessment object
        """
        return self.risk_manager.validate_trade(
            prediction=prediction,
            market=market,
            portfolio=self.trader.portfolio,
        )

    def check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is active.

        Returns:
            True if circuit breaker is active (trading should stop)
        """
        is_active = self.risk_manager.circuit_breaker_active

        if is_active:
            logger.warning("circuit_breaker_active")

        return is_active

    async def _get_market(self, market_id: str) -> Optional[Market]:
        """Get market by ID.

        This is a helper method that would typically fetch from
        MarketIntelligenceAgent or cache.

        Args:
            market_id: Market identifier

        Returns:
            Market object or None
        """
        # TODO: Implement market fetching logic
        # For now, this is a placeholder that would need to be
        # integrated with MarketIntelligenceAgent
        logger.debug("fetching_market", market_id=market_id)
        return None

    def get_portfolio_summary(self) -> dict:
        """Get current portfolio summary.

        Returns:
            Dict with portfolio statistics
        """
        return self.trader.get_portfolio_summary()
