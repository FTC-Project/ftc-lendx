#!/bin/sh
set -eu  # no 'pipefail' in /bin/sh

# Ensure we're in the app root
cd /app

# Run migrations (no prompt anyway, so no flag needed)
python manage.py migrate

# Collect static without prompting
python manage.py collectstatic --no-input

# Start Django (pick ONE, comment out the other)
# ASGI (Django 3.0+/5.x OK if you have asgi.py)
uvicorn backend.asgi:application --host 0.0.0.0 --port 8000
