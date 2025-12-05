from typing import Dict, List


def compute_fib_levels(
    swing_low: float,
    swing_high: float,
    direction: str = "long",
    levels: List[float] = None,
) -> Dict[str, float]:
    """
    Compute Fibonacci retracement levels for a given price swing.

    direction:
      - "long": expecting retracement down from swing_high towards swing_low
      - "short": expecting retracement up from swing_low towards swing_high

    Returns a dict like:
      {
        "0.236": price,
        "0.382": price,
        ...
      }
    """
    if levels is None:
        levels = [0.236, 0.382, 0.5, 0.618, 0.786]

    fibs = {}
    delta = swing_high - swing_low

    if direction == "long":
        for lvl in levels:
            price = swing_high - delta * lvl
            fibs[str(lvl)] = price
    else:
        # direction == "short"
        for lvl in levels:
            price = swing_low + delta * lvl
            fibs[str(lvl)] = price

    return fibs
