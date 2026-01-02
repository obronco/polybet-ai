"""Polymarket CLOB client for order execution and trading."""

from decimal import Decimal
from typing import Dict, List, Optional

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.constants import POLYGON

from ..models.market import OrderBook, OrderSide
from ..models.trade import Order, TradeStatus
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PolymarketClient:
    """Client for Polymarket CLOB (Central Limit Order Book)."""

    def __init__(
        self,
        private_key: Optional[str] = None,
        chain_id: int = POLYGON,
    ):
        """Initialize Polymarket CLOB client.

        Args:
            private_key: Wallet private key (defaults to config)
            chain_id: Blockchain chain ID
        """
        self.private_key = (
            private_key or config.settings.polygon_wallet_private_key.get_secret_value()
        )
        self.chain_id = chain_id

        # Initialize CLOB client
        self.client = ClobClient(
            key=self.private_key,
            chain_id=self.chain_id,
        )

        # Set API credentials if available
        api_key_value = config.settings.polymarket_api_key.get_secret_value()
        if api_key_value:
            self.client.set_api_creds(
                api_key=api_key_value,
                api_secret=config.settings.polymarket_api_secret.get_secret_value(),
                api_passphrase=config.settings.polymarket_passphrase.get_secret_value(),
            )

        logger.info("polymarket_client_initialized", chain_id=chain_id)

    async def get_order_book(self, token_id: str) -> OrderBook:
        """Get order book for a market token.

        Args:
            token_id: Market token identifier

        Returns:
            OrderBook object
        """
        try:
            book_data = self.client.get_order_book(token_id)

            bids = [
                {"price": Decimal(str(b["price"])), "size": Decimal(str(b["size"]))}
                for b in book_data.get("bids", [])
            ]

            asks = [
                {"price": Decimal(str(a["price"])), "size": Decimal(str(a["size"]))}
                for a in book_data.get("asks", [])
            ]

            order_book = OrderBook(
                market_id=token_id,
                bids=bids,
                asks=asks,
            )

            logger.debug(
                "order_book_fetched",
                token_id=token_id,
                bid_levels=len(bids),
                ask_levels=len(asks),
            )

            return order_book

        except Exception as e:
            logger.error("get_order_book_error", token_id=token_id, error=str(e))
            raise

    def create_order(
        self,
        token_id: str,
        price: Decimal,
        size: Decimal,
        side: OrderSide,
        order_type: str = "GTC",  # Good Till Cancelled
    ) -> Order:
        """Create a new order.

        Args:
            token_id: Market token identifier
            price: Limit price (0-1)
            size: Order size in contracts
            side: Order side (BUY/SELL)
            order_type: Order type (GTC, FOK, etc.)

        Returns:
            Created Order object
        """
        try:
            # Convert side to py-clob-client format
            clob_side = "BUY" if side in [OrderSide.YES, OrderSide.BUY] else "SELL"

            # Build order arguments
            order_args = OrderArgs(
                price=float(price),
                size=float(size),
                side=clob_side,
                token_id=token_id,
            )

            # Create and sign order
            signed_order = self.client.create_order(order_args)

            order = Order(
                id=signed_order.get("orderID"),
                market_id=token_id,
                side=side,
                price=price,
                size=size,
                status=TradeStatus.PENDING,
                signature=signed_order.get("signature"),
            )

            logger.info(
                "order_created",
                order_id=order.id,
                token_id=token_id,
                price=float(price),
                size=float(size),
                side=clob_side,
            )

            return order

        except Exception as e:
            logger.error("create_order_error", error=str(e))
            raise

    def submit_order(self, order: Order) -> Dict:
        """Submit a signed order to the order book.

        Args:
            order: Order object with signature

        Returns:
            Response from order submission
        """
        try:
            # Submit order to CLOB
            response = self.client.post_order(
                order.signature,  # Signed order data
                order_type=OrderType.GTC,
            )

            logger.info(
                "order_submitted",
                order_id=order.id,
                response=response,
            )

            return response

        except Exception as e:
            logger.error("submit_order_error", order_id=order.id, error=str(e))
            raise

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order.

        Args:
            order_id: Order identifier

        Returns:
            True if cancelled successfully
        """
        try:
            self.client.cancel_order(order_id)
            logger.info("order_cancelled", order_id=order_id)
            return True

        except Exception as e:
            logger.error("cancel_order_error", order_id=order_id, error=str(e))
            return False

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get status of an order.

        Args:
            order_id: Order identifier

        Returns:
            Order status data or None
        """
        try:
            status = self.client.get_order(order_id)
            logger.debug("order_status_fetched", order_id=order_id)
            return status

        except Exception as e:
            logger.error("get_order_status_error", order_id=order_id, error=str(e))
            return None

    def get_orders(self, market_id: Optional[str] = None) -> List[Dict]:
        """Get all orders, optionally filtered by market.

        Args:
            market_id: Optional market identifier filter

        Returns:
            List of order data
        """
        try:
            orders = self.client.get_orders(market=market_id)
            logger.debug("orders_fetched", count=len(orders))
            return orders

        except Exception as e:
            logger.error("get_orders_error", error=str(e))
            return []

    def get_positions(self) -> List[Dict]:
        """Get current open positions.

        Returns:
            List of position data
        """
        try:
            positions = self.client.get_positions()
            logger.debug("positions_fetched", count=len(positions))
            return positions

        except Exception as e:
            logger.error("get_positions_error", error=str(e))
            return []

    def get_balance(self) -> Decimal:
        """Get USDC balance.

        Returns:
            Current balance in USDC
        """
        try:
            balance_data = self.client.get_balance()
            balance = Decimal(str(balance_data.get("balance", 0)))
            logger.debug("balance_fetched", balance=float(balance))
            return balance

        except Exception as e:
            logger.error("get_balance_error", error=str(e))
            return Decimal(0)

    def execute_market_order(
        self,
        token_id: str,
        size: Decimal,
        side: OrderSide,
        max_slippage: Decimal = Decimal("0.02"),
    ) -> Order:
        """Execute a market order with slippage protection.

        Args:
            token_id: Market token identifier
            size: Order size
            side: Order side
            max_slippage: Maximum acceptable slippage (default 2%)

        Returns:
            Executed order
        """
        try:
            # Get current order book
            order_book = self.get_order_book(token_id)

            # Determine price with slippage protection
            if side in [OrderSide.YES, OrderSide.BUY]:
                base_price = order_book.best_ask
                if not base_price:
                    raise ValueError("No asks available in order book")
                # Add slippage for market buy
                price = base_price * (1 + max_slippage)
            else:
                base_price = order_book.best_bid
                if not base_price:
                    raise ValueError("No bids available in order book")
                # Subtract slippage for market sell
                price = base_price * (1 - max_slippage)

            # Ensure price is within valid range
            price = max(Decimal("0.01"), min(Decimal("0.99"), price))

            # Create and submit order
            order = self.create_order(token_id, price, size, side)
            self.submit_order(order)

            logger.info(
                "market_order_executed",
                token_id=token_id,
                size=float(size),
                price=float(price),
                side=side.value,
            )

            return order

        except Exception as e:
            logger.error("execute_market_order_error", error=str(e))
            raise

    def get_trades(self, market_id: Optional[str] = None) -> List[Dict]:
        """Get trade history.

        Args:
            market_id: Optional market filter

        Returns:
            List of trade data
        """
        try:
            trades = self.client.get_trades(market=market_id)
            logger.debug("trades_fetched", count=len(trades))
            return trades

        except Exception as e:
            logger.error("get_trades_error", error=str(e))
            return []
