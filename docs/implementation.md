
## Implementation

### XRPL Service

The Django app `bot_backend.apps.users.xrpl_service` wraps the `xrpl-py` client in a small `XRPLClient` that is pre-configured for the XRPL TestNet RPC endpoint. A single global client instance exposes helpers such as `get_balance`, `send_xrp`, and `create_user_wallet`, which the rest of the codebase imports as simple functions. New wallets are generated and funded via the testnet faucet and returned as a `GeneratedWallet` dataclass, while supporting utilities like `get_transaction_history` and `wait_for_balance_update` make troubleshooting ledger interactions possible without adding async code to the request path.

### Telegram Bot

Incoming webhook payloads are normalised by `telegram_bot.messages.parse_telegram_message` into a `TelegramMessage` dataclass so the bot ignores anything that is not a slash-command. The `TelegramBot` class in `telegram_bot.bot` keeps the Bot API token, registers handlers from `telegram_bot.commands`, and sends replies through the Telegram REST API. Each command module sends a quick acknowledgement to the user and then hands the structured payload off to Celery so that the webhook can return immediately even when XRPL or CoinGecko calls are slow.

### Celery Workers

`telegram_bot/tasks.py` defines `shared_task`s on the `telegram_bot` queue; when a worker receives a payload it rebuilds the `TelegramMessage` and executes the command logic in the background. `/start` ensures there is a `TelegramUser` record, `/wallet` provisions an XRPL wallet via `create_user_wallet`, and `/balance` fetches live balances with `xrpl_service.get_balance`. `/send` persists a `Transfer` row, decrypts the stored seed with `decrypt_secret`, submits the payment through `send_xrp`, and updates the record with the resulting transaction hash and status. `/prices` calls `bot_backend.apps.botutils.price_history.fetch_price_history`, captures any API failures, and formats a concise, Telegram-friendly report before sending it back through the bot.

### Database

Postgres is the primary datastore (see `bot_backend/settings/base.py`), and migrations are executed automatically by the container entrypoint. The `TelegramUser`, `Wallet`, and `Transfer` models in `bot_backend.apps.users.models` capture Telegram identities, XRPL addresses, and transaction history so that transfers can be reconciled after the fact. Wallet secrets are encrypted with `cryptography.Fernet` (`bot_backend.apps.users.crypto`) using the `FERNET_KEY` environment variable before they are stored, and the Celery tasks rely on these models to validate state (for example, refusing to send if either party lacks an active wallet).

### Redis

Redis provides the Celery broker and result backend, which keeps webhook responses lightweight and allows the worker pool to absorb coin price lookups or XRPL submissions without blocking Django. The default configuration points to `redis://redis:6379/0`, and the development compose file provisions a matching Redis 7 instance.

### Docker

The deployment image is described in `deploy/Dockerfile`, which installs Python 3.12 dependencies, creates a non-root user, and delegates start-up to `scripts/entrypoint.sh`. `compose/docker-compose.dev.yml` wires together the web service (Django + Uvicorn), a dedicated Celery worker, Postgres 16, and Redis, all sharing the same workspace via bind mounts and `.env` files so code and settings stay in sync across processes.

### Deployment

At runtime the entrypoint script applies migrations, collects static assets, optionally runs `manage.py set_webhook` to register the Telegram webhook, and then launches Uvicorn. The webhook view at `telegram_bot/webhook.telegram_webhook` validates incoming POSTs, schedules the corresponding task, and always returns a JSON acknowledgement so Telegram will not retry unnecessarily. A lightweight `health_check` endpoint exposes the bot token status and API base URL to support load balancers or uptime checks. We deploy to Render.com, which provides free TLS termination and a stable public URL for the webhook.

