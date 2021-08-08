#!/bin/sh
gunicorn --chdir /app/src registry:app -w 5 --threads 5 -b 0.0.0.0:5000