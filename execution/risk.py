from typing import List


def compute_equal_sized_orders(
    entries: List[float],
    stop_loss: float,
    account_size: float,
    risk_pct: float,
) -> List[float]:
    """
    Compute equal-sized order quantities so that if ALL entries are filled
    and price hits stop_loss, the total loss equals account_size * risk_pct.

    Assumes:
      - Long positions when entries > stop_loss
      - Short positions when entries < stop_loss

    Returns:
      A list of sizes, one per entry, all equal.
    """
    if not entries:
        raise ValueError("No entry prices provided.")

    risk_amount = account_size * risk_pct
    if risk_amount <= 0:
        raise ValueError("Risk amount must be positive.")

    diffs = [abs(e - stop_loss) for e in entries]
    denom = sum(diffs)

    if denom == 0:
        raise ValueError("Stop loss equals all entry prices, cannot size positions.")

    per_order_size = risk_amount / denom
    sizes = [per_order_size for _ in entries]
    return sizes
