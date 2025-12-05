from typing import Dict, List, Optional

import pandas as pd

from .pivots import detect_pivots
from .structure import detect_break_of_structure
from .fibs import compute_fib_levels


def generate_signals(
    df: pd.DataFrame,
    config: Dict,
) -> Optional[Dict]:
    """
    Very high-level strategy stub.

    Input:
      df: closed candles
      config: includes things like num_limit_orders, etc.

    Output:
      Either:
        None  -> no new setup
      Or:
        {
          "direction": "long" or "short",
          "entries": [price1, price2, ...],
          "stop_loss": sl_price,
          "take_profit": tp_price,
          "meta": {...}
        }
    """
    if df.empty or len(df) < 30:
        return None

    # Step 1: detect pivots
    df_pivots, pivot_highs, pivot_lows = detect_pivots(df)

    # Step 2: detect BOS
    df_bos, bos_up, bos_down = detect_break_of_structure(
        df_pivots, pivot_highs, pivot_lows
    )

    # Placeholder logic:
    # - If the latest bar has a bullish BOS, define a long setup using
    #   the most recent pivot low and high as the swing.
    # - Similarly for bearish BOS.
    last_index = df_bos.index[-1]

    if df_bos["bos_up"].iloc[-1]:
        # Find last pivot low and high before BOS
        last_pivot_low_idx = pivot_lows.dropna().index[-1]
        last_pivot_high_idx = pivot_highs.dropna().index[-1]

        swing_low = pivot_lows.loc[last_pivot_low_idx]
        swing_high = pivot_highs.loc[last_pivot_high_idx]

        fibs = compute_fib_levels(swing_low, swing_high, direction="long")

        # Example: use 0.5 and 0.618 fib levels as entries
        entries = [
            fibs.get("0.5"),
            fibs.get("0.618"),
        ]
        entries = [e for e in entries if e is not None]

        if not entries:
            return None

        stop_loss = swing_low
        take_profit = swing_high + (swing_high - swing_low)  # placeholder RR=1:1

        return {
            "direction": "long",
            "entries": entries,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "meta": {
                "signal_time": last_index,
            },
        }

    if df_bos["bos_down"].iloc[-1]:
        last_pivot_low_idx = pivot_lows.dropna().index[-1]
        last_pivot_high_idx = pivot_highs.dropna().index[-1]

        swing_low = pivot_lows.loc[last_pivot_low_idx]
        swing_high = pivot_highs.loc[last_pivot_high_idx]

        fibs = compute_fib_levels(swing_low, swing_high, direction="short")

        entries = [
            fibs.get("0.5"),
            fibs.get("0.618"),
        ]
        entries = [e for e in entries if e is not None]

        if not entries:
            return None

        stop_loss = swing_high
        take_profit = swing_low - (swing_high - swing_low)

        return {
            "direction": "short",
            "entries": entries,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "meta": {
                "signal_time": last_index,
            },
        }

    return None
