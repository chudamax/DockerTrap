import json, yaml
import datetime, time
import secrets
import os
import dateutil.parser

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
        'Date': date_now_utc,
        'SensorId': settings['sensor']['id'],
        'SensorType': 'Docker',
        'Method': request.method,
        'Path': request.path,
        'Host': request.host.split(':', 1)[0],
        'Args': dict(request.args),
        'Url': request.url,
        'Headers': dict(request.headers),
        'DataJson': request.get_json(),
        'Data': str(request.get_data()),
        'SourceIP': request.remote_addr
    }

    o = HttpRequestLog(**log_params).save()

    if settings['sensor']['log_file']:
        #dirty, but works
        log_params['Date'] = str(date_now_utc)

        date_str = date_now_utc.strftime('%d_%m_%Y')
        log_path = os.path.join(CURRENT_DIR,'logs', date_str + '_log.json')
        with open(log_path,'a') as f:
            f.write('{}\r\n'.format(json.dumps(log_params)))

@app.route('/')
def index():
    anwer = {'message':'page not found'}
    return jsonify(anwer)

@app.route('/_ping', methods = ['HEAD', 'GET'], endpoint='ping')
def ping():
    resp = make_response('OK')
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    return resp

@app.route('/version', endpoint='version_default')
@app.route('/v<api_version>/version', endpoint='version')
def version(api_version=None):
    if api_version:
        current_api_version = float(api_version)

        if current_api_version < 1.12:
            response = "client version {0} is too old. Minimum supported API version is 1.12, please upgrade your client to a newer version".format(current_api_version)
            return response


    docker = Docker.objects(SensorId=settings['sensor']['id']).first()
    keys = ['Platform', 'Version', 'ApiVersion', 'MinAPIVersion', 'GitCommit', 'GoVersion', 'Os', 'Arch', 'KernelVersion','BuildTime', 'Components']
    response = {x:docker[x] for x in keys}

    return jsonify(response)


@app.route('/info', methods = ['HEAD', 'GET'], endpoint='info')
@app.route('/v<api_version>/info', methods = ['HEAD', 'GET'], endpoint='info')
def info(api_version=None):
    docker = Docker.objects(SensorId=settings['sensor']['id']).first()
    keys = [
        'ID', 'Containers', 'ContainersRunning', 'ContainersPaused', 'ContainersStopped', 'Images', 'Driver', 'DriverStatus', 'Plugins',
        'MemoryLimit', 'SwapLimit', 'KernelMemory', 'KernelMemoryTCP', 'CpuCfsPeriod', 'CpuCfsQuota', 'CPUShares', 'CPUSet', 'PidsLimit',
        'IPv4Forwarding','BridgeNfIptables','BridgeNfIp6tables','Debug','NFd','OomKillDisable','NGoroutines','SystemTime','LoggingDriver',
        'CgroupDriver','CgroupVersion','NEventsListener','KernelVersion','OperatingSystem','OSVersion','OSType','Architecture',
        'IndexServerAddress','RegistryConfig','NCPU','MemTotal','GenericResources','DockerRootDir','HttpProxy','HttpsProxy','NoProxy',
        'Name','Labels','ExperimentalBuild','ServerVersion','Runtimes','DefaultRuntime','Swarm','LiveRestoreEnabled',
        'Isolation','InitBinary','ContainerdCommit','RuncCommit','InitCommit','SecurityOptions','Warnings'
    ]
    
    docker_dict = dict({x:docker[x] for x in keys})

    #it's forbidden to user "." in dictname in mongoengine
    #workaround
    docker_dict['RegistryConfig']['IndexConfigs'] = {'docker.io': {'Name': 'docker.io','Mirrors': [],'Secure': True, 'Official': True}}
    docker_dict['Runtimes'] = {
        "io.containerd.runc.v2": {
            "path": "runc"
        },
        "io.containerd.runtime.v1.linux": {
            "path": "runc"
        },
        "runc": {
            "path": "runc"
        }
    }
    docker_dict['SystemTime'] = datetime.datetime.utcnow().isoformat() + 'Z'

    @stream_with_context
    def generate():
        yield json.dumps(docker_dict)

    return Response(generate(), mimetype='application/json')

