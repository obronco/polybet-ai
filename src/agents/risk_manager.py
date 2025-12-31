"""Risk Management Agent - Validates trades and enforces risk limits."""

from decimal import Decimal
from typing import Dict, List, Optional

from ..models.market import Market
from ..models.trade import Portfolio, Prediction, ProposedTrade, RiskAssessment, TradeDirection
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RiskManagerAgent:
    """Agent responsible for risk management and trade validation."""

    def __init__(self):
        """Initialize Risk Manager Agent."""
        self.risk_config = config.get_risk_limits()
        self.position_config = config.get_position_sizing_config()
        self.circuit_breaker_config = config.get_circuit_breaker_config()
        self.circuit_breaker_active = False
        logger.info("risk_manager_agent_initialized")

    async def validate_trade(
        self,
        prediction: Prediction,
        market: Market,
        portfolio: Portfolio,
    ) -> RiskAssessment:
        """Validate if a proposed trade meets risk criteria.

        Args:
            prediction: AI prediction
            market: Market to trade
            portfolio: Current portfolio state

        Returns:
            RiskAssessment object
        """
        logger.info("validating_trade", market_id=market.id)

        checks_passed = []
        checks_failed = []
        warnings = []

        # 1. Circuit breaker check
        if self.circuit_breaker_active:
            checks_failed.append("Circuit breaker is active")
            return self._create_rejection(
                checks_failed, "Circuit breaker triggered"
            )

        # 2. Edge requirement
        min_edge = self.risk_config.get("min_edge", 0.05)
        if abs(float(prediction.edge)) >= min_edge:
            checks_passed.append(f"Edge ({prediction.edge:.2%}) meets minimum")
        else:
            checks_failed.append(
                f"Edge ({prediction.edge:.2%}) below minimum ({min_edge:.2%})"
            )

        # 3. Confidence requirement
        min_confidence = self.risk_config.get("min_confidence", 6)
        if prediction.confidence >= min_confidence:
            checks_passed.append(
                f"Confidence ({prediction.confidence}/10) meets minimum"
            )
        else:
            checks_failed.append(
                f"Confidence ({prediction.confidence}/10) below minimum ({min_confidence}/10)"
            )

        # 4. Market liquidity check
        min_liquidity = Decimal(str(self.risk_config.get("min_liquidity_for_size", 0)))
        if market.liquidity >= min_liquidity:
            checks_passed.append(f"Liquidity (${market.liquidity:,.0f}) sufficient")
        else:
            checks_failed.append(
                f"Liquidity (${market.liquidity:,.0f}) below minimum"
            )

        # 5. Portfolio limits
        max_positions = self.risk_config.get("max_concurrent_positions", 10)
        current_positions = len(portfolio.open_trades)
        if current_positions < max_positions:
            checks_passed.append(
                f"Open positions ({current_positions}) below limit"
            )
        else:
            checks_failed.append(
                f"Maximum positions ({max_positions}) reached"
            )

        # 6. Daily loss limit
        max_daily_loss_pct = self.risk_config.get("max_daily_loss_pct", 0.10)
        max_daily_loss = portfolio.initial_balance * Decimal(
            str(max_daily_loss_pct)
        )
        if abs(portfolio.daily_pnl) < max_daily_loss:
            checks_passed.append("Daily loss limit not exceeded")
        else:
            checks_failed.append(
                f"Daily loss limit exceeded (${abs(portfolio.daily_pnl):,.2f})"
            )

        # Calculate position size
        recommended_size = self.calculate_position_size(
            prediction=prediction,
            portfolio=portfolio,
            market=market,
        )

        max_size = portfolio.initial_balance * Decimal(
            str(self.position_config.get("max_bet_size_pct", 0.03))
        )

        # 7. Position size validation
        if recommended_size <= max_size:
            checks_passed.append(f"Position size ${recommended_size:,.2f} within limits")
        else:
            warnings.append(
                f"Recommended size capped at ${max_size:,.2f}"
            )
            recommended_size = max_size

        # 8. Available balance check
        if recommended_size <= portfolio.available_balance:
            checks_passed.append("Sufficient balance available")
        else:
            checks_failed.append(
                f"Insufficient balance (need ${recommended_size:,.2f}, have ${portfolio.available_balance:,.2f})"
            )

        # Determine approval
        approved = len(checks_failed) == 0

        # Calculate risk score (0-1, higher = riskier)
        risk_score = self._calculate_risk_score(
            prediction, market, portfolio, recommended_size
        )

        assessment = RiskAssessment(
            approved=approved,
            risk_score=risk_score,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
            recommended_size=recommended_size,
            max_size=max_size,
            kelly_size=self._calculate_kelly_size(prediction, portfolio),
            current_exposure=self._calculate_category_exposure(
                portfolio, market.category
            ),
            daily_loss=abs(portfolio.daily_pnl),
            open_positions=current_positions,
        )

        logger.info(
            "trade_validation_complete",
            approved=approved,
            recommended_size=float(recommended_size),
            risk_score=risk_score,
        )

        return assessment

    def calculate_position_size(
        self,
        prediction: Prediction,
        portfolio: Portfolio,
        market: Market,
    ) -> Decimal:
        """Calculate recommended position size.

        Args:
            prediction: AI prediction
            portfolio: Current portfolio
            market: Market to trade

        Returns:
            Recommended position size in USD
        """
        method = self.position_config.get("method", "kelly_criterion")

        if method == "kelly_criterion":
            kelly_size = self._calculate_kelly_size(prediction, portfolio)

            # Apply Kelly fraction for conservative sizing
            kelly_fraction = Decimal(
                str(self.position_config.get("kelly_fraction", 0.25))
            )
            recommended = kelly_size * kelly_fraction

        elif method == "fixed_fraction":
            fraction = Decimal(
                str(self.position_config.get("max_bet_size_pct", 0.03))
            )
            recommended = portfolio.balance * fraction

        else:  # fixed_amount
            recommended = Decimal(
                str(self.position_config.get("min_bet_size_usd", 10))
            )

        # Apply min/max constraints
        min_size = Decimal(str(self.position_config.get("min_bet_size_usd", 10)))
        max_size = Decimal(str(self.position_config.get("max_bet_size_usd", 1000)))

        recommended = max(min_size, min(max_size, recommended))

        # Adjust based on confidence
        confidence_multiplier = self._get_confidence_multiplier(
            prediction.confidence
        )
        recommended = recommended * Decimal(str(confidence_multiplier))

        logger.debug("position_size_calculated", size=float(recommended))

        return recommended

    def _calculate_kelly_size(
        self,
        prediction: Prediction,
        portfolio: Portfolio,
    ) -> Decimal:
        """Calculate Kelly Criterion position size.

        Args:
            prediction: AI prediction
            portfolio: Current portfolio

        Returns:
            Kelly size in USD
        """
        # Kelly formula: f = (bp - q) / b
        # where:
        # f = fraction of bankroll to bet
        # b = odds received (profit/stake)
        # p = probability of winning
        # q = probability of losing (1 - p)

        p = float(prediction.predicted_probability)
        q = 1 - p

        # Calculate odds (simplified for binary market)
        if prediction.direction == TradeDirection.LONG:
            # Buying YES at current price
            price = float(prediction.current_market_price)
            b = (1 - price) / price if price > 0 else 0
        else:
            # Buying NO
            price = 1 - float(prediction.current_market_price)
            b = (1 - price) / price if price > 0 else 0

        # Kelly fraction
        if b > 0:
            kelly_fraction = (b * p - q) / b
        else:
            kelly_fraction = 0

        # Kelly fraction should be between 0 and 1
        kelly_fraction = max(0, min(1, kelly_fraction))

        # Calculate kelly size
        kelly_size = portfolio.balance * Decimal(str(kelly_fraction))

        logger.debug("kelly_size_calculated", kelly_fraction=kelly_fraction, size=float(kelly_size))

        return kelly_size

    def _get_confidence_multiplier(self, confidence: int) -> float:
        """Get position size multiplier based on confidence.

        Args:
            confidence: Confidence score (1-10)

        Returns:
            Multiplier (0-1)
        """
        confidence_multipliers = config.risk_config.get(
            "confidence_multipliers",
            {"very_high": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25},
        )

        if confidence >= 9:
            return confidence_multipliers.get("very_high", 1.0)
        elif confidence >= 7:
            return confidence_multipliers.get("high", 0.75)
        elif confidence >= 5:
            return confidence_multipliers.get("medium", 0.5)
        else:
            return confidence_multipliers.get("low", 0.25)

    def _calculate_risk_score(
        self,
        prediction: Prediction,
        market: Market,
        portfolio: Portfolio,
        position_size: Decimal,
    ) -> float:
        """Calculate overall risk score for a trade.

        Args:
            prediction: Prediction object
            market: Market object
            portfolio: Portfolio object
            position_size: Proposed position size

        Returns:
            Risk score (0-1, higher = riskier)
        """
        # Factors that increase risk:
        # - Low confidence
        # - Small edge
        # - Low liquidity
        # - Large position relative to bankroll
        # - High portfolio concentration

        risk_factors = []

        # Confidence risk (inverse)
        confidence_risk = (10 - prediction.confidence) / 10
        risk_factors.append(confidence_risk * 0.3)

        # Edge risk (inverse)
        edge = abs(float(prediction.edge))
        edge_risk = max(0, 1 - (edge / 0.2))  # 20% edge = 0 risk
        risk_factors.append(edge_risk * 0.3)

        # Liquidity risk
        liquidity = float(market.liquidity)
        liquidity_risk = max(0, 1 - (liquidity / 100000))  # $100k = 0 risk
        risk_factors.append(liquidity_risk * 0.2)

        # Position size risk
        size_pct = float(position_size / portfolio.balance) if portfolio.balance > 0 else 1
        size_risk = min(1, size_pct / 0.05)  # 5% = full risk
        risk_factors.append(size_risk * 0.2)

        total_risk = sum(risk_factors)

        return min(1.0, total_risk)

    def _calculate_category_exposure(
        self,
        portfolio: Portfolio,
        category: str,
    ) -> Decimal:
        """Calculate current exposure in a category.

        Args:
            portfolio: Portfolio object
            category: Market category

        Returns:
            Total exposure in USD
        """
        # This would need market data for each trade
        # Placeholder for now
        return Decimal(0)

    def check_circuit_breaker(self, portfolio: Portfolio) -> bool:
        """Check if circuit breaker should be triggered.

        Args:
            portfolio: Current portfolio

        Returns:
            True if circuit breaker triggered
        """
        if not self.circuit_breaker_config.get("enabled", True):
            return False

        # Daily loss threshold
        daily_loss_threshold = Decimal(
            str(self.circuit_breaker_config.get("daily_loss_threshold_pct", 0.15))
        )
        if abs(portfolio.daily_pnl) >= portfolio.initial_balance * daily_loss_threshold:
            logger.warning("circuit_breaker_triggered", reason="daily_loss_threshold")
            self.circuit_breaker_active = True
            return True

        # Consecutive losses (would need trade history)

        return False

    def reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker."""
        self.circuit_breaker_active = False
        logger.info("circuit_breaker_reset")

    def _create_rejection(
        self,
        reasons: List[str],
        summary: str,
    ) -> RiskAssessment:
        """Create a rejection assessment.

        Args:
            reasons: List of rejection reasons
            summary: Summary message

        Returns:
            RiskAssessment with approved=False
        """
        return RiskAssessment(
            approved=False,
            risk_score=1.0,
            checks_passed=[],
            checks_failed=reasons,
            warnings=[summary],
            recommended_size=Decimal(0),
            max_size=Decimal(0),
        )
