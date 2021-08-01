FROM python:3.7.3-slim
COPY requirements.txt /
RUN pip3 install -r /requirements.txt
COPY . /app
RUN chmod +x /app/scripts/gunicorn_starter.sh
WORKDIR /app
ENTRYPOINT ["/app/scripts/gunicorn_starter.sh"]