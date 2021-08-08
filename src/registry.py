import json, yaml
import datetime, time
import secrets
import os


import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, make_response, jsonify, request, Response, stream_with_context, redirect
from flask_mongoengine import MongoEngine

from models import db, Docker, DockerImage, DockerContainer, HttpRequestLog
from utils import get_random_name, get_settings


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_TEMPLATES_DIR = os.path.join(CURRENT_DIR,'templates','models')

settings = get_settings()

app = Flask(__name__)

app.config['MONGODB_SETTINGS'] = {
    'host': settings['mongodb']['uri']
    }

db.init_app(app)

# def init_db():

#     Docker.objects.delete()
#     with open(MODELS_TEMPLATES_DIR + '/docker.yml') as file:
#         docker = yaml.load(file, Loader=yaml.FullLoader)['default']
#     o = Docker(**docker).save()

@app.after_request
def docker_headers_mimicking(response):
    for key, value in settings['headers'].items():
        response.headers[key] = value
    return response

@app.before_request 
def before_request_callback():
    # if request.get_json():
    #     print (request.get_json())

    date_now_utc = datetime.datetime.utcnow()

    log_params = {
        'date': date_now_utc,
        'sensor_id': settings['sensor']['id'],
        'sensor_type': settings['sensor']['type'],
        'method': request.method,
        'path': request.path,
        'host': request.host.split(':', 1)[0],
        'args': dict(request.args),
        'url': request.url,
        'headers': dict(request.headers),
        'data_json': request.get_json(),
        'data': str(request.get_data()),
        'source_ip': request.remote_addr
    }

    o = HttpRequestLog(**log_params).save()

    if settings['sensor']['log_file']:
        #dirty, but works
        log_params['date'] = str(date_now_utc)

        date_str = date_now_utc.strftime('%d_%m_%Y')
        log_path = os.path.join(CURRENT_DIR,'logs', date_str + '_log.json')
        with open(log_path,'a') as f:
            f.write('{}\r\n'.format(json.dumps(log_params)))

@app.route('/')
def index():
    anwer = {'message':'page not found'}
    return jsonify(anwer)


if __name__ == "__main__":
    # init_db()
    app.run(host='0.0.0.0', port='5000')
