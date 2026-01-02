"""Orchestration pipelines for autonomous trading."""

from .news_pipeline import NewsPipeline
from .opportunity_finder import OpportunityFinder
from .prediction_engine import PredictionEngine
from .trade_executor import TradeExecutor
from .position_manager import PositionManager

__all__ = [
    "NewsPipeline",
    "OpportunityFinder",
    "PredictionEngine",
    "TradeExecutor",
    "PositionManager",
]
