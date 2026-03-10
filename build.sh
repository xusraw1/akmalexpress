#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Automatically create a superuser if DJANGO_SUPERUSER_USERNAME is set in the environment
if [[ -n "${DJANGO_SUPERUSER_USERNAME}" ]]; then
  echo "Creating superuser..."
  python manage.py createsuperuser --noinput || echo "Superuser already exists."
fi
