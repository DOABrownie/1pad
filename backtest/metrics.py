from typing import List, Dict

from execution.orders import Trade, TradeStatus
from app_logging.event_logger import get_logger

logger = get_logger(__name__)


def compute_metrics(
    trades: List[Trade],
    starting_balance: float,
) -> Dict:
    """
    Compute simple backtest metrics from a list of trades.
    """
    closed_trades = [t for t in trades if t.status == TradeStatus.CLOSED]

    ending_balance = starting_balance + sum(t.pnl_usd for t in closed_trades)
    net_profit = ending_balance - starting_balance
    net_return_pct = (net_profit / starting_balance) * 100 if starting_balance > 0 else 0.0

    num_trades = len(closed_trades)
    wins = [t for t in closed_trades if t.pnl_usd > 0]
    losses = [t for t in closed_trades if t.pnl_usd <= 0]

    win_rate = (len(wins) / num_trades * 100) if num_trades > 0 else 0.0

    durations = []
    for t in closed_trades:
        if t.opened_at and t.closed_at:
            durations.append((t.closed_at - t.opened_at).total_seconds())

    avg_duration = sum(durations) / len(durations) if durations else 0.0
    max_duration = max(durations) if durations else 0.0
    min_duration = min(durations) if durations else 0.0

    metrics = {
        "starting_balance": starting_balance,
        "ending_balance": ending_balance,
        "net_profit": net_profit,
        "net_return_pct": net_return_pct,
        "num_trades": num_trades,
        "win_rate_pct": win_rate,
        "avg_trade_duration_sec": avg_duration,
        "max_trade_duration_sec": max_duration,
        "min_trade_duration_sec": min_duration,
    }

    logger.info(f"Backtest metrics: {metrics}")
    return metrics
