"""Position sizing strategies for trade execution."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict

from ..models.trade import Prediction, Portfolio, TradeDirection
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PositionSizingStrategy(ABC):
    """Abstract base class for position sizing strategies."""

    @abstractmethod
    def calculate_size(
        self,
        prediction: Prediction,
        portfolio: Portfolio,
        config: Dict,
    ) -> Decimal:
        """Calculate position size for a trade.

        Args:
            prediction: AI prediction
            portfolio: Current portfolio
            config: Strategy-specific configuration

        Returns:
            Recommended position size in USD
        """
        pass


class KellyCriterionStrategy(PositionSizingStrategy):
    """Kelly Criterion position sizing strategy."""

    def calculate_size(
        self,
        prediction: Prediction,
        portfolio: Portfolio,
        config: Dict,
    ) -> Decimal:
        """Calculate Kelly Criterion position size.

        Args:
            prediction: AI prediction
            portfolio: Current portfolio
            config: Configuration with kelly_fraction

        Returns:
            Kelly size in USD
        """
        kelly_size = self._calculate_kelly_size(prediction, portfolio)

        # Apply Kelly fraction for conservative sizing
        kelly_fraction = Decimal(str(config.get("kelly_fraction", 0.25)))
        recommended = kelly_size * kelly_fraction

        logger.debug(
            "kelly_size_calculated",
            raw_kelly=float(kelly_size),
            fraction=float(kelly_fraction),
            final=float(recommended),
        )

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

        # Ensure non-negative
        kelly_fraction = max(0, kelly_fraction)

        # Apply to bankroll
        kelly_size = Decimal(str(kelly_fraction)) * portfolio.balance

        return kelly_size


class FixedFractionStrategy(PositionSizingStrategy):
    """Fixed fraction of balance position sizing strategy."""

    def calculate_size(
        self,
        prediction: Prediction,
        portfolio: Portfolio,
        config: Dict,
    ) -> Decimal:
        """Calculate position size as fixed fraction of balance.

        Args:
            prediction: AI prediction
            portfolio: Current portfolio
            config: Configuration with max_bet_size_pct

        Returns:
            Position size in USD
        """
        fraction = Decimal(str(config.get("max_bet_size_pct", 0.03)))
        recommended = portfolio.balance * fraction

        logger.debug(
            "fixed_fraction_calculated",
            fraction=float(fraction),
            balance=float(portfolio.balance),
            size=float(recommended),
        )

        return recommended


class FixedAmountStrategy(PositionSizingStrategy):
    """Fixed amount position sizing strategy."""

    def calculate_size(
        self,
        prediction: Prediction,
        portfolio: Portfolio,
        config: Dict,
    ) -> Decimal:
        """Calculate position size as fixed amount.

        Args:
            prediction: AI prediction
            portfolio: Current portfolio
            config: Configuration with min_bet_size_usd

        Returns:
            Position size in USD
        """
        recommended = Decimal(str(config.get("min_bet_size_usd", 10)))

        logger.debug("fixed_amount_calculated", size=float(recommended))

        return recommended


class PositionSizer:
    """Position sizer that uses configurable strategies."""

    STRATEGIES = {
        "kelly_criterion": KellyCriterionStrategy,
        "fixed_fraction": FixedFractionStrategy,
        "fixed_amount": FixedAmountStrategy,
    }

    def __init__(self, config: Dict):
        """Initialize position sizer with configuration.

        Args:
            config: Position sizing configuration
        """
        self.config = config
        self.method = config.get("method", "kelly_criterion")

        if self.method not in self.STRATEGIES:
            logger.warning(
                "unknown_position_sizing_method",
                method=self.method,
                defaulting_to="kelly_criterion",
            )
            self.method = "kelly_criterion"

        self.strategy = self.STRATEGIES[self.method]()
        logger.info("position_sizer_initialized", method=self.method)

    def calculate_size(
        self,
        prediction: Prediction,
        portfolio: Portfolio,
    ) -> Decimal:
        """Calculate position size using configured strategy.

        Args:
            prediction: AI prediction
            portfolio: Current portfolio

        Returns:
            Recommended position size in USD
        """
        # Calculate base size using strategy
        recommended = self.strategy.calculate_size(prediction, portfolio, self.config)

        # Apply min/max constraints
        min_size = Decimal(str(self.config.get("min_bet_size_usd", 10)))
        max_size = Decimal(str(self.config.get("max_bet_size_usd", 1000)))

        recommended = max(min_size, min(max_size, recommended))

        # Adjust based on confidence
        confidence_multiplier = self._get_confidence_multiplier(prediction.confidence)
        recommended = recommended * Decimal(str(confidence_multiplier))

        # Re-apply max constraint after confidence adjustment
        recommended = min(max_size, recommended)

        logger.debug("final_position_size", size=float(recommended))

        return recommended

    def calculate_kelly_size(
        self,
        prediction: Prediction,
        portfolio: Portfolio,
    ) -> Decimal:
        """Calculate Kelly size for reporting (regardless of configured strategy).

        Args:
            prediction: AI prediction
            portfolio: Current portfolio

        Returns:
            Raw Kelly size in USD
        """
        kelly_strategy = KellyCriterionStrategy()
        return kelly_strategy._calculate_kelly_size(prediction, portfolio)

    def _get_confidence_multiplier(self, confidence: int) -> float:
        """Get position size multiplier based on confidence level.

        Args:
            confidence: Confidence level (1-10)

        Returns:
            Multiplier for position size
        """
        # Scale from 0.5x to 1.5x based on confidence
        # Confidence 1-3: 0.5x to 0.8x
        # Confidence 4-7: 0.8x to 1.2x
        # Confidence 8-10: 1.2x to 1.5x

        if confidence <= 3:
            return 0.5 + (confidence - 1) * 0.15  # 0.5 to 0.8
        elif confidence <= 7:
            return 0.8 + (confidence - 4) * 0.1  # 0.8 to 1.2
        else:
            return 1.2 + (confidence - 8) * 0.1  # 1.2 to 1.5
