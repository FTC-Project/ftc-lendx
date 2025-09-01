#!/usr/bin/env bash
set -e

# Migrate & run dev server inside container
python manage.py migrate --noinput
exec python manage.py runserver 0.0.0.0:8000 --settings=bot_backend.settings.docker
