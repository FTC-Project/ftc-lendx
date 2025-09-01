# FSE XRPL Bot

A Django-based backend application with Telegram bot integration for XRPL (XRP Ledger) functionality.

## 🏗️ Project Structure

```
fse-xrpl-bot/
├── bot_backend/           # Django backend application
│   ├── apps/             # Django apps
│   │   └── users/        # User management app
│   ├── settings/         # Django settings (base, dev, prod)
│   └── ...
├── telegram_bot/         # Telegram bot implementation
├── compose/              # Docker compose configurations
├── deploy/               # Deployment files (Dockerfile, etc.)
├── requirements/         # Python dependencies
│   ├── base.txt         # Core dependencies
│   ├── dev.txt          # Development dependencies
│   └── prod.txt         # Production dependencies
├── scripts/              # Utility scripts
└── tests/               # Test files
```

## 🚀 Quick Start

### Prerequisites

You need one of the following setups:

**Option 1: Docker (Recommended)**
- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

**Option 2: Local Development**
- Python 3.11+ or Conda/Miniconda
- PostgreSQL 16

### 🐳 Running with Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/marclevin/fse-xrpl-bot.git
   cd fse-xrpl-bot
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` file and configure:
   - `DJANGO_SECRET_KEY`: Generate a secure secret key
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token, will get this later.
   - Other settings as needed

3. **Build and run with Docker Compose**
   ```bash
   # For development
   docker-compose -f compose/docker-compose.dev.yml up --build

   # For production
   docker-compose -f compose/docker-compose.prod.yml up --build
   ```

4. **Access the application**
   - Django backend: http://localhost:8000
   - PostgreSQL: localhost:5432 (dev mode only)

### 🐍 Local Development Setup

#### Using Conda (Recommended for local development)

1. **Create and activate conda environment**
   ```bash
   conda create -n fse-xrpl-bot python=3.11 -y
   conda activate fse-xrpl-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements/dev.txt
   ```

#### Using Virtual Environment

1. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements/dev.txt
   ```

#### Database Setup for Local Development

1. **Install and start PostgreSQL**
   - Follow [PostgreSQL installation guide](https://www.postgresql.org/download/)

2. **Create database and user**
   ```sql
   CREATE DATABASE fse_db;
   CREATE USER fse_user WITH PASSWORD 'fse_password';
   GRANT ALL PRIVILEGES ON DATABASE fse_db TO fse_user;
   ```

3. **Run Django migrations**
   ```bash
   python manage.py migrate
   ```

4. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

5. **Run development server**
   ```bash
   python manage.py runserver
   ```

## 🔧 Configuration

### Environment Variables

Key environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_SETTINGS_MODULE` | Django settings module | `bot_backend.settings.dev` |
| `DJANGO_SECRET_KEY` | Django secret key | `change-me` |
| `ALLOWED_HOSTS` | Allowed hosts for Django | `localhost,127.0.0.1` |
| `DB_HOST` | Database host | `localhost` |
| `DB_PORT` | Database port | `5432` |
| `DB_NAME` | Database name | `fse_db` |
| `DB_USER` | Database user | `fse_user` |
| `DB_PASSWORD` | Database password | `fse_password` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | `xxx` |

### Django Settings

The project uses multiple settings files:
- `base.py`: Common settings
- `dev.py`: Development settings
- `prod.py`: Production settings

## 🤖 Telegram Bot Setup

1. **Create a Telegram Bot**
   - Message @BotFather on Telegram
   - Use `/newbot` command
   - Follow instructions to get your bot token

2. **Configure the bot token**
   - Add your token to `.env` file: `TELEGRAM_BOT_TOKEN=your_token_here`

3. **Start the bot**
   - The bot will start automatically with the Django application
   - Check `telegram_bot/` directory for bot implementation

## 📊 Database Management

### Migrations

```bash
# Create new migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

### Database Access

**Using Docker:**
```bash
docker-compose -f compose/docker-compose.dev.yml exec db psql -U fse_user -d fse_db
```

**Local PostgreSQL:**
```bash
psql -h localhost -U fse_user -d fse_db
```

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test bot_backend.apps.users

# Run with coverage (if installed)
coverage run manage.py test
coverage report
```

## 📚 API Documentation

- Django Admin: http://localhost:8000/admin/
- API endpoints will be available at http://localhost:8000/api/


## Logs

**Docker logs:**
```bash
# All services
docker-compose -f compose/docker-compose.dev.yml logs

# Specific service
docker-compose -f compose/docker-compose.dev.yml logs web
```

## 📄 License

Will figure out later.
