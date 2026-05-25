from services.tools.split_bill import split_bill
from services.tools.blast_message import blast_split_bill_message
from services.tools.spending_tracker import log_spending, summarize_spending, check_budget


TOOLS = [
    split_bill,
    log_spending,
    summarize_spending,
    check_budget,
    blast_split_bill_message,
]