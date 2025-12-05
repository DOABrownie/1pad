import argparse

from ui.cli import get_user_config
from data.ohlcv_manager import OhlcvManager
from ui.chart import create_dash_app
from backtest.engine import run_backtest
from logging.event_logger import get_logger

logger = get_logger(__name__)


def run_live():
    config = get_user_config(live_mode=True)
    logger.info(f"Starting LIVE mode with config: {config}")

    # TODO: initialize real ccxt exchange here
    exchange = None  # placeholder for ccxt exchange object

    ohlcv_manager = OhlcvManager(
        exchange=exchange,
        symbol=config["symbol"],
        timeframe=config["timeframe"],
        max_bars=config["lookback_bars"]
    )

    # Fetch initial history
    ohlcv_manager.load_initial_history(limit=config["lookback_bars"])

    # Create Dash app for interactive charting
    app = create_dash_app(ohlcv_manager=ohlcv_manager, live_mode=True)

    # NOTE:
    # In a later step we will start:
    # - a background thread / async task that updates ohlcv_manager with live data
    # - the Dash server to show the chart
    app.run_server(debug=True)


def run_backtest_mode():
    config = get_user_config(live_mode=False)
    logger.info(f"Starting BACKTEST mode with config: {config}")

    # In a later step, we will:
    # - Load historical OHLCV data via OhlcvManager or a dedicated loader
    # - Run run_backtest(...) and optionally initiate replay visualization
    run_backtest(config=config)


def parse_args():
    parser = argparse.ArgumentParser(description="Crypto trading bot")
    parser.add_argument(
        "--mode",
        choices=["live", "backtest"],
        default="live",
        help="Run in live trading mode or backtest mode."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.mode == "live":
        run_live()
    else:
        run_backtest_mode()
