from typing import Dict

import ccxt
import pandas as pd

from app_logging.event_logger import get_logger

logger = get_logger(__name__)


def _create_exchange() -> ccxt.Exchange:
    """
    Create a ccxt exchange instance for backtesting data.

    Using Binance for now (public data).
    """
    exchange_id = "binance"
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class(
        {
            "enableRateLimit": True,
        }
    )
    return exchange


def _fetch_ohlcv_history(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    limit: int,
) -> pd.DataFrame:
    """
    Fetch OHLCV candles from the exchange and return as a pandas DataFrame.

    Columns: [open, high, low, close, volume]
    Index:   timestamp (datetime)
    """
    logger.info(
        f"Fetching OHLCV: symbol={symbol}, timeframe={timeframe}, limit={limit}"
    )

    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    if not raw:
        logger.warning("No OHLCV data returned from exchange.")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(
        raw,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)

    logger.info(f"Fetched {len(df)} candles.")
    return df


def run_backtest(config: Dict):
    """
    Backtest entry point.

    For now this:
      - loads OHLCV via ccxt
      - if preview_replay is True, launches a Dash bar-replay viewer
      - otherwise just logs that data was loaded

    Strategy + orders + metrics will be layered on top of this later.
    """
    logger.info("Backtest started.")
    logger.info(f"Config: {config}")

    symbol = config["symbol"]
    timeframe = config["timeframe"]
    lookback_bars = int(config["lookback_bars"])
    preview = bool(config.get("preview_replay", False))

    exchange = _create_exchange()
    df = _fetch_ohlcv_history(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        limit=lookback_bars,
    )

    if df.empty:
        logger.warning("Backtest aborted, no OHLCV data loaded.")
        return

    if preview:
        from backtest.replay_viewer import run_replay_viewer

        logger.info("Launching backtest replay viewer.")
        run_replay_viewer(df, symbol=symbol, timeframe=timeframe)
    else:
        logger.info("Preview disabled. Data loaded, but no replay shown yet.")

    logger.info("Backtest finished.")
