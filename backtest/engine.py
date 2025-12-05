from typing import Dict, List, Tuple

from datetime import datetime

import ccxt
import pandas as pd

from app_logging.event_logger import get_logger
from strategy.signals import generate_signal
from execution.orders import Trade, TradeStatus
from execution.risk import compute_position_size
from backtest.metrics import compute_metrics

logger = get_logger(__name__)


# ----------------- Exchange / data helpers -----------------


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


def _add_indicators(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Add any indicator columns needed for the selected strategy.

    For now:
      - If strategy == 'sma':
          * sma_fast: 10 period SMA of close
          * sma_slow: 50 period SMA of close

      - If strategy == '1pad':
          * we do nothing yet (placeholder for future pivots/BOS/fibs etc.)
    """
    strategy_name = config.get("strategy", "sma").lower()

    if strategy_name == "sma":
        closes = df["close"]
        df["sma_fast"] = closes.rolling(10).mean()
        df["sma_slow"] = closes.rolling(50).mean()

    elif strategy_name == "1pad":
        # Placeholder for future 1pad-specific preparatory columns
        # e.g. pivot highs/lows, structure labels, etc.
        pass

    return df



# ----------------- Simple trade simulation -----------------


def _simulate_trade(
    df: pd.DataFrame,
    start_idx: int,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
) -> Tuple[int, float]:
    """
    Simulate a simple trade from start_idx onwards.

    Assumptions:
      - Entry at the close of bar at index start_idx.
      - For each subsequent bar, we check:

          long:
            if low <= SL -> SL hit
            elif high >= TP -> TP hit

          short:
            if high >= SL -> SL hit
            elif low <= TP -> TP hit

      - If neither SL nor TP hit by the end of data,
        exit at the last close.

    Returns:
        (exit_index, exit_price)
    """
    for i in range(start_idx + 1, len(df)):
        high = df["high"].iloc[i]
        low = df["low"].iloc[i]

        if direction == "long":
            if low <= stop_loss:
                return i, stop_loss
            if high >= take_profit:
                return i, take_profit
        else:  # short
            if high >= stop_loss:
                return i, stop_loss
            if low <= take_profit:
                return i, take_profit

    exit_idx = len(df) - 1
    exit_price = df["close"].iloc[-1]
    return exit_idx, exit_price


def _pnl_for_trade(
    direction: str,
    entry_price: float,
    exit_price: float,
    size: float,
) -> float:
    """
    Compute PnL in quote currency (USD) for a trade.
    """
    if direction == "long":
        return (exit_price - entry_price) * size
    else:
        return (entry_price - exit_price) * size


# ----------------- Backtest loop -----------------


def run_backtest(config: Dict):
    """
    Backtest entry point.

    Flow:
      1. Load OHLCV data.
      2. Add SMA indicators.
      3. Step through candles, calling strategy.generate_signal(df_slice, config).
      4. For 'market_entry' signals, simulate trades with SL/TP.
      5. Collect trades, compute metrics.
      6. Optionally launch the replay viewer with candles and trades.
    """
    logger.info("Backtest started.")
    logger.info(f"Config: {config}")

    symbol = config["symbol"]
    timeframe = config["timeframe"]
    lookback_bars = int(config["lookback_bars"])
    preview = bool(config.get("preview_replay", False))
    account_size = float(config["account_size"])
    risk_pct = float(config["risk_pct"])

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

    df = _add_indicators(df, config)

    trades: List[Trade] = []
    trades_for_view: List[Dict] = []
    balance = account_size

    # Start after 50 bars so SMAs are well defined
    i = 50

    while i < len(df) - 1:
        df_slice = df.iloc[: i + 1]

        signal = generate_signal(df_slice, config)
        if signal is None:
            i += 1
            continue

        signal_type = signal.get("signal_type", "")
        if signal_type != "market_entry":
            # We are not yet handling limit-bundle signals in the backtest.
            logger.info(
                f"Signal type '{signal_type}' not implemented in backtest yet. Skipping."
            )
            i += 1
            continue

        direction = signal["direction"]  # "long" or "short"
        entry_price = float(signal["entries"][0])
        stop_loss = float(signal["stop_loss"])
        take_profit = float(signal["take_profit"])

        # Position sizing
        try:
            size = compute_position_size(
                account_size=balance,
                risk_pct=risk_pct,
                entry_price=entry_price,
                stop_loss=stop_loss,
            )
        except ValueError as e:
            logger.warning(f"Skipping signal at index {i} due to sizing error: {e}")
            i += 1
            continue

        entry_idx = i
        exit_idx, exit_price = _simulate_trade(
            df=df,
            start_idx=entry_idx,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        pnl = _pnl_for_trade(
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
        )

        entry_time = df.index[entry_idx]
        exit_time = df.index[exit_idx]

        trade = Trade(
            id=f"trade_{len(trades) + 1}",
            symbol=symbol,
            direction=direction,
        )
        trade.opened_at = entry_time.to_pydatetime()
        trade.closed_at = exit_time.to_pydatetime()
        trade.entry_price_avg = entry_price
        trade.exit_price = exit_price
        trade.size_total = size
        trade.pnl_usd = pnl
        trade.status = TradeStatus.CLOSED
        trade.stop_loss = stop_loss
        trade.take_profit = take_profit

        trades.append(trade)
        balance += pnl

        logger.info(
            f"Closed trade {trade.id}: "
            f"direction={direction}, entry={entry_price:.2f}, exit={exit_price:.2f}, "
            f"size={size:.6f}, pnl={pnl:.2f}, new_balance={balance:.2f}"
        )

        trades_for_view.append(
            {
                "id": trade.id,
                "direction": direction,
                "entry_index": entry_idx,
                "exit_index": exit_idx,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            }
        )

        # Move index to the bar after exit
        i = exit_idx + 1

    # ------------- Metrics and optional replay -------------

    metrics = compute_metrics(trades, starting_balance=account_size)
    logger.info(f"Backtest metrics summary: {metrics}")

    print("\n=== Backtest Summary ===")
    for k, v in metrics.items():
        print(f"{k}: {v}")

    if preview:
        from backtest.replay_viewer import run_replay_viewer

        logger.info("Launching backtest replay viewer.")
        run_replay_viewer(
            df,
            symbol=symbol,
            timeframe=timeframe,
            trades=trades_for_view,
            strategy=config.get("strategy", "sma"),
        )
    logger.info("Backtest finished.")
