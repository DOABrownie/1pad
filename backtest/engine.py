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
trades_logger = get_logger("trades", filename="trades.log")


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
    Fetch OHLCV candles and build a DataFrame.

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
    Add technical indicators based on the strategy config.
    Currently supports a simple SMA crossover config.
    """
    strategy = config.get("strategy", "sma").lower()

    if strategy == "sma":
        fast = int(config.get("sma_fast", 10))
        slow = int(config.get("sma_slow", 50))

        df["sma_fast"] = df["close"].rolling(window=fast).mean()
        df["sma_slow"] = df["close"].rolling(window=slow).mean()

        logger.info(f"Added SMA indicators: fast={fast}, slow={slow}")
    else:
        logger.warning(f"Unknown strategy '{strategy}', no indicators added.")

    return df


# ----------------- Trade simulation -----------------


def _simulate_trade(
    df: pd.DataFrame,
    entry_index: int,
    direction: str,
    take_profit: float,
    stop_loss: float,
) -> Tuple[int, float]:
    """
    Walk forward through df starting at entry_index + 1 until
    either the TP or SL is hit. Return (exit_index, exit_price).
    """
    prices = df["close"].values

    if direction == "long":
        for i in range(entry_index + 1, len(df)):
            high = df["high"].iloc[i]
            low = df["low"].iloc[i]

            if high >= take_profit:
                return i, take_profit
            if low <= stop_loss:
                return i, stop_loss

        return len(df) - 1, prices[-1]

    elif direction == "short":
        for i in range(entry_index + 1, len(df)):
            high = df["high"].iloc[i]
            low = df["low"].iloc[i]

            if low <= take_profit:
                return i, take_profit
            if high >= stop_loss:
                return i, stop_loss

        return len(df) - 1, prices[-1]

    else:
        raise ValueError(f"Unknown trade direction '{direction}'")


# ----------------- Backtest loop -----------------


def run_backtest(config: Dict, preview: bool = True) -> None:
    """
    Run a simple bar-by-bar backtest loop based on the config dict.
    """
    symbol = config["symbol"]
    timeframe = config["timeframe"]
    lookback_bars = int(config["lookback_bars"])
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

        direction = signal["direction"]
        entry_idx = i
        entry_time = df.index[entry_idx]
        entry_price = df["close"].iloc[entry_idx]

        if direction == "long":
            stop_loss = signal["stop_loss"]
            take_profit = signal["take_profit"]
        elif direction == "short":
            stop_loss = signal["stop_loss"]
            take_profit = signal["take_profit"]
        else:
            logger.warning(f"Unknown direction from signal: {direction}")
            i += 1
            continue

        logger.info(
            f"Signal at index {i}: direction={direction}, "
            f"entry_price={entry_price:.2f}, tp={take_profit:.2f}, sl={stop_loss:.2f}"
        )

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
            entry_index=entry_idx,
            direction=direction,
            take_profit=take_profit,
            stop_loss=stop_loss,
        )

        exit_time = df.index[exit_idx]

        if direction == "long":
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

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

        trades_logger.info(
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
                "take_profit": take_profit,
                "stop_loss": stop_loss,
            }
        )

        i = exit_idx + 1

    metrics = compute_metrics(trades, starting_balance=account_size)

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
            metrics=metrics,
        )
    logger.info("Backtest finished.")
