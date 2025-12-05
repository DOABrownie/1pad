from datetime import datetime, timezone


def now_utc() -> datetime:
    """
    Returns current UTC datetime.
    """
    return datetime.now(timezone.utc)
