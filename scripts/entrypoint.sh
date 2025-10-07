#!/bin/bash
set -euo pipefail


echo "[entrypoint] Running database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput

if [ -n "${PUBLIC_URL}" ]; then
  echo "[entrypoint] Setting Telegram webhook to ${PUBLIC_URL}/webhook/telegram/..."
  python manage.py set_webhook || echo "[entrypoint] Warning: failed to set webhook"
else
  echo "[entrypoint] Skipping webhook setup (PUBLIC_URL not set)"
fi


if [ "${CREATE_DUMMY_USER:-false}" = "true" ]; then
  echo "[entrypoint] Creating dummy user..."
  python manage.py create_dummy_user || echo "[entrypoint] Failed to create dummy user (maybe exists)"
fi

exec uvicorn backend.asgi:application \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-4}" \
  --lifespan off
  # Make sure hot reload ON for dev
