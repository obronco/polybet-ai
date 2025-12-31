"""Market data models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MarketStatus(str, Enum):
    """Market status enumeration."""

    ACTIVE = "active"
    CLOSED = "closed"
    RESOLVED = "resolved"
    SUSPENDED = "suspended"


class OrderSide(str, Enum):
    """Order side enumeration."""

    YES = "YES"
    NO = "NO"
    BUY = "BUY"
    SELL = "SELL"


class Market(BaseModel):
    """Polymarket prediction market model."""

    id: str = Field(..., description="Unique market identifier")
    question: str = Field(..., description="Market question")
    description: Optional[str] = Field(None, description="Market description")

    # Categorization
    category: str = Field(..., description="Market category")
    tags: List[str] = Field(default_factory=list, description="Market tags")

    # Status and timing
    status: MarketStatus = Field(..., description="Current market status")
    start_date: datetime = Field(..., description="Market start date")
    end_date: datetime = Field(..., description="Market end date")
    resolution_date: Optional[datetime] = Field(None, description="Resolution date")

    # Market metrics
    liquidity: Decimal = Field(..., description="Total liquidity in USD")
    volume: Decimal = Field(..., description="Total volume traded in USD")
    volume_24h: Decimal = Field(
        default=Decimal(0), description="24-hour trading volume"
    )
    num_traders: int = Field(default=0, description="Number of unique traders")

    # Pricing
    yes_price: Decimal = Field(..., description="Current YES price (0-1)")
    no_price: Decimal = Field(..., description="Current NO price (0-1)")
    spread: Decimal = Field(..., description="Bid-ask spread")

    # Metadata
    event_id: Optional[str] = Field(None, description="Associated event ID")
    market_maker: Optional[str] = Field(None, description="Market maker address")
    outcome_prices: Dict[str, Decimal] = Field(
        default_factory=dict, description="Outcome prices for multi-outcome markets"
    )

    # Computed fields
    @property
    def time_to_resolution_hours(self) -> float:
        """Calculate hours until market resolution."""
        if not self.end_date:
            return 0
        delta = self.end_date - datetime.now()
        return max(0, delta.total_seconds() / 3600)

    @property
    def is_active(self) -> bool:
        """Check if market is currently active."""
        return self.status == MarketStatus.ACTIVE

    @property
    def implied_probability_yes(self) -> float:
        """Get implied probability for YES outcome."""
        return float(self.yes_price)

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class Event(BaseModel):
    """Polymarket event model (collection of related markets)."""

    id: str = Field(..., description="Unique event identifier")
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    category: str = Field(..., description="Event category")
    markets: List[Market] = Field(default_factory=list, description="Related markets")
    start_date: datetime = Field(..., description="Event start date")
    end_date: datetime = Field(..., description="Event end date")
    tags: List[str] = Field(default_factory=list, description="Event tags")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class OrderBook(BaseModel):
    """Order book for a market."""

    market_id: str = Field(..., description="Market identifier")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Snapshot timestamp"
    )

    # Bids and asks
    bids: List[Dict[str, Decimal]] = Field(
        default_factory=list, description="Buy orders (price, size)"
    )
    asks: List[Dict[str, Decimal]] = Field(
        default_factory=list, description="Sell orders (price, size)"
    )

    @property
    def best_bid(self) -> Optional[Decimal]:
        """Get best bid price."""
        return max((b["price"] for b in self.bids), default=None)

    @property
    def best_ask(self) -> Optional[Decimal]:
        """Get best ask price."""
        return min((a["price"] for a in self.asks), default=None)

    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class MarketOpportunity(BaseModel):
    """Identified trading opportunity for a market."""

    market: Market = Field(..., description="The market")
    relevance_score: float = Field(
        ..., description="How relevant the opportunity is (0-1)", ge=0, le=1
    )
    edge: Optional[Decimal] = Field(
        None, description="Expected edge over market (if calculated)"
    )
    news_context: List[str] = Field(
        default_factory=list, description="Related news article IDs"
    )
    identified_at: datetime = Field(
        default_factory=datetime.now, description="When opportunity was identified"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}
