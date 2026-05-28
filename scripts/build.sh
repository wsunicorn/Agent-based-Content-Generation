#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements/production.txt
python manage.py collectstatic --no-input
