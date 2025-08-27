# ------------ Docker Shortcuts ------------

# Build + Up (detached mode) + Migrate
up:
	docker-compose up --build -d
	docker-compose exec web python manage.py migrate

# Stop + Remove containers
down:
	docker-compose down

# Restart containers
restart:
	docker-compose down
	docker-compose up -d

# See logs (follow)
logs:
	docker-compose logs -f

# Run bash inside web container
bash:
	docker-compose exec web bash

# Create superuser
superuser:
	docker-compose exec web python manage.py createsuperuser

# Collect static files
collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput
