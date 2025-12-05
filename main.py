import sys

from ui.cli import get_run_mode, get_user_config
from data.ohlcv_manager import OhlcvManager
from ui.chart import create_dash_app
from backtest.engine import run_backtest
from app_logging.event_logger import get_logger

logger = get_logger(__name__)


def run_live(config: dict):
    """
    Entry point for LIVE mode.
    For now this only prepares the OhlcvManager and Dash app.
    Later we will:
      - Hook up ccxt
      - Start a background loop to update candles
    """
    logger.info(f"Starting LIVE mode with config: {config}")

    # TODO: create real ccxt exchange here
    exchange = None

    ohlcv_manager = OhlcvManager(
        exchange=exchange,
        symbol=config["symbol"],
        timeframe=config["timeframe"],
        max_bars=config["lookback_bars"],
    )

    # At this stage, this is still a stub.
    # Later we will fetch real OHLCV here.
    ohlcv_manager.load_initial_history(limit=config["lookback_bars"])

    app = create_dash_app(ohlcv_manager=ohlcv_manager, live_mode=True)
    app.run_server(debug=True)


def run_backtest_mode(config: dict):
    """
    Entry point for BACKTEST mode.
    The actual logic lives in backtest.engine.run_backtest.
    """
    logger.info(f"Starting BACKTEST mode with config: {config}")
    run_backtest(config=config)


def main():
    """
    Main entry point.
    We no longer rely on argparse. The user chooses 'live' or 'backtest'
    through the CLI prompts.
    """
    mode = get_run_mode()
    config = get_user_config(live_mode=(mode == "live"))

    if mode == "live":
        run_live(config)
    else:
        run_backtest_mode(config)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt.")
        sys.exit(0)
