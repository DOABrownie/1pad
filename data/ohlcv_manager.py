from typing import Optional

import pandas as pd


class OhlcvManager:
    """
    Manages historical (closed) candles and the current forming candle.

    Live mode:
      - Maintains a rolling window of size max_bars.
      - On new closed candle, adds it and drops the oldest if needed.

    Backtest mode:
      - We can bypass the rolling behavior and load full history.
    """

    def __init__(self, exchange, symbol: str, timeframe: str, max_bars: int = 1000):
        self.exchange = exchange  # placeholder for ccxt exchange
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_bars = max_bars

        self.df_closed = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        )
        self.current_candle: Optional[dict] = None

    def load_initial_history(self, limit: int):
        """
        Placeholder: fetches initial OHLCV history.
        For now, this just sets up an empty DataFrame.
        Later we will plug in ccxt.fetch_ohlcv here.
        """
        # TODO: implement ccxt fetch_ohlcv. For now, keep empty df.
        # Example:
        # raw = self.exchange.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=limit)
        # df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        # df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        # df.set_index("timestamp", inplace=True)
        # self.df_closed = df
        pass

    def update_with_new_closed_candle(self, candle: pd.Series):
        """
        Add a new closed candle to df_closed and enforce the rolling window.

        candle: a pandas Series with index fields matching df_closed columns,
                index name should be a timestamp.
        """
        # Append the candle to df_closed
        self.df_closed.loc[candle.name] = candle

        # Enforce rolling window in LIVE mode
        if len(self.df_closed) > self.max_bars:
            # Drop the oldest candle (first index)
            oldest_index = self.df_closed.index[0]
            self.df_closed.drop(index=oldest_index, inplace=True)

    def set_current_candle(self, o: float, h: float, l: float, c: float, ts):
        """
        Set or update the forming (current) candle.
        ts will typically be a timestamp for the current interval.
        """
        self.current_candle = {
            "timestamp": ts,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
        }

    def get_closed_candles(self) -> pd.DataFrame:
        return self.df_closed.copy()

    def get_current_candle(self) -> Optional[dict]:
        return self.current_candle
