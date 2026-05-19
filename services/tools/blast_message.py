import urllib.parse

from langchain_core.tools import tool
from typing import Dict, List, Optional

from utils.gsheet import read_all
from constants.config import BANK_INFO_SHEET


@tool
def blast_split_bill_message(
    per_person_total: Dict[str, float],
    payer_name: str,
    currency: str = "IDR",
    event_name: str = "our hangout",
    contacts: Optional[Dict[str, str]] = None,
    per_person_items: Optional[Dict[str, List[Dict]]] = None,
    per_person_subtotal: Optional[Dict[str, float]] = None,
    grand_total: Optional[float] = None,
    tax_amount: Optional[float] = None,
    service_amount: Optional[float] = None,
    discount: Optional[float] = None,
) -> Dict:
    """Generate per-person blast messages for a split bill, with optional WhatsApp links.

    Call this AFTER `split_bill` to produce a message that can be sent to each
    participant asking them to pay their share. Pass the relevant fields from
    the `split_bill` result so the message can include item-level detail and
    overall totals.

    Args:
        per_person_total: Mapping of participant name -> amount they owe.
        payer_name: The name of the person who paid the bill upfront.
        currency: Currency code, default "IDR".
        event_name: Short description of the event (e.g. "dinner at X").
        contacts: Optional mapping of participant name -> phone number in
            international format (e.g. "+628123456789"). When provided, a
            WhatsApp wa.me deep link is generated for each contact.
        per_person_items: Optional mapping name -> list of items
            ({name, price, shared_with, your_share}) — from `split_bill`.
        per_person_subtotal: Optional mapping name -> subtotal (pre tax/service).
        grand_total: Optional grand total of the whole bill.
        tax_amount: Optional tax amount of the whole bill.
        service_amount: Optional service-charge amount of the whole bill.
        discount: Optional discount amount applied to the whole bill.

    Returns:
        Dict with `messages` (list of per-person message + optional wa.me link)
        and a combined `summary`.
    """
    contacts = contacts or {}
    per_person_items = per_person_items or {}
    per_person_subtotal = per_person_subtotal or {}
    messages: List[Dict] = []
    
    bank_info = read_all(BANK_INFO_SHEET)
    bank_info = [f"{i.get('Bank')}\na.n {i.get('Atas Nama')}\n{i.get('Nomor Rekening')}" 
                 for i in bank_info if i.get('Bank') and i.get('Atas Nama') and i.get('Nomor Rekening')]
    bank_info = "\n\n".join(bank_info)

    bill_total_parts: List[str] = []
    if grand_total is not None:
        bill_total_parts.append(f"Total bill: {currency} {grand_total:,.2f}")
    if tax_amount:
        bill_total_parts.append(f"tax {currency} {tax_amount:,.2f}")
    if service_amount:
        bill_total_parts.append(f"service {currency} {service_amount:,.2f}")
    if discount:
        bill_total_parts.append(f"discount {currency} {discount:,.2f}")
    bill_total_line = " | ".join(bill_total_parts) if bill_total_parts else ""

    for name, amount in per_person_total.items():
        if name == payer_name:
            continue

        detail_lines: List[str] = []
        items = per_person_items.get(name) or []
        if items:
            detail_lines.append("Your items:")
            for it in items:
                shared = it.get("shared_with", 1)
                share_note = f" (split by {shared})" if shared and shared > 1 else ""
                detail_lines.append(
                    f"  • {it['name']} — {currency} {it['your_share']:,.2f}{share_note}"
                )

        sub = per_person_subtotal.get(name)
        if sub is not None:
            detail_lines.append(f"Subtotal: {currency} {sub:,.2f}")
        detail_lines.append(f"Your total (incl. tax/service): {currency} {amount:,.2f}")
        if bill_total_line:
            detail_lines.append(bill_total_line)

        details = "\n".join(detail_lines)
        text = (
            f"Hi {name}! 🤚\n"
            f"Here's your share for {event_name}:\n"
            f"{details}\n"
            f"Please send it to:\n{bank_info}\n"
            f"Thanks!"
        )
        entry = {"name": name, "amount": round(amount, 2), "message": text}
        phone = contacts.get(name)
        if phone:
            clean = phone.lstrip("+").replace(" ", "").replace("-", "")
            entry["whatsapp_url"] = (
                f"https://wa.me/{clean}?text={urllib.parse.quote(text)}"
            )
        messages.append(entry)

    summary_lines = [f"Blast messages for {event_name} ({len(messages)} people):"]
    for m in messages:
        line = f"- {m['name']} owes {currency} {m['amount']:,.2f}"
        if "whatsapp_url" in m:
            line += f"  → {m['whatsapp_url']}"
        summary_lines.append(line)

    return {
        "messages": messages,
        "summary": "\n".join(summary_lines),
    }