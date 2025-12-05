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

    entry_price_avg: Optional[float] = None
    exit_price: Optional[float] = None
    size_total: float = 0.0
    pnl_usd: float = 0.0

    extra: Dict[str, Any] = field(default_factory=dict)


class OrderManager:
    """
    Responsible for placing and tracking orders.

    LIVE mode:
      - will be wired to ccxt.

    BACKTEST mode:
      - will be backed by a simulated execution engine.
    """

    def __init__(self, exchange=None, simulate_only: bool = True):
        self.exchange = exchange
        self.simulate_only = simulate_only

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
        For now, this only logs the intent and attaches Order objects to the Trade.
        """
        logger.info(
            f"Placing limit orders for trade {trade.id}: "
            f"entries={entries}, sizes={sizes}, SL={stop_loss}, TP={take_profit}"
        )

        trade.stop_loss = stop_loss
        trade.take_profit = take_profit

        for entry_price, size in zip(entries, sizes):
            order = Order(
                id=None,  # real exchange order id will be filled in LIVE mode
                symbol=trade.symbol,
                side=OrderSide.BUY if trade.direction == "long" else OrderSide.SELL,
                type=OrderType.LIMIT,
                price=entry_price,
                size=size,
            )
            trade.entry_orders.append(order)

        return trade
