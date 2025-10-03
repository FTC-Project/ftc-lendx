#!/bin/bash
set -e
python manage.py migrate --noinput
exec uvicorn bot_backend.asgi:application \
  --host 0.0.0.0 --port 8000 \
  --lifespan off \
  --reload