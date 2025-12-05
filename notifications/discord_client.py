from app_logging.event_logger import get_logger

logger = get_logger(__name__)


class DiscordNotifier:
    """
    Wrapper around your existing Discord notification logic.
    Right now this just logs messages. You can plug in real webhook calls later.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        # TODO: add webhook URL or bot token here

    def _send(self, message: str):
        if not self.enabled:
            return
        # TODO: replace this with a real HTTP POST to Discord webhook.
        logger.info(f"[DISCORD] {message}")

    def notify_trade_opened(self, trade_info: dict):
        self._send(f"Trade opened: {trade_info}")

    def notify_trade_closed(self, trade_info: dict):
        self._send(f"Trade closed: {trade_info}")

    def notify_backtest_finished(self, summary: dict):
        self._send(f"Backtest finished: {summary}")
