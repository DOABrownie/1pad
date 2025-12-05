from logging.event_logger import get_logger

logger = get_logger(__name__)


class DiscordNotifier:
    """
    Wrapper around your existing Discord notification logic.

    You can plug in webhook URL or bot token here.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        # TODO: add webhook URL or other credentials here

    def _send(self, message: str):
        if not self.enabled:
            return
        # TODO: implement actual HTTP request to Discord webhook.
        logger.info(f"[DISCORD] {message}")

    def notify_trade_opened(self, trade_info: dict):
        msg = f"Trade opened: {trade_info}"
        self._send(msg)

    def notify_trade_closed(self, trade_info: dict):
        msg = f"Trade closed: {trade_info}"
        self._send(msg)

    def notify_backtest_finished(self, summary: dict):
        msg = f"Backtest finished: {summary}"
        self._send(msg)
