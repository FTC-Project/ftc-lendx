from .base import *
DEBUG = True
ALLOWED_HOSTS = ["*"]
# In docker-compose we’ll set DB_HOST=db, so base.py’s Postgres config just works.
