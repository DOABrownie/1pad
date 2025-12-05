from typing import Tuple

import pandas as pd


def detect_break_of_structure(
    df: pd.DataFrame,
    pivot_highs: pd.Series,
    pivot_lows: pd.Series,
    lookback_pivots: int = 10,
) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Detect simple Break of Structure (BOS).

    Bullish BOS:
      - Latest close breaks above a recent pivot high.

    Bearish BOS:
      - Latest close breaks below a recent pivot low.

    We mark BOS at the bar where the break occurs.

    Returns:
      - df with 'bos_up' and 'bos_down' boolean columns
      - bos_up: series with True at bullish BOS bars
      - bos_down: series with True at bearish BOS bars
    """
    df = df.copy()

    bos_up = [False] * len(df)
    bos_down = [False] * len(df)

    closes = df["close"]

    # Indices of pivots
    ph_idx = pivot_highs.dropna().index
    pl_idx = pivot_lows.dropna().index

    if len(df) == 0:
        df["bos_up"] = False
        df["bos_down"] = False
        return df, df["bos_up"], df["bos_down"]

    for i in range(len(df)):
        if i == 0:
            continue

        current_close = closes.iloc[i]
        current_index = df.index[i]

        # Consider recent pivot highs / lows up to lookback_pivots
        recent_ph = ph_idx[ph_idx < current_index][-lookback_pivots:]
        recent_pl = pl_idx[pl_idx < current_index][-lookback_pivots:]

        if len(recent_ph) > 0:
            last_pivot_high = pivot_highs.loc[recent_ph].iloc[-1]
            if current_close > last_pivot_high:
                bos_up[i] = True

        if len(recent_pl) > 0:
            last_pivot_low = pivot_lows.loc[recent_pl].iloc[-1]
            if current_close < last_pivot_low:
                bos_down[i] = True

    df["bos_up"] = bos_up
    df["bos_down"] = bos_down

    return df, df["bos_up"], df["bos_down"]
