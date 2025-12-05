from typing import Tuple

import pandas as pd


def detect_pivots(
    df: pd.DataFrame, left: int = 2, right: int = 2
) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Detect swing highs and swing lows in the OHLC data.

    A pivot high at index i if its high is greater than highs for `left`
    candles before and `right` candles after.
    Similarly for pivot lows using the lows.

    Returns:
      - df with 'pivot_high' and 'pivot_low' boolean columns
      - pivot_highs: series of pivot high prices (NaN when not a pivot)
      - pivot_lows: series of pivot low prices (NaN when not a pivot)
    """
    if df.empty:
        df["pivot_high"] = False
        df["pivot_low"] = False
        return df, df["pivot_high"], df["pivot_low"]

    highs = df["high"].values
    lows = df["low"].values

    pivot_high = [False] * len(df)
    pivot_low = [False] * len(df)

    for i in range(left, len(df) - right):
        high_segment = highs[i - left : i + right + 1]
        low_segment = lows[i - left : i + right + 1]

        if highs[i] == max(high_segment):
            pivot_high[i] = True
        if lows[i] == min(low_segment):
            pivot_low[i] = True

    df = df.copy()
    df["pivot_high"] = pivot_high
    df["pivot_low"] = pivot_low

    pivot_highs = df["high"].where(df["pivot_high"])
    pivot_lows = df["low"].where(df["pivot_low"])

    return df, pivot_highs, pivot_lows
