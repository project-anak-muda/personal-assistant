import os

from datetime import datetime
from langchain_core.tools import tool
from typing import Optional, Dict, List
from utils.gsheet import append_row, read_all

from constants.config import (
    SPENDING_SHEET, BUDGET_SHEET, 
    BUDGET_WARN_THRESHOLD, TIMEZONE
)


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
        spend_date = datetime.now(TIMEZONE).date().isoformat()

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

def _read_monthly_budget() -> float:
    """Read the monthly budget from the Budget worksheet.

    Expects a worksheet with a `monthly_budget` column. Uses the first
    non-empty value found. Returns 0.0 if not configured.
    """
    try:
        rows = read_all(BUDGET_SHEET)
    except Exception:
        return 0.0

    for r in rows:
        raw = r.get("monthly_budget") or r.get("budget") or r.get("amount")
        if raw in (None, ""):
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return 0.0

@tool
def check_budget(currency: str = "IDR") -> Dict:
    """Check whether this month's spending is still within the monthly budget.

    Sums all spending from the 1st of the current month up to today, compares
    it against the monthly budget (from the Budget worksheet), and flags an
    alert when usage reaches the warning threshold (default 80%) or exceeds 100%.

    Use this RIGHT AFTER logging a new spend, so the user is warned as soon as
    they get close to or over budget.

    Args:
        currency: Currency code for display (default "IDR").

    Returns:
        Dict with month_total, budget, percent_used, status
        ("ok" | "warning" | "over"), `alert` (bool), and a human-readable
        `summary` to surface in the final response.
    """
    today = datetime.now(TIMEZONE).date()
    month_start = today.replace(day=1)

    records: List[dict] = read_all(SPENDING_SHEET)
    month_total = 0.0
    for r in records:
        d_str = str(r.get("date", "")).strip()
        if not d_str:
            continue
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if month_start <= d <= today:
            try:
                month_total += float(r.get("amount", 0) or 0)
            except (TypeError, ValueError):
                continue

    budget = _read_monthly_budget()
    month_total = round(month_total, 2)

    if budget <= 0:
        return {
            "month": today.strftime("%Y-%m"),
            "month_total": month_total,
            "budget": 0,
            "percent_used": None,
            "status": "no_budget",
            "alert": False,
            "summary": (
                f"This month's spending so far: {currency} {month_total:,.2f}. "
                f"No monthly budget is set, so I can't check it."
            ),
        }

    percent = month_total / budget
    remaining = budget - month_total

    if percent >= 1.0:
        status = "over"
        alert = True
        emoji = "🚨"
        headline = f"{emoji} OVER BUDGET! You've used {percent*100:.0f}% of your monthly budget."
    elif percent >= BUDGET_WARN_THRESHOLD:
        status = "warning"
        alert = True
        emoji = "⚠️"
        headline = f"{emoji} Heads up: you've used {percent*100:.0f}% of your monthly budget."
    else:
        status = "ok"
        alert = False
        emoji = "✅"
        headline = f"{emoji} You're within budget ({percent*100:.0f}% used)."

    summary = (
        f"{headline}\n"
        f"Spent this month: {currency} {month_total:,.2f} / {currency} {budget:,.2f}\n"
        f"Remaining: {currency} {remaining:,.2f}"
    )

    return {
        "month": today.strftime("%Y-%m"),
        "month_total": month_total,
        "budget": round(budget, 2),
        "remaining": round(remaining, 2),
        "percent_used": round(percent * 100, 1),
        "status": status,
        "alert": alert,
        "summary": summary,
    }