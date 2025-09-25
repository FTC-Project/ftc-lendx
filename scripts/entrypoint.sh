#!/bin/bash
set -euo pipefail

exec uvicorn bot_backend.asgi:application \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-4}" \
  --lifespan off