@app.route('/v<id>/containers/create', methods = ['POST', 'GET'], endpoint='container_create')
def create_container(id):
    if request.method == 'POST':
       
        container_request = request.get_json()
        image = container_request['Image']

        #do we have such image?
        RepoTags = ['{}:latest'.format(image)]
        docker_images = DockerImage.objects(RepoTags=RepoTags, SensorId=settings['sensor']['id'])
        if len(docker_images) == 0:
            answer = {"message":"No such image: {}".format(RepoTags)}
            return jsonify(answer),404

        if type(container_request['Cmd']) is list:
            cmd = ' '.join(container_request['Cmd'])
        else:
            cmd = container_request['Cmd']
        
        with open(MODELS_TEMPLATES_DIR + '/containers.yml') as file:
            new_container = yaml.load(file, Loader=yaml.FullLoader)['default']

        container_id = secrets.token_hex(32)

        new_container['SensorId'] = settings['sensor']['id']
        new_container['Id'] = container_id
        new_container['Created'] = datetime.datetime.utcnow().isoformat()
        new_container['Path'] = cmd
        new_container['State']['StartedAt'] = datetime.datetime.utcnow().isoformat()
        new_container['Image'] = "sha256:{}".format(container_id)
        new_container['ResolvConfPath'] = "/var/lib/docker/containers/{}/resolv.conf".format(container_id)
        new_container['HostnamePath'] =  "/var/lib/docker/containers/{}/hostname".format(container_id)
        new_container['HostsPath'] =  "/var/lib/docker/containers/{}/hosts".format(container_id)
        new_container['LogPath'] =  "/var/lib/docker/containers/{0}/{0}-json.log".format(container_id)
        new_container['Name'] = get_random_name()
        new_container['Config']['Hostname'] = secrets.token_hex(6)
        new_container['Config']['Cmd'] = cmd
        new_container['NetworkSettings']['Networks']['bridge']['NetworkID'] = secrets.token_hex(32)
        new_container['NetworkSettings']['Networks']['bridge']['EndpointID'] = secrets.token_hex(32)

        o = DockerContainer(**new_container).save()

        answer = {
            "Id":container_id,
            "Warnings":[]
        }

        return jsonify(answer),201
    else:
        return jsonify("")

#/v1.24/images/create?fromImage=alpine&tag=latest
@app.route('/v<id>/images/create', methods = ['POST', 'GET'], endpoint='image_create')
def image_create(id):
    if request.method == 'POST':
        image = request.args.get("fromImage")
        tag = request.args.get("tag")

        with open(MODELS_TEMPLATES_DIR + '/images.yml') as file:
            new_image = yaml.load(file, Loader=yaml.FullLoader)['default']

        new_image['Created'] = int(datetime.datetime.utcnow().timestamp())
        new_image['Id'] = secrets.token_hex(32)
        new_image['RepoDigests'] = ["{0}@sha256:{1}".format(image,secrets.token_hex(32))]
        new_image['RepoTags'] = ["{}:{}".format(image,tag)]
        new_image['SensorId'] = settings['sensor']['id']

        o = DockerImage(**new_image).save()

        @stream_with_context
        def generate():
            digest = 'sha256:{}'.format(new_image['Id'])
            yield json.dumps({'status':"Pulling from library/{}".format(image),'id':'{}'.format(tag)})
            yield json.dumps({'status':"Pulling fs layer",'progressDetail':{},'id':'{}'.format(digest)})
            yield json.dumps({'status':"Downloading",'progressDetail':{'current':29404, 'total':2811478}, 'progress':'[\u003e 29.4kB/2.811MB]','id':'{}'.format(digest)})
            time.sleep(1)
            yield json.dumps({'status':"Downloading",'progressDetail':{'current':209404, 'total':2811478}, 'progress':'[\u003e 2MB/2.811MB]','id':'{}'.format(digest)})
            yield json.dumps({'status':"Verifying Checksum",'progressDetail':{}, 'id':'{}'.format(digest)})
            yield json.dumps({'status':"Download complete",'progressDetail':{}, 'id':'{}'.format(digest)})
            yield json.dumps({'status':"Extracting",'progressDetail':{'current':32768, 'total':2811478}, 'progress':'[\u003e 32.77kB/2.811MB]','id':'{}'.format(digest)})
            yield json.dumps({'status':"Pull complete",'progressDetail':{}, 'id':'{}'.format(digest)})
            yield json.dumps({'status':"Digest: {}".format(digest)})
            yield json.dumps({'status':"Downloaded newer image for {}:{}".format(image,digest)})

    return Response(generate(), mimetype='application/json')

#POST
#http://ip:2375/v1.24/containers/cb0ef905f1aa248e32261af63a39da3988287bcf6323e0e368bfa7fef212950a/attach?stderr=1&stdout=1&stream=1
@app.route('/v<api_version>/containers/<container_id>/attach', methods = ['POST'], endpoint='container_attach')
def container_attach(api_version, container_id):

    resp = Response("uid=0(root) gid=0(root) groups=0(root)")
    resp.headers['Content-Type'] = 'application/vnd.docker.raw-stream'
    resp.headers['Connection'] = 'Upgrade'
    resp.headers['Upgrade'] = 'tcp'
    return resp, 101

@app.route('/v<api_version>/containers/<container_id>/resize', methods = ['POST'], endpoint='container_resize')
def container_resize(api_version, container_id):
    return Response()

@app.route('/v<api_version>/containers/<container_id>', methods = ['DELETE'], endpoint='container_delete')
def container_delete(api_version, container_id):
    return Response()

