import os
import gspread

from typing import List
from functools import lru_cache
from google.oauth2.service_account import Credentials

from constants.config import SCOPES


@lru_cache(maxsize=1)
def _client() -> gspread.Client:
    sa_path = os.getenv("GOOGLE_SA_PATH")
    if not sa_path:
        raise RuntimeError("GOOGLE_SA_PATH env var is not set")
    creds = Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    return gspread.authorize(creds)

def get_worksheet(worksheet_name: str) -> gspread.Worksheet:
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID env var is not set")

    sh = _client().open_by_key(sheet_id)
    try:
        return sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=10)
        ws.append_row(
            ["date", "category", "description", "amount", "currency", "note"],
            value_input_option="USER_ENTERED",
        )
        return ws

def append_row(worksheet_name: str, row: List) -> None:
    ws = get_worksheet(worksheet_name)
    ws.append_row(row, value_input_option="USER_ENTERED")

def read_all(worksheet_name: str) -> List[dict]:
    ws = get_worksheet(worksheet_name)
    return ws.get_all_records()