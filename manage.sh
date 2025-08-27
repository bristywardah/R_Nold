#!/bin/bash

COMMAND=$1

case $COMMAND in
  up)
    docker-compose up --build -d
    docker-compose exec web python manage.py migrate
    ;;
  down)
    docker-compose down
    ;;
  restart)
    docker-compose down
    docker-compose up -d
    ;;
  logs)
    docker-compose logs -f
    ;;
  bash)
    docker-compose exec web bash
    ;;
  superuser)
    docker-compose exec web python manage.py createsuperuser
    ;;
  collectstatic)
    docker-compose exec web python manage.py collectstatic --noinput
    ;;
  *)
    echo "Usage: ./manage.sh {up|down|restart|logs|bash|superuser|collectstatic}"
    ;;
esac
