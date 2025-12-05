from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime

from app_logging.event_logger import get_logger

logger = get_logger(__name__)


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"


class TradeStatus(str, Enum):
    PENDING = "pending"   # waiting for entry fill
    OPEN = "open"         # entry filled, position live
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class Order:
    id: Optional[str]
    symbol: str
    side: OrderSide
    type: OrderType
    price: float
    size: float
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trade:
    """
    Represents a logical trade made up of one or more entry orders,
    plus associated SL / TP levels.
    """
    id: str
    symbol: str
    direction: str        # "long" or "short"
    status: TradeStatus = TradeStatus.PENDING

    entry_orders: List[Order] = field(default_factory=list)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    # Basic PnL fields (for backtesting and reporting)
    entry_price_avg: Optional[float] = None
    exit_price: Optional[float] = None
    size_total: float = 0.0
    pnl_usd: float = 0.0

    extra: Dict[str, Any] = field(default_factory=dict)


class OrderManager:
    """
    Responsible for placing and tracking orders.

    In LIVE mode:
      - Will be wired to a real ccxt exchange.

    In BACKTEST mode:
      - Can be backed by a simulated execution engine.
    """

    def __init__(self, exchange=None, simulate_only: bool = True):
        self.exchange = exchange
        self.simulate_only = simulate_only

    # --- Public API stubs we will flesh out later ---

    def place_limit_orders_for_trade(
        self,
        trade: Trade,
        entries: List[float],
        sizes: List[float],
        stop_loss: float,
        take_profit: float,
    ) -> Trade:
        """
        Create a set of limit orders (scaled entries) with a common SL/TP.

        For now, this only logs the intent. Later we will:
          - send orders via ccxt (LIVE)
          - or simulate fills (BACKTEST)
        """
        logger.info(
            f"Placing limit orders for trade {trade.id}: "
            f"entries={entries}, sizes={sizes}, SL={stop_loss}, TP={take_profit}"
        )

        trade.stop_loss = stop_loss
        trade.take_profit = take_profit

        for i, (entry_price, size) in enumerate(zip(entries, sizes), start=1):
            order = Order(
                id=None,  # ccxt order id will be set after sending
                symbol=trade.symbol,
                side=OrderSide.BUY if trade.direction == "long" else OrderSide.SELL,
                type=OrderType.LIMIT,
                price=entry_price,
                size=size,
            )
            trade.entry_orders.append(order)

        return trade

    def sync_orders_with_exchange(self, trade: Trade):
        """
        Placeholder for future implementation.

        LIVE:
          - Query open orders, update their statuses in the Trade object.

        BACKTEST:
          - Execution engine will manage fills, this might be a no-op here.
        """
        logger.debug(f"Syncing orders with exchange for trade {trade.id} (stub).")

    def close_trade_at_market(self, trade: Trade, current_price: float):
        """
        Placeholder for closing a trade at market price.

        In LIVE mode we will:
          - Submit a market order to close the remaining position.

        For now this only logs the intent.
        """
        logger.info(
            f"Closing trade {trade.id} at market price {current_price} (stub)."
        )
