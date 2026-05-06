#!/bin/bash
set -o errexit

python manage.py prepare_render
gunicorn moviefinder.wsgi:application --log-file -
