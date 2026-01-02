    async def run_trading_cycle(self) -> Dict:
        """Execute one complete trading cycle using pipelines.

        This orchestrates the entire trading flow through specialized pipelines:
        1. NewsPipeline: Fetch recent news
        2. OpportunityFinder: Correlate news with markets
        3. PredictionEngine: Generate predictions
        4. TradeExecutor: Validate and execute trades
        5. PositionManager: Update and manage positions

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
            "opportunities_identified": 0,
            "predictions_made": 0,
            "trades_executed": 0,
            "positions_closed": 0,
            "errors": [],
        }

        try:
            # Step 1: Fetch recent news via NewsPipeline
            logger.info("step_1_fetching_news")
            news_articles = await self.news_pipeline.fetch_recent_news(
                lookback_hours=config.settings.scrape_interval_minutes // 60 + 1,
                max_results_per_source=50,
            )
            results["news_articles_found"] = len(news_articles)

            if not news_articles:
                logger.warning("no_news_articles_found")
                return self._finalize_results(results, cycle_start)

            # Step 2: Find opportunities via OpportunityFinder
            logger.info("step_2_finding_opportunities")
            opportunities = await self.opportunity_finder.find_from_news(
                news_articles=news_articles,
                min_relevance=0.5,
                top_k=10,
            )
            results["opportunities_identified"] = len(opportunities)

            if not opportunities:
                logger.info("no_opportunities_found")
                return self._finalize_results(results, cycle_start)

            # Step 3: Generate predictions via PredictionEngine
            logger.info("step_3_generating_predictions")
            predictions = await self.prediction_engine.generate_predictions(
                opportunities=opportunities,
            )

            # Filter by confidence and edge
            predictions = self.prediction_engine.filter_by_confidence(
                predictions,
                min_confidence=5,
            )
            predictions = self.prediction_engine.filter_by_edge(
                predictions,
                min_edge=0.05,
            )

            results["predictions_made"] = len(predictions)

            if not predictions:
                logger.info("no_predictions_met_criteria")
                return self._finalize_results(results, cycle_start)

            # Step 4: Execute approved trades via TradeExecutor
            logger.info("step_4_executing_trades")
            if not self.trade_executor.check_circuit_breaker():
                trades = await self.trade_executor.execute_approved_trades(predictions)
                results["trades_executed"] = len(trades)

                if trades:
                    logger.info("trades_executed_successfully", count=len(trades))
            else:
                logger.warning("circuit_breaker_active_skipping_trades")

            # Step 5: Update positions via PositionManager
            logger.info("step_5_updating_positions")
            async with self.market_intel:
                markets = await self.market_intel.get_active_markets(limit=100)

            markets_dict = {m.id: m for m in markets}
            closed_trades = await self.position_manager.update_and_exit(markets_dict)

            results["positions_closed"] = len(closed_trades)

            # Log portfolio status
            portfolio_summary = self.position_manager.get_portfolio_summary()
            logger.info(
                "portfolio_status",
                balance=portfolio_summary["balance"],
                open_positions=portfolio_summary["open_positions"],
                total_pnl=portfolio_summary["total_pnl"],
            )

        except Exception as e:
            logger.error("trading_cycle_error", error=str(e), cycle=self.cycle_count)
            results["errors"].append({"error": str(e), "type": "cycle_error"})

        # Finalize results
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        results["duration_seconds"] = cycle_duration
        results["completed_at"] = datetime.now().isoformat()

        self._log_cycle_summary(results)

        logger.info(
            "trading_cycle_completed",
            cycle=self.cycle_count,
            duration=cycle_duration,
        )

        return results

    def _finalize_results(self, results: Dict, cycle_start: datetime) -> Dict:
        """Helper to finalize results with timing info.

        Args:
            results: Results dict to finalize
            cycle_start: Cycle start time

        Returns:
            Finalized results dict
        """
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        results["duration_seconds"] = cycle_duration
        results["completed_at"] = datetime.now().isoformat()
        return results
