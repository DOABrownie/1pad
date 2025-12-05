from typing import Dict

from logging.event_logger import get_logger

logger = get_logger(__name__)


def run_backtest(config: Dict):
    """
    Backtest entry point.

    Later we will:
      - Load historical OHLCV
      - Step through candles, applying strategy logic
      - Optionally call a replay visual callback
      - Compute and log metrics at the end
    """
    logger.info(f"Backtest started with config: {config}")

    # TODO:
    # - Load historical OHLCV for config["symbol"], config["timeframe"]
    # - Initialize state (account balance, trades list, etc.)
    # - For each candle:
    #       * Update indicators (pivots, BOS, fibs)
    #       * Generate signals
    #       * Simulate orders and positions
    #       * If config["preview_replay"], store snapshots for replay
    # - Compute metrics and write report to logs/reports

    logger.info("Backtest finished (stub implementation).")
