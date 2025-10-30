import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Load .env file if present

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "dev-insecure-bot-token")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes"}
raw_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]
FERNET_KEY = os.getenv("FERNET_KEY", "dev-insecure-fernet-key-1234567890123456")


# raw_csrf = os.getenv("CSRF_TRUSTED_ORIGINS", "")
# CSRF_TRUSTED_ORIGINS = [o.strip() for o in raw_csrf.split(",") if o.strip()]


SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    # Django Admin Deps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Our apps and 3rd party
    "rest_framework",
    "backend.apps.users.apps.UsersConfig",
    "backend.apps.kyc.apps.KycConfig",
    "backend.apps.banking.apps.BankingConfig",
    "backend.apps.scoring.apps.ScoringConfig",
    "backend.apps.tokens.apps.TokensConfig",
    "backend.apps.loans.apps.LoansConfig",
    "backend.apps.pool.apps.PoolConfig",
    "backend.apps.audit.apps.AuditConfig",
    "backend.apps.telegram_bot.apps.TelegramBotConfig",
    "backend.apps.botutils.apps.BotutilsConfig",
    "backend.apps.sys_frontend.apps.SysFrontendConfig", # frontend lender page
    "whitenoise.runserver_nostatic",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "backend.wsgi.application"

# Postgres by default; override with docker/dev settings as needed
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "NAME": os.getenv("DB_NAME", "fse_db"),
        "USER": os.getenv("DB_USER", "fse_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", "fse_password"),
    }
}

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_URL)
    DATABASES["default"].update(
        {
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": parsed.port or "5432",
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
        }
    )

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Johannesburg"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Bot settings (will move to env later)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Celery configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "telegram_bot")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "60"))

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Load .env file if present

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "dev-insecure-bot-token")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes"}
raw_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]
FERNET_KEY = os.getenv("FERNET_KEY", "dev-insecure-fernet-key-1234567890123456")


# raw_csrf = os.getenv("CSRF_TRUSTED_ORIGINS", "")
# CSRF_TRUSTED_ORIGINS = [o.strip() for o in raw_csrf.split(",") if o.strip()]


SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    # Django Admin Deps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Our apps and 3rd party
    "rest_framework",
    "backend.apps.users.apps.UsersConfig",
    "backend.apps.kyc.apps.KycConfig",
    "backend.apps.banking.apps.BankingConfig",
    "backend.apps.scoring.apps.ScoringConfig",
    "backend.apps.tokens.apps.TokensConfig",
    "backend.apps.loans.apps.LoansConfig",
    "backend.apps.pool.apps.PoolConfig",
    "backend.apps.audit.apps.AuditConfig",
    "backend.apps.telegram_bot.apps.TelegramBotConfig",
    "backend.apps.botutils.apps.BotutilsConfig",
    "whitenoise.runserver_nostatic",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "backend.wsgi.application"

# Postgres by default; override with docker/dev settings as needed
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "NAME": os.getenv("DB_NAME", "fse_db"),
        "USER": os.getenv("DB_USER", "fse_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", "fse_password"),
    }
}

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_URL)
    DATABASES["default"].update(
        {
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": parsed.port or "5432",
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
        }
    )

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Johannesburg"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Bot settings (will move to env later)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Celery configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "telegram_bot")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "60"))

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ==============================================================================
# Web3 / Blockchain Configuration
# ==============================================================================

# Web3 Provider URL
# For local Hardhat: http://127.0.0.1:8545
# For XRPL EVM Testnet: https://rpc-evm-sidechain.xrpl.org
WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "http://127.0.0.1:8545")

# Admin wallet (for contract write operations)
ADMIN_ADDRESS = os.getenv("ADMIN_ADDRESS", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
ADMIN_PRIVATE_KEY = os.getenv(
    "ADMIN_PRIVATE_KEY",
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
)

# Burn wallet (for off-ramped tokens - in production this would be an exchange wallet)
# Using Hardhat test account #1 as the burn wallet by default
BURN_WALLET_ADDRESS = os.getenv(
    "BURN_WALLET_ADDRESS", "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
)

# Contract Addresses
FTCTOKEN_ADDRESS = os.getenv("FTCTOKEN_ADDRESS", "")
CREDITTRUST_ADDRESS = os.getenv("CREDITTRUST_ADDRESS", "")
LOANSYSTEM_ADDRESS = os.getenv("LOANSYSTEM_ADDRESS", "")

# ABI Paths
FTCTOKEN_ABI_PATH = BASE_DIR / "backend" / "onchain" / "abi" / "FTCToken.json"
CREDITTRUST_ABI_PATH = (
    BASE_DIR / "backend" / "onchain" / "abi" / "CreditTrustToken.json"
)
LOANSYSTEM_ABI_PATH = BASE_DIR / "backend" / "onchain" / "abi" / "LoanSystemMVP.json"

# Legacy settings for backward compatibility
WEB3_PROVIDER = WEB3_PROVIDER_URL
CREDIT_TRUST_TOKEN_ADDRESS = CREDITTRUST_ADDRESS
try:
    import json

    if CREDITTRUST_ABI_PATH.exists():
        with open(CREDITTRUST_ABI_PATH, "r") as f:
            CREDIT_TRUST_TOKEN_ABI = json.load(f)
    else:
        CREDIT_TRUST_TOKEN_ABI = []
except:
    CREDIT_TRUST_TOKEN_ABI = []
