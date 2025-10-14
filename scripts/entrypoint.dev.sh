#!/bin/sh
set -eu  # no 'pipefail' in /bin/sh

# Ensure we're in the app root
cd /app

# Run migrations (no prompt anyway, so no flag needed)
python manage.py migrate

# Collect static without prompting
python manage.py collectstatic --no-input

# Bind the webhook if $PUBLIC_URL is set
if [ -n "${PUBLIC_URL:-}" ]; then
    if ! output=$(python manage.py set_webhook 2>&1); then
        echo "Error: Failed to bind webhook with 'python manage.py set_webhook'."
        echo "Output:"
        echo "$output"
        exit 1
    fi
fi

# ASGI (Django 3.0+/5.x OK if you have asgi.py)
uvicorn backend.asgi:application --host 0.0.0.0 --port 8000 --lifespan off --reload
