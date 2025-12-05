from typing import Dict

BINANCE_TIMEFRAMES = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
]


def get_run_mode() -> str:
    default = "backtest"
    prompt = f"Run mode [live/backtest] [{default}]: "

    while True:
        raw = input(prompt).strip().lower()
        if raw == "":
            return default
        if raw in ("live", "backtest"):
            return raw
        print("Please type 'live' or 'backtest'.")


def _prompt_timeframe(default: str = "4h") -> str:
    allowed_str = ", ".join(BINANCE_TIMEFRAMES)
    while True:
        raw = input(
            f"Timeframe (one of: {allowed_str}) [{default}]: "
        ).strip()
        if raw == "":
            return default
        candidate = raw.replace(" ", "")
        if candidate in BINANCE_TIMEFRAMES:
            return candidate
        print(
            f"'{raw}' is not a valid timeframe.\n"
            f"Please type one of: {allowed_str}\n"
        )


def _prompt_strategy(default: str = "sma") -> str:
    """
    Ask which strategy to use.

    For now we support:
      - 'sma'   : simple 10/50 SMA crossover test strategy
      - '1pad'  : real strategy (placeholder for now)

    Later we can add more names without changing callers.
    """
    valid = {"sma", "1pad"}
    prompt = f"Strategy [sma/1pad] [{default}]: "

    while True:
        raw = input(prompt).strip().lower()
        if raw == "":
            return default
        if raw in valid:
            return raw
        print("Please type 'sma' or '1pad'.")


def get_user_config(live_mode: bool = True) -> Dict:
    print("=== Trading Bot Configuration ===")

    default_symbol = "BTC/USDT"
    default_timeframe = "4h"
    default_account_size = 2000.0
    default_risk_pct = 2.0
    default_lookback = 1000
    default_num_orders = 5

    symbol = input(
        f"Symbol (e.g. BTC/USDT, XRP/USDT, ETH/USDT) [{default_symbol}]: "
    ).strip()
    if not symbol:
        symbol = default_symbol

    timeframe = _prompt_timeframe(default=default_timeframe)

    # 👇 NEW: strategy selection
    strategy = _prompt_strategy(default="sma")

    account_size_str = input(
        f"Account size in USD [{int(default_account_size)}]: "
    ).strip()
    account_size = (
        float(account_size_str) if account_size_str else default_account_size
    )

    risk_pct_str = input(
        f"Risk per trade in % [{int(default_risk_pct)}]: "
    ).strip()
    risk_pct = float(risk_pct_str) if risk_pct_str else default_risk_pct
    risk_pct /= 100.0

    lookback_str = input(
        f"Lookback bars (history candles to load) [{default_lookback}]: "
    ).strip()
    lookback_bars = int(lookback_str) if lookback_str else default_lookback

    num_orders_str = input(
        f"Number of limit orders per setup [{default_num_orders}]: "
    ).strip()
    num_limit_orders = (
        int(num_orders_str) if num_orders_str else default_num_orders
    )

    if live_mode:
        preview_replay = False
    else:
        preview_str = input("Preview backtest replay? [Y/n]: ").strip().lower()
        preview_replay = (preview_str != "n")

    config = {
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy": strategy,          # 👈 important
        "account_size": account_size,
        "risk_pct": risk_pct,
        "lookback_bars": lookback_bars,
        "num_limit_orders": num_limit_orders,
        "preview_replay": preview_replay,
    }

    return config
