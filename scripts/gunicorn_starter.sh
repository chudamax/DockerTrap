#!/bin/sh
gunicorn --chdir /app/src app:app -w 5 --threads 5 -b 0.0.0.0:2375