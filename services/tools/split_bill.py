from langchain_core.tools import tool
from typing import Dict, List, Optional

from constants.params import SplitItem


@tool
def split_bill(
    items: List[Dict],
    participants: List[str],
    tax_percent: float = 0.0,
    service_percent: float = 0.0,
    discount: float = 0.0,
    currency: str = "IDR",
) -> Dict:
    """Split a bill among participants based on per-item consumption.

    Each item is consumed by a subset of participants. Tax, service charge,
    and discount are distributed proportionally to each participant's
    subtotal.

    Args:
        items: List of items. Each item is a dict with keys:
            - name (str)
            - price (float)
            - shared_by (list[str]): names of participants who share this item
        participants: Full list of participant names included in the bill.
        tax_percent: Tax percent applied to the subtotal (e.g. 11 for 11%).
        service_percent: Service charge percent applied to the subtotal.
        discount: Flat discount amount applied to the subtotal (in currency unit).
        currency: Currency code, default "IDR".

    Returns:
        Dict with per-person breakdown, totals, and a human-readable summary.
    """
    parsed = [SplitItem(**i) for i in items]

    per_person_subtotal: Dict[str, float] = {p: 0.0 for p in participants}
    per_person_items: Dict[str, List[Dict]] = {p: [] for p in participants}
    for item in parsed:
        if not item.shared_by:
            continue
        share = item.price / len(item.shared_by)
        for p in item.shared_by:
            if p not in per_person_subtotal:
                per_person_subtotal[p] = 0.0
                per_person_items[p] = []
            per_person_subtotal[p] += share
            per_person_items[p].append({
                "name": item.name,
                "price": round(item.price, 2),
                "shared_with": len(item.shared_by),
                "your_share": round(share, 2),
            })

    subtotal = sum(per_person_subtotal.values())
    tax_amount = subtotal * (tax_percent / 100.0)
    service_amount = subtotal * (service_percent / 100.0)
    grand_total = subtotal + tax_amount + service_amount - discount

    per_person_total: Dict[str, float] = {}
    for p, sub in per_person_subtotal.items():
        ratio = (sub / subtotal) if subtotal > 0 else 0
        per_person_total[p] = round(
            sub + (tax_amount * ratio) + (service_amount * ratio) - (discount * ratio),
            2,
        )

    lines = [f"Bill split ({currency}):"]
    for p, total in per_person_total.items():
        lines.append(f"- {p}: {currency} {total:,.2f} (subtotal {per_person_subtotal[p]:,.2f})")
    lines.append(
        f"Subtotal: {currency} {subtotal:,.2f} | Tax: {tax_amount:,.2f} | "
        f"Service: {service_amount:,.2f} | Discount: {discount:,.2f} | "
        f"Grand total: {currency} {grand_total:,.2f}"
    )

    return {
        "currency": currency,
        "subtotal": round(subtotal, 2),
        "tax_amount": round(tax_amount, 2),
        "service_amount": round(service_amount, 2),
        "discount": round(discount, 2),
        "grand_total": round(grand_total, 2),
        "per_person_subtotal": {k: round(v, 2) for k, v in per_person_subtotal.items()},
        "per_person_total": per_person_total,
        "per_person_items": per_person_items,
        "summary": "\n".join(lines),
    }
