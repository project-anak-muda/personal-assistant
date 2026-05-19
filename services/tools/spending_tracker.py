import os

from datetime import datetime, date
from langchain_core.tools import tool
from typing import Optional, Dict, List
from utils.gsheet import append_row, read_all

from constants.config import SPENDING_SHEET


@tool
def log_spending(
    amount: float,
    category: str,
    description: str = "",
    currency: str = "IDR",
    spend_date: Optional[str] = None,
    note: str = "",
) -> str:
    """Record a personal spending entry into Google Sheet.

    Use this whenever the user mentions they spent money and wants it tracked.

    Args:
        amount: Amount spent (positive number).
        category: Spending category (e.g. "food", "transport", "entertainment").
        description: Short description of what was bought.
        currency: Currency code (default "IDR").
        spend_date: Date of spending in YYYY-MM-DD format. Defaults to today.
        note: Additional free-form note.

    Returns:
        Confirmation string.
    """
    if not spend_date:
        spend_date = date.today().isoformat()

    append_row(
        SPENDING_SHEET,
        [spend_date, category, description, amount, currency, note],
    )
    return (
        f"Logged: {currency} {amount:,.2f} on {spend_date} for "
        f"'{description or category}' ({category})."
    )

@tool
def summarize_spending(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict:
    """Summarize personal spending from the Google Sheet within a date range.

    Args:
        start_date: Inclusive start date (YYYY-MM-DD). If omitted, no lower bound.
        end_date: Inclusive end date (YYYY-MM-DD). If omitted, no upper bound.
        category: Optional category filter (case-insensitive exact match).

    Returns:
        Dict with total, count, breakdown by category, and matching entries.
    """
    records: List[dict] = read_all(SPENDING_SHEET)

    def in_range(r: dict) -> bool:
        d_str = str(r.get("date", "")).strip()
        if not d_str:
            return False
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            return False
        if start_date and d < datetime.strptime(start_date, "%Y-%m-%d").date():
            return False
        if end_date and d > datetime.strptime(end_date, "%Y-%m-%d").date():
            return False
        if category and str(r.get("category", "")).lower() != category.lower():
            return False
        return True

    filtered = [r for r in records if in_range(r)]
    total = 0.0
    by_category: Dict[str, float] = {}
    for r in filtered:
        try:
            amt = float(r.get("amount", 0) or 0)
        except (TypeError, ValueError):
            amt = 0.0
        total += amt
        cat = str(r.get("category", "uncategorized"))
        by_category[cat] = by_category.get(cat, 0.0) + amt

    return {
        "total": round(total, 2),
        "count": len(filtered),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "entries": filtered,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "category": category,
        },
    }