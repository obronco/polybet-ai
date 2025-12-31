"""Forecasting Agent - Uses LLM to predict market outcomes."""

from decimal import Decimal
from typing import List, Optional

from ..models.market import Market
from ..models.news import NewsArticle
from ..models.trade import Prediction, TradeDirection
from ..utils.llm import llm_client
from ..utils.logger import get_logger
from ..utils.prompts import MARKET_ANALYSIS_TEMPLATE, build_news_context

logger = get_logger(__name__)


class ForecastingAgent:
    """Agent responsible for forecasting market outcomes using AI."""

    def __init__(self, model: Optional[str] = None, temperature: float = 0.7):
        """Initialize Forecasting Agent.

        Args:
            model: LLM model name (defaults to config)
            temperature: Sampling temperature for predictions
        """
        self.model = model
        self.temperature = temperature
        logger.info(
            "forecasting_agent_initialized",
            model=model or "default",
            temperature=temperature,
        )

    async def predict_outcome(
        self,
        market: Market,
        news_context: Optional[List[NewsArticle]] = None,
    ) -> Prediction:
        """Predict the outcome of a market.

        Args:
            market: Market to predict
            news_context: Optional relevant news articles

        Returns:
            Prediction object with probability and reasoning
        """
        logger.info("predicting_market_outcome", market_id=market.id)

        # Build news context string
        if news_context:
            news_text = build_news_context(
                [
                    {
                        "source_name": a.source_name,
                        "title": a.title,
                        "published_at": a.published_at.isoformat(),
                        "description": a.description or "",
                    }
                    for a in news_context
                ],
                max_articles=5,
            )
        else:
            news_text = "No recent relevant news available."

        # Build prompt
        prompt = MARKET_ANALYSIS_TEMPLATE.format(
            question=market.question,
            current_price=float(market.yes_price),
            category=market.category,
            liquidity=float(market.liquidity),
            volume_24h=float(market.volume_24h),
            end_date=market.end_date.isoformat(),
            time_remaining=f"{market.time_to_resolution_hours:.1f} hours",
            news_context=news_text,
        )

        # Get prediction from LLM
        prediction_data = await llm_client.predict_market_outcome(
            question=market.question,
            current_odds=float(market.yes_price),
            news_context=news_text,
            end_date=market.end_date.isoformat(),
        )

        # Parse prediction
        predicted_prob = Decimal(str(prediction_data.get("probability", 0.5)))
        confidence = int(prediction_data.get("confidence", 5))
        reasoning = prediction_data.get("reasoning", "")
        key_factors = prediction_data.get("key_factors", [])

        # Calculate edge
        edge = predicted_prob - market.yes_price

        # Calculate expected value (simplified)
        if edge > 0:
            # Betting YES
            expected_value = edge * Decimal("100")  # Per $100 bet
        else:
            # Betting NO
            expected_value = abs(edge) * Decimal("100")

        # Create prediction object
        prediction = Prediction(
            market_id=market.id,
            predicted_probability=predicted_prob,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=key_factors,
            news_context=[a.id for a in news_context] if news_context else [],
            current_market_price=market.yes_price,
            edge=edge,
            expected_value=expected_value,
            model_name=self.model or "gpt-4-turbo-preview",
            temperature=self.temperature,
        )

        logger.info(
            "prediction_complete",
            market_id=market.id,
            predicted_prob=float(predicted_prob),
            edge=float(edge),
            confidence=confidence,
        )

        return prediction

    async def batch_predict(
        self,
        markets: List[Market],
        news_context_map: Optional[dict] = None,
    ) -> List[Prediction]:
        """Predict outcomes for multiple markets.

        Args:
            markets: List of markets to predict
            news_context_map: Optional dict mapping market_id to news articles

        Returns:
            List of Prediction objects
        """
        logger.info("batch_predicting", num_markets=len(markets))

        predictions = []

        for market in markets:
            news = None
            if news_context_map:
                news = news_context_map.get(market.id, [])

            try:
                prediction = await self.predict_outcome(market, news)
                predictions.append(prediction)
            except Exception as e:
                logger.error(
                    "prediction_error",
                    market_id=market.id,
                    error=str(e),
                )

        logger.info("batch_prediction_complete", total=len(predictions))

        return predictions

    async def compare_to_market(
        self,
        prediction: Prediction,
        min_edge: float = 0.05,
    ) -> dict:
        """Compare prediction to current market price.

        Args:
            prediction: Prediction object
            min_edge: Minimum required edge

        Returns:
            Dict with comparison analysis
        """
        edge = float(prediction.edge)
        has_edge = abs(edge) >= min_edge

        # Determine trade direction
        if edge > 0:
            direction = TradeDirection.LONG
            recommendation = "BUY YES" if has_edge else "PASS"
        else:
            direction = TradeDirection.SHORT
            recommendation = "BUY NO" if has_edge else "PASS"

        analysis = {
            "has_edge": has_edge,
            "edge": edge,
            "edge_pct": edge * 100,
            "direction": direction.value,
            "recommendation": recommendation,
            "predicted_prob": float(prediction.predicted_probability),
            "market_price": float(prediction.current_market_price),
            "confidence": prediction.confidence,
            "expected_value": float(prediction.expected_value),
        }

        logger.debug("market_comparison", **analysis)

        return analysis

    async def evaluate_confidence(
        self,
        prediction: Prediction,
        news_quality: Optional[float] = None,
    ) -> dict:
        """Evaluate the confidence level of a prediction.

        Args:
            prediction: Prediction object
            news_quality: Optional news quality score (0-1)

        Returns:
            Dict with confidence evaluation
        """
        base_confidence = prediction.confidence

        # Adjust confidence based on factors
        adjusted_confidence = base_confidence

        # Reduce confidence if news quality is low
        if news_quality is not None and news_quality < 0.5:
            adjusted_confidence -= 1

        # Reduce confidence if edge is small
        if abs(float(prediction.edge)) < 0.03:
            adjusted_confidence -= 1

        # Ensure confidence is in valid range
        adjusted_confidence = max(1, min(10, adjusted_confidence))

        evaluation = {
            "original_confidence": base_confidence,
            "adjusted_confidence": adjusted_confidence,
            "confidence_level": self._get_confidence_label(adjusted_confidence),
            "should_trade": adjusted_confidence >= 6,
        }

        logger.debug("confidence_evaluated", **evaluation)

        return evaluation

    def _get_confidence_label(self, confidence: int) -> str:
        """Get confidence level label.

        Args:
            confidence: Confidence score (1-10)

        Returns:
            Confidence label
        """
        if confidence >= 9:
            return "very_high"
        elif confidence >= 7:
            return "high"
        elif confidence >= 5:
            return "medium"
        elif confidence >= 3:
            return "low"
        else:
            return "very_low"

    async def update_prediction(
        self,
        original_prediction: Prediction,
        new_news: List[NewsArticle],
        market: Market,
    ) -> Prediction:
        """Update a prediction with new information.

        Args:
            original_prediction: Original prediction
            new_news: New news articles
            market: Updated market data

        Returns:
            Updated Prediction object
        """
        logger.info(
            "updating_prediction",
            market_id=market.id,
            new_news_count=len(new_news),
        )

        # Get new prediction with updated context
        updated_prediction = await self.predict_outcome(market, new_news)

        # Compare predictions
        prob_change = (
            updated_prediction.predicted_probability
            - original_prediction.predicted_probability
        )

        logger.info(
            "prediction_updated",
            market_id=market.id,
            prob_change=float(prob_change),
            new_confidence=updated_prediction.confidence,
        )

        return updated_prediction

    async def calibrate_prediction(
        self,
        prediction: Prediction,
        historical_accuracy: Optional[float] = None,
    ) -> Prediction:
        """Calibrate prediction based on historical performance.

        Args:
            prediction: Prediction to calibrate
            historical_accuracy: Historical accuracy rate (0-1)

        Returns:
            Calibrated prediction
        """
        # If we have historical accuracy data, adjust confidence
        if historical_accuracy is not None:
            # Reduce confidence if model has been overconfident
            if historical_accuracy < 0.7:
                prediction.confidence = max(1, prediction.confidence - 2)
            elif historical_accuracy > 0.85:
                prediction.confidence = min(10, prediction.confidence + 1)

        logger.debug(
            "prediction_calibrated",
            confidence=prediction.confidence,
            historical_accuracy=historical_accuracy,
        )

        return prediction
