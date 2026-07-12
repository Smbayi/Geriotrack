#!/usr/bin/env bash
# Build Render — GérioTrack
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input
