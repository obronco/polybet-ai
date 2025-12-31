"""Orchestrator - Coordinates all agents for autonomous trading."""

import asyncio
from datetime import datetime
from typing import Dict, Optional

from .agents.analyst import AnalystAgent
from .agents.forecaster import ForecastingAgent
from .agents.market_intel import MarketIntelligenceAgent
from .agents.news_scraper import NewsScraperAgent
from .agents.risk_manager import RiskManagerAgent
from .agents.trader import TradingAgent
from .utils.config import config
from .utils.logger import get_logger

logger = get_logger(__name__)


class AutonomousOrchestrator:
    """Orchestrates all agents for autonomous trading."""

    def __init__(self, paper_trading: bool = True):
        """Initialize orchestrator with all agents.

        Args:
            paper_trading: Whether to use paper trading mode
        """
        logger.info("initializing_orchestrator", paper_trading=paper_trading)

        # Initialize all agents
        self.news_scraper = NewsScraperAgent()
        self.market_intel = MarketIntelligenceAgent()
        self.analyst = AnalystAgent()
        self.forecaster = ForecastingAgent()
        self.risk_manager = RiskManagerAgent()
        self.trader = TradingAgent(paper_trading=paper_trading)

        self.running = False
        self.cycle_count = 0

        logger.info("orchestrator_initialized")

    async def run_trading_cycle(self) -> Dict:
        """Execute one complete trading cycle.

        Returns:
            Dict with cycle results
        """
        self.cycle_count += 1
        cycle_start = datetime.now()

        logger.info("trading_cycle_started", cycle=self.cycle_count)

        results = {
            "cycle": self.cycle_count,
            "started_at": cycle_start.isoformat(),
            "news_articles_found": 0,
            "markets_analyzed": 0,
            "opportunities_identified": 0,
            "predictions_made": 0,
            "trades_executed": 0,
            "trades_rejected": 0,
            "errors": [],
        }

        try:
            # Step 1: Scrape latest news
            logger.info("step_1_scraping_news")
            news_articles = await self.news_scraper.scrape_news(
                lookback_hours=config.settings.scrape_interval_minutes // 60 + 1,
                max_results_per_source=50,
            )
            results["news_articles_found"] = len(news_articles)

            if not news_articles:
                logger.warning("no_news_articles_found")
                return results

            # Step 2: Get active markets
            logger.info("step_2_fetching_markets")
            async with self.market_intel as intel:
                markets = await intel.get_active_markets(limit=100)
            results["markets_analyzed"] = len(markets)

            if not markets:
                logger.warning("no_active_markets_found")
                return results

            # Step 3: Find opportunities (correlate news with markets)
            logger.info("step_3_finding_opportunities")
            opportunities = await self.analyst.find_opportunities_from_news(
                news_articles=news_articles,
                min_relevance=0.5,
            )
            results["opportunities_identified"] = len(opportunities)

            if not opportunities:
                logger.info("no_opportunities_found")
                return results

            # Step 4: Generate predictions for top opportunities
            logger.info("step_4_generating_predictions")
            top_opportunities = opportunities[:10]  # Top 10 most relevant

            predictions_made = []
            trades_executed = []
            trades_rejected = []

            for opportunity in top_opportunities:
                try:
                    # Get relevant news for this market
                    relevant_news = [
                        article
                        for article in news_articles
                        if article.id in opportunity.news_context
                    ]

                    # Generate prediction
                    prediction = await self.forecaster.predict_outcome(
                        market=opportunity.market,
                        news_context=relevant_news,
                    )
                    predictions_made.append(prediction)

                    # Step 5: Risk assessment
                    logger.info(
                        "step_5_risk_assessment",
                        market_id=opportunity.market.id,
                    )
                    risk_assessment = await self.risk_manager.validate_trade(
                        prediction=prediction,
                        market=opportunity.market,
                        portfolio=self.trader.portfolio,
                    )

                    # Step 6: Execute trade if approved
                    if risk_assessment.approved:
                        logger.info(
                            "step_6_executing_trade",
                            market_id=opportunity.market.id,
                        )
                        trade = await self.trader.execute_trade(
                            prediction=prediction,
                            risk_assessment=risk_assessment,
                            market=opportunity.market,
                        )

                        if trade:
                            trades_executed.append(trade)
                            logger.info(
                                "trade_executed_successfully",
                                trade_id=trade.id,
                                market=opportunity.market.question[:50],
                            )
                        else:
                            trades_rejected.append(
                                {"market_id": opportunity.market.id, "reason": "execution_failed"}
                            )
                    else:
                        trades_rejected.append(
                            {
                                "market_id": opportunity.market.id,
                                "reason": "risk_assessment_failed",
                                "checks_failed": risk_assessment.checks_failed,
                            }
                        )
                        logger.info(
                            "trade_rejected",
                            market_id=opportunity.market.id,
                            reason=risk_assessment.checks_failed,
                        )

                except Exception as e:
                    logger.error(
                        "opportunity_processing_error",
                        market_id=opportunity.market.id,
                        error=str(e),
                    )
                    results["errors"].append(
                        {
                            "market_id": opportunity.market.id,
                            "error": str(e),
                        }
                    )

            results["predictions_made"] = len(predictions_made)
            results["trades_executed"] = len(trades_executed)
            results["trades_rejected"] = len(trades_rejected)

            # Step 7: Update existing positions
            logger.info("step_7_updating_positions")
            market_dict = {m.id: m for m in markets}
            await self.trader.update_open_positions(market_dict)

            # Apply exit rules
            positions_closed = await self.trader.apply_exit_rules(market_dict)
            results["positions_closed"] = positions_closed

            # Check circuit breaker
            circuit_breaker_triggered = self.risk_manager.check_circuit_breaker(
                self.trader.portfolio
            )
            results["circuit_breaker_triggered"] = circuit_breaker_triggered

        except Exception as e:
            logger.error("trading_cycle_error", error=str(e))
            results["errors"].append({"error": str(e), "stage": "overall"})

        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        results["duration_seconds"] = cycle_duration
        results["completed_at"] = datetime.now().isoformat()

        logger.info(
            "trading_cycle_completed",
            cycle=self.cycle_count,
            duration=cycle_duration,
            trades_executed=results["trades_executed"],
        )

        return results

    async def run_continuous(
        self,
        interval_minutes: Optional[int] = None,
    ) -> None:
        """Run continuous autonomous trading.

        Args:
            interval_minutes: Cycle interval (defaults to config)
        """
        interval = interval_minutes or config.settings.trading_cycle_interval_minutes
        self.running = True

        logger.info(
            "starting_continuous_trading",
            interval_minutes=interval,
            paper_trading=self.trader.paper_trading,
        )

        while self.running:
            try:
                # Run trading cycle
                results = await self.run_trading_cycle()

                # Log summary
                self._log_cycle_summary(results)

                # Check if we should stop (circuit breaker)
                if results.get("circuit_breaker_triggered"):
                    logger.warning("circuit_breaker_triggered_stopping")
                    self.running = False
                    break

                # Wait for next cycle
                logger.info(
                    "waiting_for_next_cycle",
                    interval_minutes=interval,
                )
                await asyncio.sleep(interval * 60)

            except KeyboardInterrupt:
                logger.info("keyboard_interrupt_received")
                self.running = False
                break

            except Exception as e:
                logger.error("continuous_trading_error", error=str(e))
                # Wait before retrying
                await asyncio.sleep(60)

        logger.info("continuous_trading_stopped")

    def stop(self) -> None:
        """Stop continuous trading."""
        logger.info("stopping_orchestrator")
        self.running = False

    def _log_cycle_summary(self, results: Dict) -> None:
        """Log summary of trading cycle.

        Args:
            results: Cycle results dict
        """
        portfolio_summary = self.trader.get_portfolio_summary()

        logger.info(
            "cycle_summary",
            cycle=results["cycle"],
            news_found=results["news_articles_found"],
            opportunities=results["opportunities_identified"],
            predictions=results["predictions_made"],
            trades_executed=results["trades_executed"],
            trades_rejected=results["trades_rejected"],
            **portfolio_summary,
        )

    async def get_status(self) -> Dict:
        """Get current status of the orchestrator.

        Returns:
            Dict with status information
        """
        portfolio_summary = self.trader.get_portfolio_summary()

        status = {
            "running": self.running,
            "cycle_count": self.cycle_count,
            "paper_trading": self.trader.paper_trading,
            "circuit_breaker_active": self.risk_manager.circuit_breaker_active,
            "portfolio": portfolio_summary,
        }

        return status

    async def manual_trade(
        self,
        market_id: str,
        force: bool = False,
    ) -> Optional[Dict]:
        """Manually analyze and potentially trade a specific market.

        Args:
            market_id: Market identifier
            force: Force trade even if risk checks fail

        Returns:
            Dict with trade result
        """
        logger.info("manual_trade_requested", market_id=market_id, force=force)

        # Get market details
        async with self.market_intel as intel:
            market = await intel.get_market_details(market_id)

        if not market:
            logger.error("market_not_found", market_id=market_id)
            return {"error": "Market not found"}

        # Find relevant news
        # Generate prediction
        prediction = await self.forecaster.predict_outcome(market)

        # Risk assessment
        risk_assessment = await self.risk_manager.validate_trade(
            prediction=prediction,
            market=market,
            portfolio=self.trader.portfolio,
        )

        # Execute if approved or forced
        if risk_assessment.approved or force:
            trade = await self.trader.execute_trade(
                prediction=prediction,
                risk_assessment=risk_assessment,
                market=market,
            )

            return {
                "success": True,
                "trade_id": trade.id if trade else None,
                "prediction": {
                    "probability": float(prediction.predicted_probability),
                    "confidence": prediction.confidence,
                    "edge": float(prediction.edge),
                },
                "risk_assessment": {
                    "approved": risk_assessment.approved,
                    "recommended_size": float(risk_assessment.recommended_size),
                },
            }
        else:
            return {
                "success": False,
                "reason": "Risk assessment failed",
                "checks_failed": risk_assessment.checks_failed,
                "prediction": {
                    "probability": float(prediction.predicted_probability),
                    "confidence": prediction.confidence,
                    "edge": float(prediction.edge),
                },
            }
