# Personal Assistant — Telegram Bot

A personal assistant Telegram bot powered by **LangChain + LangGraph** and **Gemini**, with three capabilities:

1. **Split bills** — from text or a photo of a receipt
2. **Track personal spending** — logged into a Google Sheet
3. **Blast split-bill messages** — per-person breakdowns ready to forward

The bot connects to Telegram via **long polling** (no public URL, no webhook, no ngrok required). A FastAPI HTTP layer is also available for testing or non-Telegram clients.

## Features

- Single LangGraph agent with multiple tools (`split_bill`, `log_spending`, `summarize_spending`, `blast_split_bill_message`).
- Multimodal input (text or receipt photos) via Gemini.
- Google Sheets as the datastore for **spending**, **bank info**, and the **username whitelist** — everything you'd want to edit without redeploying lives in the Sheet.
- Per-chat conversation memory (`thread_id=tg-<chat_id>`).
- Username whitelist (loaded from a Sheet) so only allowed Telegram users can talk to the bot.
- Asia/Jakarta datetime is injected into every request so the agent always knows "now".
- Docker support for one-command deploy.

## Project Structure

```text
personal_assistance/
├── telegram_bot.py            # Standalone long-polling Telegram bot (main entry)
├── main_client.py             # Optional FastAPI server (HTTP endpoints)
├── Dockerfile                 # Container build for the Telegram bot
├── requirements-bot.txt       # Slim deps for the bot-only deployment
├── requirements.txt           # Full deps (bot + FastAPI)
├── constants/
│   ├── config.py              # Worksheet names, SCOPES, TIMEZONE, POLL_TIMEOUT
│   ├── prompt.py              # Agent system prompt
│   └── ...
├── routers/single_agent.py    # FastAPI endpoints (optional)
├── services/
│   ├── agent_manager.py       # Builds the single LangGraph agent
│   ├── tools/                 # split_bill, log_spending, summarize_spending, blast
│   └── middlewares/
└── utils/
    ├── gsheet.py              # Google Sheets client (service account)
    └── helpers.py             # build_user_message + datetime prefix
```

## Prerequisites

- Python 3.13
- A **Telegram bot token** (free, via `@BotFather`)
- A **Gemini API key** (Google AI Studio — free tier available)
- A **Google Sheet** + **service account JSON** for spending tracking

## Setup

### 1. Create the Telegram bot

In Telegram, message `@BotFather`:

```
/newbot
<pick a name>
<pick a username ending in "bot">
```

Copy the token it gives you (looks like `123456:ABC-DEF_xxx`).

### 2. Prepare Google Sheets

1. Create a new Google Sheet, copy the **Sheet ID** from its URL.
2. In Google Cloud Console:
   - Create a project (or reuse one).
   - Enable the **Google Sheets API** and **Google Drive API**.
   - Create a **Service Account**, download its JSON key, save as `service_account.json` in the project root.
3. Open the Sheet → **Share** → paste the service account's email (ends in `@...iam.gserviceaccount.com`) → give it **Editor** access.

Inside that one Sheet the bot uses three worksheets (names are env-configurable — defaults shown below):

| Worksheet | Default name | Purpose | Columns |
|-----------|--------------|---------|---------|
| Spending | `Spending` | Auto-appended every time you log a spend | `date`, `category`, `description`, `amount`, `currency`, `note` |
| Bank info | `BankInfo` | Payment details inserted into every blast message | free-form rows (e.g. bank name, account number, name) |
| Whitelist | `WhitelistUsername` | Telegram usernames allowed to talk to the bot | column header **`users`** containing usernames (no `@`) |

The Spending sheet is auto-created with the right header on first write. The Bank-info and Whitelist sheets you create yourself — and you can edit them anytime without restarting the bot.

### 3. Configure `.env`

```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF_your_token_here

# Gemini
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL_NAME=gemini-2.0-flash-exp

# Google Sheets
GOOGLE_SHEET_ID=your-sheet-id
GOOGLE_SA_PATH=./service_account.json
SPENDING_WORKSHEET=Spending
BANK_INFO_WORKSHEET=BankInfo
WHITELIST_USERS_WORKSHEET=WhitelistUsername
```

All three worksheet names default to the values above if you omit the env var — only set them if you've renamed the tabs in your Sheet.

### 4. Install & run (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-bot.txt
python telegram_bot.py
```

Open Telegram, message your bot, and you're live.

## Running with Docker

```bash
# Build
docker build -t personal-assistant .

# Run (loads env from .env, mounts service account JSON)
docker run -d --name pa-bot \
  --restart unless-stopped \
  --env-file .env \
  -v "$PWD/service_account.json:/app/service_account.json:ro" \
  personal-assistant
```

Long polling means no exposed port — the bot reaches out to Telegram on its own.

```bash
# Tail logs
docker logs -f pa-bot

# Stop
docker stop pa-bot && docker rm pa-bot
```

## Example Conversations

**Logging a spend:**
> "Beli kopi 35rb di kantor"

The agent will call `log_spending(amount=35000, category="food", description="kopi", ...)` and confirm.

**Asking for a summary:**
> "Berapa total pengeluaranku minggu ini?"

The agent will call `summarize_spending` with the relevant date range and reply with a category breakdown.

**Splitting a bill from a photo:**
Send a photo of a receipt with a caption like:
> "Split sama Andi, Budi, Citra. Pajak 11%, service 5%."

The agent extracts items from the image, calls `split_bill`, then `blast_split_bill_message` (with per-item breakdowns), then `log_spending` for **only your share**.

## Optional: FastAPI Mode

If you also want HTTP endpoints (e.g. for a custom UI), use the full `requirements.txt` and run:

```bash
pip install -r requirements.txt
python main_client.py   # listens on :2707
```

Endpoints (see [routers/single_agent.py](routers/single_agent.py)):

- `POST /single-agent/generate-answer` — multipart form (`session_id`, `query`, optional `image` file or `image_base64`)
- `POST /single-agent/stream/generate-answer` — SSE streaming variant
- `POST /single-agent/continue-answer` — resume after a HITL interrupt

Example:

```python
import requests

requests.post(
    "http://localhost:2707/single-agent/generate-answer",
    data={
        "session_id": "test-1",
        "query": "Pengeluaran 322500 untuk biji kopi",
    },
).json()
```

## Troubleshooting

- **`Bad Request: chat not found`** — `sendMessage` needs the numeric `chat.id`, not `chat.username`. The bot uses `id` for sending and `username` only for the whitelist check.
- **`Maaf, Anda tidak diizinkan…`** — your Telegram username isn't in the `WhitelistUsername` worksheet. Open the Google Sheet, add a row with your username (no `@`) under the `users` column, and message the bot again — no restart needed. If you don't have a Telegram username, set one in Telegram settings first (the bot uses `chat.username` to authorize).
- **Google Sheets `403` / `PERMISSION_DENIED`** — you forgot to share the sheet with the service account email.
- **Webhook conflict** — long polling can't run while a webhook is registered. The bot auto-calls `deleteWebhook` on startup, but if you see `409 Conflict`, run it manually:
  ```bash
  curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"
  ```
- **Wrong "now" / timezone** — the datetime prefix is hardcoded to `Asia/Jakarta` in `utils/helpers.py`. Change `TIMEZONE` there if needed.
- **Container can't find timezone** — `tzdata` is already in `requirements-bot.txt`; reinstall if you switch base images.

## License

See [LICENSE](LICENSE).
