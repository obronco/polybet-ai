"""Configuration management utilities."""

from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Polymarket Configuration
    polygon_wallet_private_key: SecretStr = Field(..., alias="POLYGON_WALLET_PRIVATE_KEY")
    polygon_wallet_address: str = Field(..., alias="POLYGON_WALLET_ADDRESS")

    polymarket_api_key: SecretStr = Field(default=SecretStr(""), alias="POLYMARKET_API_KEY")
    polymarket_api_secret: SecretStr = Field(default=SecretStr(""), alias="POLYMARKET_API_SECRET")
    polymarket_passphrase: SecretStr = Field(default=SecretStr(""), alias="POLYMARKET_PASSPHRASE")

    # AI/LLM Configuration
    openai_api_key: SecretStr = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.7, alias="OPENAI_TEMPERATURE")

    # News Sources
    newsapi_key: SecretStr = Field(..., alias="NEWSAPI_KEY")
    tavily_api_key: SecretStr = Field(default=SecretStr(""), alias="TAVILY_API_KEY")

    # Optional: Twitter/X API
    twitter_api_key: SecretStr = Field(default=SecretStr(""), alias="TWITTER_API_KEY")
    twitter_api_secret: SecretStr = Field(default=SecretStr(""), alias="TWITTER_API_SECRET")
    twitter_bearer_token: SecretStr = Field(default=SecretStr(""), alias="TWITTER_BEARER_TOKEN")

    # Database Configuration
    chroma_persist_directory: str = Field(
        default="./data/chroma", alias="CHROMA_PERSIST_DIRECTORY"
    )
    postgres_url: SecretStr = Field(
        default=SecretStr(""),
        alias="POSTGRES_URL",
    )

    # Trading Configuration
    paper_trading_mode: bool = Field(default=True, alias="PAPER_TRADING_MODE")
    max_bet_size_pct: float = Field(default=0.03, alias="MAX_BET_SIZE_PCT")
    max_daily_loss_pct: float = Field(default=0.10, alias="MAX_DAILY_LOSS_PCT")
    min_edge_required: float = Field(default=0.05, alias="MIN_EDGE_REQUIRED")
    min_confidence_score: int = Field(default=6, alias="MIN_CONFIDENCE_SCORE")

    # Risk Management
    kelly_fraction: float = Field(default=0.25, alias="KELLY_FRACTION")
    max_concurrent_positions: int = Field(default=10, alias="MAX_CONCURRENT_POSITIONS")
    circuit_breaker_enabled: bool = Field(default=True, alias="CIRCUIT_BREAKER_ENABLED")

    # Monitoring & Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    sentry_dsn: SecretStr = Field(default=SecretStr(""), alias="SENTRY_DSN")
    telegram_bot_token: SecretStr = Field(default=SecretStr(""), alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    # System Configuration
    scrape_interval_minutes: int = Field(default=15, alias="SCRAPE_INTERVAL_MINUTES")
    trading_cycle_interval_minutes: int = Field(
        default=30, alias="TRADING_CYCLE_INTERVAL_MINUTES"
    )
    api_rate_limit_calls_per_minute: int = Field(
        default=60, alias="API_RATE_LIMIT_CALLS_PER_MINUTE"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        populate_by_name = True

    def __repr__(self) -> str:
        """Custom repr that never exposes secrets."""
        return (
            f"Settings("
            f"paper_trading={self.paper_trading_mode}, "
            f"log_level={self.log_level}, "
            f"model={self.openai_model}"
            f")"
        )


class ConfigManager:
    """Manages application configuration from files and environment."""

    def __init__(self, config_dir: str = "config"):
        """Initialize configuration manager.

        Args:
            config_dir: Directory containing YAML configuration files
        """
        self.config_dir = Path(config_dir)
        self.settings = Settings()
        self._markets_config: Dict[str, Any] = {}
        self._risk_config: Dict[str, Any] = {}
        self._load_configs()

    def _load_configs(self) -> None:
        """Load YAML configuration files."""
        markets_config_path = self.config_dir / "markets_config.yaml"
        risk_config_path = self.config_dir / "risk_config.yaml"

        if markets_config_path.exists():
            with open(markets_config_path, "r") as f:
                self._markets_config = yaml.safe_load(f)

        if risk_config_path.exists():
            with open(risk_config_path, "r") as f:
                self._risk_config = yaml.safe_load(f)

    @property
    def markets_config(self) -> Dict[str, Any]:
        """Get markets configuration."""
        return self._markets_config

    @property
    def risk_config(self) -> Dict[str, Any]:
        """Get risk management configuration."""
        return self._risk_config

    def get_market_filters(self) -> Dict[str, Any]:
        """Get market filtering criteria."""
        return self._markets_config.get("market_filters", {})

    def get_focus_keywords(self, category: str = None) -> Dict[str, list]:
        """Get focus keywords, optionally filtered by category."""
        keywords = self._markets_config.get("focus_keywords", {})
        if category:
            return {category: keywords.get(category, [])}
        return keywords

    def get_risk_limits(self) -> Dict[str, Any]:
        """Get risk limit configuration."""
        return self._risk_config.get("risk_limits", {})

    def get_position_sizing_config(self) -> Dict[str, Any]:
        """Get position sizing configuration."""
        return self._risk_config.get("position_sizing", {})

    def get_circuit_breaker_config(self) -> Dict[str, Any]:
        """Get circuit breaker configuration."""
        return self._risk_config.get("circuit_breakers", {})

    def is_paper_trading(self) -> bool:
        """Check if paper trading mode is enabled."""
        return self.settings.paper_trading_mode


# Global configuration instance
config = ConfigManager()
