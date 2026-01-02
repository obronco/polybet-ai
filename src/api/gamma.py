"""Gamma API client for Polymarket market and event data."""

import aiohttp
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from ..models.market import Event, Market, MarketStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GammaClient:
    """Client for Polymarket Gamma API."""

    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self):
        """Initialize Gamma API client."""
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request to Gamma API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            Exception: If request fails
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                logger.debug(
                    "gamma_api_request", endpoint=endpoint, status=response.status
                )
                return data

        except aiohttp.ClientError as e:
            logger.error("gamma_api_error", endpoint=endpoint, error=str(e))
            raise

    async def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
    ) -> List[Market]:
        """Retrieve markets from Gamma API.

        Args:
            limit: Maximum number of markets to return
            offset: Offset for pagination
            active: Include active markets
            closed: Include closed markets

        Returns:
            List of Market objects
        """
        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
        }

        data = await self._get("/markets", params=params)

        markets = []
        for item in data:
            try:
                market = self._parse_market(item)
                markets.append(market)
            except Exception as e:
                logger.warning(
                    "market_parse_error", market_id=item.get("id"), error=str(e)
                )

        logger.info("markets_fetched", count=len(markets))
        return markets

    async def get_market(self, market_id: str) -> Optional[Market]:
        """Get a specific market by ID.

        Args:
            market_id: Market identifier

        Returns:
            Market object or None if not found
        """
        try:
            data = await self._get(f"/markets/{market_id}")
            return self._parse_market(data)
        except Exception as e:
            logger.error("get_market_error", market_id=market_id, error=str(e))
            return None

    async def get_events(self, limit: int = 100, offset: int = 0) -> List[Event]:
        """Retrieve events from Gamma API.

        Args:
            limit: Maximum number of events
            offset: Offset for pagination

        Returns:
            List of Event objects
        """
        params = {"limit": limit, "offset": offset}
        data = await self._get("/events", params=params)

        events = []
        for item in data:
            try:
                event = self._parse_event(item)
                events.append(event)
            except Exception as e:
                logger.warning("event_parse_error", error=str(e))

        logger.info("events_fetched", count=len(events))
        return events

    async def get_event(self, event_id: str) -> Optional[Event]:
        """Get a specific event by ID.

        Args:
            event_id: Event identifier

        Returns:
            Event object or None if not found
        """
        try:
            data = await self._get(f"/events/{event_id}")
            return self._parse_event(data)
        except Exception as e:
            logger.error("get_event_error", event_id=event_id, error=str(e))
            return None

    async def search_markets(self, query: str, limit: int = 50) -> List[Market]:
        """Search markets by query string.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching markets
        """
        params = {"query": query, "limit": limit}
        data = await self._get("/markets/search", params=params)

        markets = []
        for item in data:
            try:
                market = self._parse_market(item)
                markets.append(market)
            except Exception as e:
                logger.warning("market_parse_error", error=str(e))

        return markets

    def _parse_market(self, data: Dict) -> Market:
        """Parse market data from API response.

        Args:
            data: Raw market data from API

        Returns:
            Market object
        """
        # Parse status
        status_str = data.get("active", True)
        if isinstance(status_str, bool):
            status = MarketStatus.ACTIVE if status_str else MarketStatus.CLOSED
        else:
            status = MarketStatus(status_str.lower())

        # Parse dates
        start_date = self._parse_datetime(data.get("startDate"))
        end_date = self._parse_datetime(data.get("endDate"))
        resolution_date = self._parse_datetime(data.get("resolutionDate"))

        # Parse prices
        yes_price = Decimal(str(data.get("outcomePrices", ["0.5", "0.5"])[0]))
        no_price = Decimal(str(data.get("outcomePrices", ["0.5", "0.5"])[1]))

        # Calculate spread
        best_bid = Decimal(str(data.get("bestBid", yes_price)))
        best_ask = Decimal(str(data.get("bestAsk", yes_price)))
        spread = abs(best_ask - best_bid)

        return Market(
            id=data.get("id", ""),
            question=data.get("question", ""),
            description=data.get("description"),
            category=data.get("category", "Other"),
            tags=data.get("tags", []),
            status=status,
            start_date=start_date or datetime.now(),
            end_date=end_date or datetime.now(),
            resolution_date=resolution_date,
            liquidity=Decimal(str(data.get("liquidity", 0))),
            volume=Decimal(str(data.get("volume", 0))),
            volume_24h=Decimal(str(data.get("volume24hr", 0))),
            num_traders=int(data.get("numTraders", 0)),
            yes_price=yes_price,
            no_price=no_price,
            spread=spread,
            event_id=data.get("eventId"),
            market_maker=data.get("marketMaker"),
        )

    def _parse_event(self, data: Dict) -> Event:
        """Parse event data from API response.

        Args:
            data: Raw event data

        Returns:
            Event object
        """
        start_date = self._parse_datetime(data.get("startDate"))
        end_date = self._parse_datetime(data.get("endDate"))

        # Parse associated markets
        markets = []
        for market_data in data.get("markets", []):
            try:
                market = self._parse_market(market_data)
                markets.append(market)
            except Exception as e:
                logger.warning("event_market_parse_error", error=str(e))

        return Event(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description"),
            category=data.get("category", "Other"),
            markets=markets,
            start_date=start_date or datetime.now(),
            end_date=end_date or datetime.now(),
            tags=data.get("tags", []),
        )

    @staticmethod
    def _parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string.

        Args:
            date_str: ISO format datetime string

        Returns:
            datetime object or None
        """
        if not date_str:
            return None

        try:
            # Handle ISO format with Z suffix
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            return datetime.fromisoformat(date_str)
        except (ValueError, AttributeError):
            return None
