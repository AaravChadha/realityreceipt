"""How a new item is paid for (PLAN.md row A3).

Each function returns the cash flow of paying the price by one method. Only
`cash` knows where the price came from, so only it carries the `purchase` line.
"""

from app.models import MONTHS, Contribution, CostLine

USER_SOURCE_IDS = {"user", "user_listing", "user_lease"}


def cash(price: float, source_id: str) -> Contribution:
    """The whole price in month 0: paid in full today."""
    price = round(price, 2)
    monthly = [0.0] * MONTHS
    monthly[0] = price
    line = CostLine(
        kind="purchase",
        label="Price today",
        amount_low=price,
        amount_high=price,
        period="once",
        source_type="user_entered" if source_id in USER_SOURCE_IDS else "published",
        source_id=source_id,
        formula=f"${price:,.2f} paid in full today",
    )
    return Contribution(pay_today=price, monthly_low=monthly, monthly_high=list(monthly), lines=[line])
