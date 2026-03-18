#!/bin/zsh
ENV_FILE=.env.real ./.venv/bin/python manage.py migrate
