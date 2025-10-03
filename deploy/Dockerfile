# deploy/Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ---- system deps (root) ----
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# ---- create non-root runtime user ----
# (system user 'app' in group 'app')
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# ---- install deps (still root) ----
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r /tmp/requirements.txt


 # Pre-create staticfiles dir and make it writable
RUN mkdir -p /app/staticfiles && chmod 777 /app/staticfiles

# ---- copy code and set ownership for runtime user ----
COPY --chown=app:app . /app

# Drop privileges for runtime
USER app

# In case the repo bind-mount removes +x, we invoke via bash (no +x needed)
CMD ["bash", "/app/scripts/entrypoint.dev.sh"]
