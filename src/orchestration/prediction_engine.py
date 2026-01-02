"""Prediction Engine - Generates predictions for market opportunities."""

from typing import Dict, List, Optional

from ..agents.forecaster import ForecastingAgent
from ..models.market import MarketOpportunity
from ..models.news import NewsArticle
from ..models.trade import Prediction
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PredictionEngine:
    """Generates predictions for trading opportunities."""

    def __init__(self, forecaster: Optional[ForecastingAgent] = None):
        """Initialize Prediction Engine.

        Args:
            forecaster: Forecasting agent (creates default if None)
        """
        self.forecaster = forecaster or ForecastingAgent()
        logger.info("prediction_engine_initialized")

    async def generate_predictions(
        self,
        opportunities: List[MarketOpportunity],
        news_context: Optional[Dict[str, List[NewsArticle]]] = None,
    ) -> List[Prediction]:
        """Generate predictions for a list of opportunities.

        Args:
            opportunities: List of market opportunities to predict
            news_context: Optional dict mapping market_id to relevant news articles

        Returns:
            List of Prediction objects
        """
        logger.info("generating_predictions", num_opportunities=len(opportunities))

        if not opportunities:
            logger.warning("no_opportunities_to_predict")
            return []

        predictions = []

        for opportunity in opportunities:
            try:
                # Get news context for this market
                market_news = None
                if news_context and opportunity.market.id in news_context:
                    market_news = news_context[opportunity.market.id]

                # Generate prediction
                prediction = await self.forecaster.predict_outcome(
                    market=opportunity.market,
                    news_context=market_news,
                )

                # Add opportunity metadata to prediction
                prediction.metadata = prediction.metadata or {}
                prediction.metadata["opportunity_score"] = opportunity.relevance_score
                prediction.metadata["opportunity_rank"] = opportunities.index(opportunity) + 1

                predictions.append(prediction)

                logger.debug(
                    "prediction_generated",
                    market_id=opportunity.market.id,
                    probability=float(prediction.predicted_probability),
                    confidence=prediction.confidence,
                )

            except Exception as e:
                logger.error(
                    "prediction_error",
                    market_id=opportunity.market.id,
                    error=str(e),
                )
                continue

        logger.info(
            "predictions_complete",
            total_opportunities=len(opportunities),
            successful_predictions=len(predictions),
        )

        return predictions

    async def batch_predict(
        self,
        opportunities: List[MarketOpportunity],
    ) -> List[Prediction]:
        """Generate predictions for multiple opportunities in batch.

        This is optimized for multiple predictions and uses
        the forecaster's batch prediction capabilities.

        Args:
            opportunities: List of market opportunities

        Returns:
            List of Prediction objects
        """
        logger.info("batch_predicting", num_opportunities=len(opportunities))

        if not opportunities:
            return []

        try:
            # Extract markets from opportunities
            markets = [opp.market for opp in opportunities]

            # Use batch prediction
            predictions = await self.forecaster.batch_predict(markets)

            # Enhance with opportunity metadata
            for i, prediction in enumerate(predictions):
                if i < len(opportunities):
                    prediction.metadata = prediction.metadata or {}
                    prediction.metadata["opportunity_score"] = opportunities[i].relevance_score
                    prediction.metadata["opportunity_rank"] = i + 1

            logger.info("batch_prediction_complete", count=len(predictions))
            return predictions

        except Exception as e:
            logger.error("batch_prediction_error", error=str(e))
            # Fall back to sequential prediction
            return await self.generate_predictions(opportunities)

    async def predict_with_comparison(
        self,
        opportunity: MarketOpportunity,
        min_edge: float = 0.05,
    ) -> Optional[Prediction]:
        """Generate prediction and compare to market price.

        Args:
            opportunity: Market opportunity to predict
            min_edge: Minimum edge required

        Returns:
            Prediction object if has sufficient edge, None otherwise
        """
        logger.info(
            "predicting_with_comparison",
            market_id=opportunity.market.id,
            min_edge=min_edge,
        )

        try:
            # Generate prediction
            prediction = await self.forecaster.predict_outcome(
                market=opportunity.market,
                news_context=None,  # Could be enhanced
            )

            # Compare to market
            comparison = await self.forecaster.compare_to_market(
                prediction=prediction,
                min_edge=min_edge,
            )

            if comparison["has_edge"]:
                logger.info(
                    "prediction_has_edge",
                    market_id=opportunity.market.id,
                    edge=comparison["edge"],
                )
                return prediction
            else:
                logger.debug(
                    "prediction_no_edge",
                    market_id=opportunity.market.id,
                    edge=comparison["edge"],
                )
                return None

        except Exception as e:
            logger.error(
                "prediction_comparison_error",
                market_id=opportunity.market.id,
                error=str(e),
            )
            return None

    def filter_by_confidence(
        self,
        predictions: List[Prediction],
        min_confidence: int = 5,
    ) -> List[Prediction]:
        """Filter predictions by minimum confidence.

        Args:
            predictions: List of predictions to filter
            min_confidence: Minimum confidence score (1-10)

        Returns:
            Filtered list of predictions
        """
        filtered = [p for p in predictions if p.confidence >= min_confidence]

        logger.info(
            "predictions_filtered_by_confidence",
            total=len(predictions),
            filtered=len(filtered),
            min_confidence=min_confidence,
        )

        return filtered

    def filter_by_edge(
        self,
        predictions: List[Prediction],
        min_edge: float = 0.05,
    ) -> List[Prediction]:
        """Filter predictions by minimum edge.

        Args:
            predictions: List of predictions to filter
            min_edge: Minimum edge (difference from market price)

        Returns:
            Filtered list of predictions
        """
        filtered = [p for p in predictions if abs(float(p.edge)) >= min_edge]

        logger.info(
            "predictions_filtered_by_edge",
            total=len(predictions),
            filtered=len(filtered),
            min_edge=min_edge,
        )

        return filtered
