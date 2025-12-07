from typing import Optional, Dict, Any

import pandas as pd

from strategy.pivots import detect_pivots
from strategy.fibs import compute_fib_levels


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
    strategy_name = config.get("strategy", "1pad").lower()

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
    1pad long-only strategy (initial implementation).

    High level logic (matches the TradingView explanation):

      - Market structure:
          structure_high = highest CLOSE in the last 50 candles.
      - Bullish BOS (break of structure):
          current close > previous structure_high.

      - After a BOS:
          * wait for a pivot high (PH) defined as a 3-candle pattern:
                high[i] > high[i-1] and high[i] > high[i+1]
            (implemented via detect_pivots(..., left=1, right=1)).
          * use the most recent pivot low (PL) BEFORE that PH.

      - Build Fibonacci retracement for the swing PL -> PH (long direction):
          levels = [0, 0.236, 0.618, 1.0]
          Fib(0)    ≈ swing high
          Fib(1.0)  ≈ swing low
          Fib(0.236), Fib(0.618) between them.

      - Net window (entry zone):
          delta_pct   = |Fib(0.236) - Fib(1.0)| / Fib(1.0) * 100
          net_size    = delta_pct * 0.375      (e.g. 8% -> 3%)
          net_center  = Fib(0.618)
          half_net    = net_size / 2

          zone_top    = net_center * (1 + half_net / 100)
          zone_bottom = net_center * (1 - half_net / 100)

          (clamped inside the swing range for safety).

      - Entry trigger:
          On the FIRST candle after that PH which trades into [zone_bottom, zone_top]
          (its high/low range intersects the zone), we emit a signal to create a
          bundle of limit-buy orders:

            * entries: num_limit_orders prices equally spaced inside the zone
              (top -> bottom).
            * stop_loss:   Fib(1.0)
            * take_profit: Fib(0.236)

          The engine + risk layer will size these so that if ALL limits fill and
          price hits stop_loss, loss ≈ account_size * risk_pct.

    Returns a signal with the SAME structure as _sma_generate_signal:

        {
            "strategy": "1pad",
            "signal_type": "limit_bundle",
            "direction": "long",
            "entries": [...],
            "stop_loss": ...,
            "take_profit": ...,
            "meta": {...debug info...}
        }
    """
    if df is None or df.empty:
        return None

    # Need enough history for structure + pivots
    structure_lookback = 50
    if len(df) < structure_lookback + 5:
        return None

    closes = df["close"]
    highs = df["high"]
    lows = df["low"]

    # ----------------- Market structure & BOS -----------------
    structure_high = closes.rolling(structure_lookback).max()
    prev_structure = structure_high.shift(1)

    # Bullish BOS when close breaks above previous structure high
    bos_up = closes > prev_structure

    current_idx = df.index[-1]
    bos_indices = bos_up[bos_up].index

    if bos_indices.empty:
        return None

    # Use the most recent BOS before the current bar
    bos_idx = bos_indices[-1]
    if bos_idx >= current_idx:
        # BOS is on or after the current bar -> wait for more data
        return None

    # ----------------- Pivots (PH & PL) -----------------
    # Use 3-candle pivots: left=1, right=1
    _, pivot_highs, pivot_lows = detect_pivots(df, left=1, right=1)

    # Most recent pivot high after BOS and before the current bar
    ph_candidates = pivot_highs.dropna()
    ph_candidates = ph_candidates[
        (ph_candidates.index > bos_idx) & (ph_candidates.index < current_idx)
    ]
    if ph_candidates.empty:
        return None
    ph_idx = ph_candidates.index[-1]

    # Most recent pivot low before that pivot high
    pl_candidates = pivot_lows.dropna()
    pl_candidates = pl_candidates[pl_candidates.index < ph_idx]
    if pl_candidates.empty:
        return None
    pl_idx = pl_candidates.index[-1]

    swing_low = float(lows.loc[pl_idx])
    swing_high = float(highs.loc[ph_idx])
    if swing_high <= swing_low:
        # Degenerate swing
        return None

    # ----------------- Fibonacci & net window -----------------
    fibs = compute_fib_levels(
        swing_low=swing_low,
        swing_high=swing_high,
        direction="long",
        levels=[0, 0.236, 0.618, 1.0],
    )

    fib_0 = fibs["0"]
    fib_0236 = fibs["0.236"]
    fib_0618 = fibs["0.618"]
    fib_1 = fibs["1.0"]

    if fib_1 == 0:
        return None

    # % delta between Fib 1.0 and Fib 0.236
    delta_pct = abs((fib_0236 - fib_1) / fib_1) * 100.0
    net_size_pct = delta_pct * 0.375
    half_net_pct = net_size_pct / 2.0

    center_price = fib_0618
    zone_top = center_price * (1 + half_net_pct / 100.0)
    zone_bottom = center_price * (1 - half_net_pct / 100.0)

    # Keep the zone inside the swing range just in case
    upper_bound = max(fib_0, fib_1)
    lower_bound = min(fib_0, fib_1)
    zone_top = min(zone_top, upper_bound)
    zone_bottom = max(zone_bottom, lower_bound)
    if zone_bottom >= zone_top:
        return None

    # ----------------- First touch of the net window -----------------
    cur_low = float(lows.loc[current_idx])
    cur_high = float(highs.loc[current_idx])

    # Does the current candle enter the net zone at all?
    touches_now = (cur_low <= zone_top) and (cur_high >= zone_bottom)
    if not touches_now:
        return None

    # Ensure this is the FIRST bar since the pivot high that touches the zone
    cur_pos = df.index.get_loc(current_idx)
    ph_pos = df.index.get_loc(ph_idx)
    if cur_pos - ph_pos > 1:
        low_hist = lows.iloc[ph_pos + 1 : cur_pos]
        high_hist = highs.iloc[ph_pos + 1 : cur_pos]
        if not low_hist.empty:
            touched_before = (low_hist <= zone_top) & (high_hist >= zone_bottom)
            if touched_before.any():
                # The zone was touched earlier; the "first touch" already happened.
                return None

    # ----------------- Build the limit entry bundle -----------------
    num_orders = int(config.get("num_limit_orders", 4))
    if num_orders <= 0:
        return None

    if num_orders == 1:
        entries = [center_price]
    else:
        step = (zone_top - zone_bottom) / float(num_orders - 1)
        # Place orders from top -> bottom inside the net window
        entries = [zone_top - step * i for i in range(num_orders)]

    sl = fib_1
    tp = fib_0236

    signal: Signal = {
        "strategy": "1pad",
        "signal_type": "limit_bundle",
        "direction": "long",
        "entries": [float(e) for e in entries],
        "stop_loss": float(sl),
        "take_profit": float(tp),
        "meta": {
            # Helpful for debugging / later plotting
            "bos_index": bos_idx,
            "pivot_high_index": ph_idx,
            "pivot_low_index": pl_idx,
            "fib_levels": {
                "0": float(fib_0),
                "0.236": float(fib_0236),
                "0.618": float(fib_0618),
                "1.0": float(fib_1),
            },
            "net": {
                "size_pct": float(net_size_pct),
                "top": float(zone_top),
                "bottom": float(zone_bottom),
                "center": float(center_price),
            },
        },
    }

    return signal

