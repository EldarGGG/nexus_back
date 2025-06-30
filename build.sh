#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python nexus_back/manage.py collectstatic --no-input
python nexus_back/manage.py migrate
