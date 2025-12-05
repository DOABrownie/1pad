def get_user_config(live_mode: bool = True) -> dict:
    """
    Collects user configuration from the command line.
    Later we can add support for reading from a config file.
    """
    print("=== Trading Bot Configuration ===")
    symbol = input("Symbol (e.g. BTC/USDT, XRP/USDT, ETH/USDT): ").strip() or "BTC/USDT"
    timeframe = input("Timeframe (e.g. 5m, 30m, 4h): ").strip() or "5m"

    account_size = float(input("Account size in USD (e.g. 2000): ").strip() or "2000")
    risk_pct = float(input("Risk per trade in % (e.g. 2): ").strip() or "2")
    risk_pct /= 100.0

    lookback_bars = int(input("Lookback bars (e.g. 1000): ").strip() or "1000")

    num_limit_orders = int(
        input("Number of limit orders per setup (e.g. 3): ").strip() or "3"
    )

    if not live_mode:
        print("Backtest options:")
        preview_str = input("Preview backtest replay? [y/N]: ").strip().lower()
        preview_replay = preview_str == "y"
    else:
        preview_replay = False

    config = {
        "symbol": symbol,
        "timeframe": timeframe,
        "account_size": account_size,
        "risk_pct": risk_pct,
        "lookback_bars": lookback_bars,
        "num_limit_orders": num_limit_orders,
        "preview_replay": preview_replay,
    }

    return config
