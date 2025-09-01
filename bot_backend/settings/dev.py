from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

# For quick local dev without Docker: use SQLite if no DB env is set
if os.getenv("USE_SQLITE", "1") == "1":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
