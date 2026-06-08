import os
import json

from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Dict, List


def parse_value(value: str) -> Any:
    """Try to parse string into Python type (int, float, bool, list, dict)."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value
    
def split_string(value: str, delimiter: str = ",") -> List[str]:
    """Split a string by delimiter into a list."""
    return [item.strip() for item in value.split(delimiter) if item.strip()]

def all_env_variables(prefix: str = None) -> Dict[str, Any]:
    """
    Get all environment variables. 
    If prefix is provided, filter by it and strip the prefix from keys.
    """
    env_dict = dict(os.environ)
    if prefix:
        env_dict = {
            k[len(prefix):]: v  # strip prefix from key
            for k, v in env_dict.items()
            if k.startswith(prefix)
        }
    
    return {k: parse_value(v) for k, v in env_dict.items()}

PATH = (Path(__file__)).resolve()
PATH = '/'.join(str(PATH).split('/')[:-2])

TIMEZONE = ZoneInfo("Asia/Jakarta")

MIDDLEWARE_LIST_TOOLS = {}

USED_MIDDLEWARE = [
    'tool_call_limit',
    'hitl',
    'handle_empty_response',
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPENDING_SHEET = os.getenv("SPENDING_WORKSHEET", "Spending")
BANK_INFO_SHEET = os.getenv("BANK_INFO_WORKSHEET", "BankInfo")
WHITELIST_USERS_SHEET = os.getenv("WHITELIST_USERS_WORKSHEET", "WhitelistUsername")
BUDGET_SHEET = os.getenv("BUDGET_WORKSHEET", "Budget")

# Alert thresholds (as fractions of the monthly budget)
BUDGET_WARN_THRESHOLD = float(os.getenv("BUDGET_WARN_THRESHOLD", "0.8"))

POLL_TIMEOUT = 300