from typing import List, Callable, Any

import pandas as pd

from execution.orders import Trade
from app_logging.event_logger import get_logger

logger = get_logger(__name__)


class ReplayState:
    """
    Holds data needed for bar-replay style visualization.

    In a simple approach:
      - snapshots: list of dicts, each representing state at a given candle index.
    """

    def __init__(self):
        self.snapshots: List[dict] = []

    def add_snapshot(self, index: int, df_slice: pd.DataFrame, trades: List[Trade]):
        snapshot = {
            "index": index,
            "df": df_slice.copy(),
            "trades": trades.copy(),
        }
        self.snapshots.append(snapshot)


def replay_backtest(
    replay_state: ReplayState,
    on_step: Callable[[dict], Any],
):
    """
    Simple replay loop that iterates over stored snapshots and calls `on_step`.

    `on_step` will typically update the chart in the UI layer.
    """
    for snapshot in replay_state.snapshots:
        logger.debug(f"Replaying snapshot index={snapshot['index']}")
        on_step(snapshot)
