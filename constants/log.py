import logging

from logging.config import fileConfig


fileConfig("log.ini", disable_existing_loggers=False)
LOGGER = logging.getLogger('uvicorn.error')
LOGGER.setLevel(logging.DEBUG)

# httpx logs every request URL at INFO. The Telegram bot token lives *inside*
# the URL (api.telegram.org/bot<TOKEN>/sendMessage), so leaving this on writes
# the token into Cloud Logging on every reply, where anyone with log-read
# access can lift it. WARNING still surfaces genuine transport failures.
logging.getLogger("httpx").setLevel(logging.WARNING)