#!/bin/zsh
ENV_FILE=.env.local ./.venv/bin/python manage.py migrate
