from typing import Optional, Dict, Any

import pandas as pd


Signal = Dict[str, Any]


def generate_signal(df: pd.DataFrame, config: Dict[str, Any]) -> Optional[Signal]:
    """
    Strategy dispatcher.

    Looks at config['strategy'] and calls the appropriate strategy-specific
    signal generator, which returns a generic 'signal' dict or None.

    The engine will NOT decide what kind of orders to create.
    The strategy decides and encodes that decision in the 'signal_type' field.

    Signal contract (for now):

        None -> no new setup on this bar

        dict with at least:
            {
                "strategy": "sma" or "1pad",
                "signal_type": "market_entry" or "limit_bundle",
                "direction": "long" or "short",
                "entries": [float, ...],  # list of proposed entry prices
                "stop_loss": float,
                "take_profit": float,
                "meta": dict,             # optional extra info
            }

    For the SMA test strategy:
        - signal_type = "market_entry"
        - entries     = [current_close]
        - direction   = "long"
        - stop_loss   = entry * 0.97
        - take_profit = entry * 1.03

    For the future 1pad strategy:
        - we will likely have:
            signal_type = "limit_bundle"
            entries     = [entry1, entry2, ...]  (fib-based limit levels)
    """
    strategy_name = config.get("strategy", "sma").lower()

    if strategy_name == "sma":
        return _sma_generate_signal(df, config)
    elif strategy_name == "1pad":
        return _onepad_generate_signal(df, config)
    else:
        # Unknown strategy -> do nothing
        return None


def _sma_generate_signal(
    df: pd.DataFrame,
    config: Dict[str, Any],
) -> Optional[Signal]:
    """
    Very basic 10/50 SMA bullish crossover strategy.

    Entry condition:
      - 10-period SMA crosses UP over 50-period SMA
        on the current bar.

    Order semantics:
      - direction   = "long"
      - entry_price = current close
      - stop_loss   = entry_price * 0.97  (approx -3%)
      - take_profit = entry_price * 1.03  (approx +3%)

    This is deliberately simple and is intended only as a test harness
    for the engine and replay logic.
    """
    # Need enough history for the SMAs
    if len(df) < 51:
        return None

    closes = df["close"]

    # Compute SMAs on the fly for now.
    # Later we can compute these once in the engine and reuse.
    sma_fast = closes.rolling(10).mean()
    sma_slow = closes.rolling(50).mean()

    i = len(df) - 1  # current bar index

    fast_now = sma_fast.iloc[i]
    slow_now = sma_slow.iloc[i]
    fast_prev = sma_fast.iloc[i - 1]
    slow_prev = sma_slow.iloc[i - 1]

    # If any SMA value is NaN, skip.
    if any(pd.isna(x) for x in (fast_now, slow_now, fast_prev, slow_prev)):
        return None

    # Bullish crossover: fast crosses above slow
    crossed_up = fast_now > slow_now and fast_prev <= slow_prev
    if not crossed_up:
        return None

    entry = closes.iloc[i]
    tp = entry * 1.03
    sl = entry * 0.97

    signal: Signal = {
        "strategy": "sma",
        "signal_type": "market_entry",  # important for the engine
        "direction": "long",
        "entries": [float(entry)],      # single market entry at current close
        "stop_loss": float(sl),
        "take_profit": float(tp),
        "meta": {
            "sma_fast": float(fast_now),
            "sma_slow": float(slow_now),
        },
    }

    return signal


def _onepad_generate_signal(
    df: pd.DataFrame,
    config: Dict[str, Any],
) -> Optional[Signal]:
    """
    Placeholder for the real 1pad strategy.

    Eventually this will implement:
      - pivot highs/lows
      - break of structure
      - fib levels
      - multiple limit entry orders, etc.

    The important part is that it returns the SAME signal shape as _sma_generate_signal,
    so the engine and replay code do not need to change when 1pad is implemented.
    """
    # For now, we do nothing for 1pad until the real logic is ready.
    return None
