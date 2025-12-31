"""Trade execution and prediction models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .market import Market, OrderSide


class TradeStatus(str, Enum):
    """Trade execution status."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TradeDirection(str, Enum):
    """Trade direction."""

    LONG = "long"  # Betting YES/buying probability
    SHORT = "short"  # Betting NO/selling probability


class Prediction(BaseModel):
    """AI-generated prediction for a market outcome."""

    market_id: str = Field(..., description="Market identifier")
    predicted_probability: Decimal = Field(
        ..., description="Predicted probability for YES outcome", ge=0, le=1
    )
    confidence: int = Field(
        ..., description="Confidence level (1-10)", ge=1, le=10
    )

    # Analysis
    reasoning: str = Field(..., description="Explanation of the prediction")
    key_factors: List[str] = Field(
        default_factory=list, description="Key factors influencing prediction"
    )
    news_context: List[str] = Field(
        default_factory=list, description="News article IDs used for prediction"
    )

    # Edge calculation
    current_market_price: Decimal = Field(
        ..., description="Current market price for YES"
    )
    edge: Decimal = Field(
        ..., description="Expected edge (predicted_prob - market_price)"
    )
    expected_value: Decimal = Field(
        ..., description="Expected value of the bet"
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.now, description="Prediction timestamp"
    )
    model_name: str = Field(..., description="LLM model used")
    temperature: float = Field(default=0.7, description="Model temperature")

    @property
    def has_edge(self, min_edge: float = 0.05) -> bool:
        """Check if prediction has sufficient edge."""
        return float(self.edge) >= min_edge

    @property
    def direction(self) -> TradeDirection:
        """Determine trade direction based on edge."""
        if self.predicted_probability > self.current_market_price:
            return TradeDirection.LONG
        return TradeDirection.SHORT

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class RiskAssessment(BaseModel):
    """Risk assessment for a proposed trade."""

    approved: bool = Field(..., description="Whether trade is approved")
    risk_score: float = Field(..., description="Overall risk score (0-1)", ge=0, le=1)

    # Risk factors
    checks_passed: List[str] = Field(
        default_factory=list, description="Risk checks that passed"
    )
    checks_failed: List[str] = Field(
        default_factory=list, description="Risk checks that failed"
    )
    warnings: List[str] = Field(default_factory=list, description="Risk warnings")

    # Position sizing
    recommended_size: Decimal = Field(..., description="Recommended bet size in USD")
    max_size: Decimal = Field(..., description="Maximum allowable bet size")
    kelly_size: Optional[Decimal] = Field(None, description="Kelly criterion size")

    # Limits
    current_exposure: Decimal = Field(
        default=Decimal(0), description="Current exposure in category"
    )
    daily_loss: Decimal = Field(default=Decimal(0), description="Daily loss so far")
    open_positions: int = Field(default=0, description="Number of open positions")

    created_at: datetime = Field(
        default_factory=datetime.now, description="Assessment timestamp"
    )

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class ProposedTrade(BaseModel):
    """A proposed trade before execution."""

    market: Market = Field(..., description="Target market")
    prediction: Prediction = Field(..., description="AI prediction")
    risk_assessment: Optional[RiskAssessment] = Field(
        None, description="Risk assessment"
    )

    # Trade parameters
    side: OrderSide = Field(..., description="Order side (YES/NO)")
    direction: TradeDirection = Field(..., description="Trade direction")
    size: Decimal = Field(..., description="Position size in USD")
    max_slippage: Decimal = Field(
        default=Decimal("0.02"), description="Maximum acceptable slippage"
    )

    created_at: datetime = Field(
        default_factory=datetime.now, description="Proposal timestamp"
    )

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class Order(BaseModel):
    """Order model for Polymarket DEX."""

    id: Optional[str] = Field(None, description="Order ID (assigned after creation)")
    market_id: str = Field(..., description="Market identifier")

    # Order details
    side: OrderSide = Field(..., description="Order side")
    price: Decimal = Field(..., description="Limit price", ge=0, le=1)
    size: Decimal = Field(..., description="Order size in contracts/USD")

    # Execution
    status: TradeStatus = Field(
        default=TradeStatus.PENDING, description="Order status"
    )
    filled_size: Decimal = Field(default=Decimal(0), description="Filled amount")
    average_fill_price: Optional[Decimal] = Field(
        None, description="Average fill price"
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.now, description="Order creation time"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update time"
    )
    signature: Optional[str] = Field(None, description="Order signature")

    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.status == TradeStatus.FILLED

    @property
    def fill_percentage(self) -> float:
        """Calculate fill percentage."""
        if self.size == 0:
            return 0
        return float(self.filled_size / self.size * 100)

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class Trade(BaseModel):
    """Executed trade record."""

    id: str = Field(..., description="Trade identifier")
    order_id: str = Field(..., description="Associated order ID")
    market_id: str = Field(..., description="Market identifier")

    # Trade details
    side: OrderSide = Field(..., description="Trade side")
    direction: TradeDirection = Field(..., description="Trade direction")
    entry_price: Decimal = Field(..., description="Entry price")
    size: Decimal = Field(..., description="Position size")
    cost: Decimal = Field(..., description="Total cost including fees")

    # Performance tracking
    current_price: Optional[Decimal] = Field(None, description="Current market price")
    pnl: Optional[Decimal] = Field(None, description="Profit/Loss")
    pnl_percentage: Optional[Decimal] = Field(None, description="P&L percentage")

    # Exit
    exit_price: Optional[Decimal] = Field(None, description="Exit price if closed")
    exit_at: Optional[datetime] = Field(None, description="Exit timestamp")
    closed: bool = Field(default=False, description="Whether position is closed")

    # Metadata
    prediction_id: Optional[str] = Field(
        None, description="Associated prediction ID"
    )
    news_context: List[str] = Field(
        default_factory=list, description="News articles that influenced trade"
    )
    notes: str = Field(default="", description="Trade notes")

    # Timestamps
    executed_at: datetime = Field(
        default_factory=datetime.now, description="Execution timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )

    # Paper trading
    is_paper_trade: bool = Field(
        default=False, description="Whether this is a paper trade"
    )

    @property
    def is_profitable(self) -> bool:
        """Check if trade is profitable."""
        return self.pnl is not None and self.pnl > 0

    @property
    def hold_time_hours(self) -> float:
        """Calculate how long position has been held."""
        end_time = self.exit_at if self.closed else datetime.now()
        delta = end_time - self.executed_at
        return delta.total_seconds() / 3600

    def update_pnl(self, current_price: Decimal) -> None:
        """Update P&L based on current market price."""
        self.current_price = current_price

        if self.direction == TradeDirection.LONG:
            self.pnl = (current_price - self.entry_price) * self.size
        else:
            self.pnl = (self.entry_price - current_price) * self.size

        if self.cost > 0:
            self.pnl_percentage = (self.pnl / self.cost) * 100

        self.updated_at = datetime.now()

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class Portfolio(BaseModel):
    """Trading portfolio tracking."""

    balance: Decimal = Field(..., description="Current balance")
    initial_balance: Decimal = Field(..., description="Starting balance")

    # Positions
    open_trades: List[Trade] = Field(
        default_factory=list, description="Open positions"
    )
    closed_trades: List[Trade] = Field(
        default_factory=list, description="Closed positions"
    )

    # Performance
    total_pnl: Decimal = Field(default=Decimal(0), description="Total P&L")
    daily_pnl: Decimal = Field(default=Decimal(0), description="Today's P&L")
    weekly_pnl: Decimal = Field(default=Decimal(0), description="This week's P&L")

    # Statistics
    total_trades: int = Field(default=0, description="Total number of trades")
    winning_trades: int = Field(default=0, description="Number of winning trades")
    losing_trades: int = Field(default=0, description="Number of losing trades")

    # Updated timestamp
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update"
    )

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return 0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def roi(self) -> float:
        """Calculate return on investment percentage."""
        if self.initial_balance == 0:
            return 0
        return float((self.total_pnl / self.initial_balance) * 100)

    @property
    def available_balance(self) -> Decimal:
        """Calculate available balance for trading."""
        open_exposure = sum(trade.cost for trade in self.open_trades)
        return self.balance - open_exposure

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}