#GET
#http://ip:2375/v1.24/events?filters={"container":{"cb0ef905f1aa248e32261af63a39da3988287bcf6323e0e368bfa7fef212950a":true},"type":{"container":true}}
@app.route('/v<api_version>/events', methods = ['GET'], endpoint='events')
def events(api_version):

    filters = json.loads(request.args.get("filters"))
    id = list(filters['container'].keys())[0]

    containers = DockerContainer.objects(Id=id, SensorId=settings['sensor']['id'])
    if len(containers) > 0:
        container = containers[0]
        image_name = container.Config['Image']
        container_name = container.Name

    event_create = {
          "status": "create",
          "id": id,
          "from": image_name,
          "Type": "container",
          "Action": "create",
          "Actor": {
            "ID": id,
            "Attributes": {
              "com.example.some-label": "some-label-value",
              "image": image_name,
              "name": container_name
            }
          },
          "time": int(datetime.datetime.utcnow().timestamp()),
          "timeNano": int(datetime.datetime.utcnow().timestamp())*10^9
        }

    event_network = {
        "Type": "network",
        "Action": "connect",
        "Actor": {
            "ID": id,
            "Attributes": {
                "container": id,
                "name": "bridge",
                "type": "bridge"
            }
        },
        "scope": "local",
        "time": int(datetime.datetime.utcnow().timestamp()),
        "timeNano": int(datetime.datetime.utcnow().timestamp())*10^9
    }

    event_start = {
        "status": "start",
        "id": id,
        "from": image_name,
        "Type": "container",
        "Action": "start",
        "Actor": {
            "ID": id,
            "Attributes": {
                "image": image_name,
                "name": container_name
            }
        },
        "scope": "local",
        "time": int(datetime.datetime.utcnow().timestamp()),
        "timeNano": int(datetime.datetime.utcnow().timestamp())*10^9
    }
        
    event_resize = {
        "status": "resize",
        "id": id,
        "from": image_name,
        "Type": "container",
        "Action": "resize",
        "Actor": {
            "ID": id,
            "Attributes": {
                "height": "30",
                "image": image_name,
                "name": container_name,
                "width": "120"
            }
        },
        "scope": "local",
        "time": int(datetime.datetime.utcnow().timestamp()),
        "timeNano": int(datetime.datetime.utcnow().timestamp())*10^9
    }

    event_die = {
        "status": "die",
        "id": id,
        "from": image_name,
        "Type": "container",
        "Action": "die",
        "Actor": {
            "ID": id,
            "Attributes": {
                "exitCode": "0",
                "image": image_name,
                "name": container_name
            }
        },
        "scope": "local",
        "time": int(datetime.datetime.utcnow().timestamp()),
        "timeNano": int(datetime.datetime.utcnow().timestamp())*10^9
    }

    @stream_with_context
    def generate():
        yield json.dumps(event_create)
        yield json.dumps(event_network)
        yield json.dumps(event_start)
        yield json.dumps(event_resize)
        yield json.dumps(event_die)

    return Response(generate(), mimetype='application/json')

#POST /v1.24/containers/cb0ef905f1aa248e32261af63a39da3988287bcf6323e0e368bfa7fef212950a/start HTTP/1.1
@app.route('/v<api_version>/containers/<container_id>/start', methods = ['POST'], endpoint='container_start')
def container_start(api_version, container_id):
    return '', 204

@app.route('/v<api_version>/containers/json', endpoint='view_containers')
def view_containers(api_version):

    containers = []
    for container in DockerContainer.objects(SensorId=settings['sensor']['id']):
        new_container = {}
        new_container['Id'] = container['Id']
        new_container['Names'] = [container['Name']]
        new_container['Image'] = container['Config']['Image']
        new_container['ImageID'] = container['Image'].split(":")[1]
        if container['Config']['Cmd']:
            new_container['Command'] = ' '.join(container['Config']['Cmd'])
        else:
            container['Config']['Cmd'] = ''
        new_container['Created'] = int(dateutil.parser.isoparse(container['Created']).timestamp())
        new_container['Ports'] = []
        new_container['Labels'] = {}
        new_container['State'] = container['State']['Status']
        new_container['Status'] = 'Up About a minute'
        new_container['HostConfig'] = {'NetworkMode':'default'}
        new_container['NetworkSettings'] = {}
        new_container['NetworkSettings']['Networks'] = container['NetworkSettings']['Networks']
        new_container['Mounts'] = container['Mounts']

        containers.append(new_container)

    return jsonify(containers)
    
@app.route('/v<api_version>/images/json', endpoint='images_info')
def images_info(api_version):
    return jsonify(DockerImage.objects(SensorId=settings['sensor']['id']))

#/v1.41/containers/061ee0bfdb4c/json
@app.route('/v<api_version>/containers/<container_id>/json', endpoint='container_info')
def container_info(api_version, container_id):
    containers = DockerContainer.objects(Id__startswith='{}'.format(container_id))
    return jsonify(containers[0])

#/v1.41/containers/061ee0bfdb4c/exec
@app.route('/v<api_version>/containers/<container_id>/exec', methods = ['POST'], endpoint='container_exec')
def container_exec(api_version, container_id):
    if request.method == 'POST':
        data = request.get_json()
        answer = {"Id":container_id}
        return jsonify(answer),201

@app.route('/v<api_version>/exec/<container_id>/start', methods = ['POST'], endpoint='exec_start')
def exec_start(api_version, container_id):
    return '', 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port='2375')
