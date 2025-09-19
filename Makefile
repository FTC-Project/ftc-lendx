.PHONY: up down build logs manage migrate makemigrations createsuperuser shell setwebhook createdummyuser worker

# Start services
up:
	docker compose -f compose/docker-compose.dev.yml up --build

# Stop services (keep volumes/data)
down:
	docker compose -f compose/docker-compose.dev.yml down

# Rebuild web container
build:
	docker compose -f compose/docker-compose.dev.yml build web celery_worker

# View logs
logs:
	docker compose -f compose/docker-compose.dev.yml logs -f web celery_worker

# Run any manage.py command: make manage CMD=migrate
manage:
	docker compose -f compose/docker-compose.dev.yml exec web python manage.py $(CMD)

# Common shortcuts
migrate:
	docker compose -f compose/docker-compose.dev.yml exec web python manage.py migrate

makemigrations:
	docker compose -f compose/docker-compose.dev.yml exec web python manage.py makemigrations

createsuperuser:
	docker compose -f compose/docker-compose.dev.yml exec web python manage.py createsuperuser

shell:
	docker compose -f compose/docker-compose.dev.yml exec web python manage.py shell

# Execute the manage.py set_webhook command within the web container
setwebhook:
	docker compose -f compose/docker-compose.dev.yml exec web python manage.py set_webhook

createdummyuser:
	docker compose -f compose/docker-compose.dev.yml exec web python manage.py create_dummy_user

# Run the Celery worker manually
worker:
	docker compose -f compose/docker-compose.dev.yml run --rm celery_worker
