#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, yaml
import datetime, time
import secrets
import os
import dateutil.parser

import mongoengine

import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, make_response, jsonify, request, Response, stream_with_context, redirect
from flask_mongoengine import MongoEngine

from models import db, Docker, DockerImage, DockerContainer, HttpRequestLog, DockerExec
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
        'Data': request.get_data(),
        'SourceIP': request.remote_addr
    }

    o = HttpRequestLog(**log_params).save()

    if settings['sensor']['log_file']:
        #dirty, but works
        log_params['Date'] = str(date_now_utc)
        log_params['Data'] = str(request.get_data())

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

#HEAD /v1.41/containers/2628/archive?path=%2Ftmp%2F2.txt
#PUT /v1.41/containers/2628/archive?noOverwriteDirNonDir=true&path=%2Ftmp HTTP/1.1
@app.route('/containers/<container_id>/archive', methods = ['POST', 'GET', 'HEAD', 'PUT'], endpoint='put_file')
@app.route('/v<api_version>/containers/<container_id>/archive', methods = ['POST', 'GET', 'HEAD', 'PUT'], endpoint='put_file')
def put_file(container_id, api_version=None):
    if request.method == 'HEAD':
        return '', 404
    else:
        path = request.args.get("path")
        return '', 200

@app.route('/containers/create', methods = ['POST', 'GET'], endpoint='container_create')
@app.route('/v<api_version>/containers/create', methods = ['POST', 'GET'], endpoint='container_create')
def create_container(api_version=None):
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
            if container_request['Cmd']:
                cmd = container_request['Cmd']
            else:
                cmd = ''
        
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
        if request.args.get("name"):
            new_container['Name'] = request.args.get("name")
        else:
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
@app.route('/images/create', methods = ['POST', 'GET'], endpoint='image_create')
@app.route('/v<api_version>/images/create', methods = ['POST', 'GET'], endpoint='image_create')
def image_create(api_version=None):
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
@app.route('/containers/<container_id>/attach', methods = ['POST'], endpoint='container_attach')
@app.route('/v<api_version>/containers/<container_id>/attach', methods = ['POST'], endpoint='container_attach')
def container_attach(container_id, api_version=None):

    containers = DockerContainer.objects(Id__startswith='{}'.format(container_id))
    if len(containers) == 0:
        return '', 404

    cmd = containers[0]['Config']['Cmd']
    if cmd in ['id','whoami']:
        resp = Response("uid=0(root) gid=0(root) groups=0(root)")
    else:
        resp = Response("")

    resp.headers['Content-Type'] = 'application/vnd.docker.raw-stream'
    resp.headers['Connection'] = 'Upgrade'
    resp.headers['Upgrade'] = 'tcp'
    return resp, 200

@app.route('/v<api_version>/containers/<container_id>/resize', methods = ['POST'], endpoint='container_resize')
@app.route('/containers/<container_id>/resize', methods = ['POST'], endpoint='container_resize')
def container_resize(container_id, api_version=None):
    return Response()

@app.route('/v<api_version>/exec/<container_id>/resize', methods = ['POST'], endpoint='exec_resize')
@app.route('/exec/<container_id>/resize', methods = ['POST'], endpoint='exec_resize')
def exec_resize(container_id, api_version=None):
    return Response()

@app.route('/v<api_version>/containers/<container_id>', methods = ['DELETE'], endpoint='container_delete')
@app.route('/containers/<container_id>', methods = ['DELETE'], endpoint='container_delete')
def container_delete(container_id, api_version=None):
    return Response()

#/v1.41/containers/061ee0bfdb4c/json
@app.route('/v<api_version>/containers/<container_id>/json', endpoint='container_info')
@app.route('/containers/<container_id>/json', endpoint='container_info')
def container_info(container_id, api_version=None):
    containers = DockerContainer.objects(Id__startswith='{}'.format(container_id))
    if len(containers) > 0:
        return jsonify(containers[0])

    containers = DockerContainer.objects(Name='/{}'.format(container_id))
    if len(containers) > 0:
        return jsonify(containers[0])

    answer = {'message':'No such container: {}'.format(container_id)}
    return jsonify(answer), 404

#/v1.41/containers/061ee0bfdb4c/exec
@app.route('/v<api_version>/containers/<container_id>/exec', methods = ['POST'], endpoint='container_exec')
@app.route('/containers/<container_id>/exec', methods = ['POST'], endpoint='container_exec')
def container_exec(container_id, api_version=None):
    if request.method == 'POST':

        containers = DockerContainer.objects(Id__startswith='{}'.format(container_id))
        if len(containers) == 0:
            answer = {'message':'No such container: {}'.format(container_id)}
            return jsonify(answer), 404

        container = containers[0]

        data = request.get_json()
        new_exec = {}
        new_exec['Id'] = secrets.token_hex(32)
        new_exec['Running'] = False
        new_exec['ExitCode'] = 0

        cmd_array = data.get('Cmd')
        cmd = ''
        if cmd_array:
            cmd = ' '.join(cmd_array)

        process_config = {"tty":True,"entrypoint":cmd,"arguments":[],"privileged":False}
        new_exec['ProcessConfig'] = process_config
        new_exec['OpenStdin'] = False
        new_exec['OpenStderr'] = False
        new_exec['OpenStdout'] = False
        new_exec['CanRemove'] = False
        new_exec['ContainerID'] = container_id
        
        new_exec['DetachKeys'] = ""
        new_exec['Pid'] = 1637
        new_exec['SensorId'] = settings['sensor']['id']

        o = DockerExec(**new_exec).save()

        answer = {"Id":new_exec['Id']}
        return jsonify(answer),201

@app.route('/v<api_version>/exec/<exec_id>/start', methods = ['POST'], endpoint='exec_start')
@app.route('/exec/<exec_id>/start', methods = ['POST'], endpoint='exec_start')
def exec_start(api_version, exec_id):

    exec_list = DockerExec.objects(Id__startswith='{}'.format(exec_id))
    if len(exec_list) == 0:
        answer = {'message':'No such container: {}'.format(exec_id)}
        return jsonify(answer), 404
    exec_obj = exec_list[0]

    cmd = exec_obj.ProcessConfig.get('entrypoint')
    if cmd in ['id','whoami']:
        resp = Response("uid=0(root) gid=0(root) groups=0(root)")
    else:
        resp = Response("")

    return resp

@app.route('/v<api_version>/exec/<exec_id>/json', methods = ['GET'], endpoint='exec_view')
@app.route('/exec/<exec_id>/json', methods = ['POST'], endpoint='exec_view')
def exec_view(api_version, exec_id):

    exec_list = DockerExec.objects(Id__startswith='{}'.format(exec_id))
    if len(exec_list) == 0:
        answer = {'message':'No such container: {}'.format(exec_id)}
        return jsonify(answer), 404

    exec_obj = exec_list[0]   

    return jsonify(exec_obj)

#GET
#http://ip:2375/v1.24/events?filters={"container":{"cb0ef905f1aa248e32261af63a39da3988287bcf6323e0e368bfa7fef212950a":true},"type":{"container":true}}
@app.route('/v<api_version>/events', methods = ['GET'], endpoint='events')
@app.route('/events', methods = ['GET'], endpoint='events')
def events(api_version=None):

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
@app.route('/containers/<container_id>/start', methods = ['POST'], endpoint='container_start')
def container_start(api_version, container_id):
    return '', 204

#/v1.24/containers/061ee0bfdb4c/kill
@app.route('/v<api_version>/containers/<container_id>/kill', methods = ['POST'], endpoint='container_kill')
@app.route('/containers/<container_id>/kill', methods = ['POST'], endpoint='container_kill')
def container_kill(api_version, container_id):
    containers = DockerContainer.objects(Id__startswith='{}'.format(container_id))
    if len(containers) > 0:
        containers[0].delete()
        return '', 200
    else:
        answer = {'message':'No such container: {}'.format(container_id)}
        return jsonify(answer), 404

@app.route('/build', methods = ['POST'], endpoint='build')
@app.route('/v<api_version>/build', methods = ['POST'], endpoint='build')
def build(api_version=None):
    return '', 200


@app.route('/containers/json', endpoint='view_containers')
@app.route('/v<api_version>/containers/json', endpoint='view_containers')
def view_containers(api_version=None):

    containers = []
    for container in DockerContainer.objects(SensorId=settings['sensor']['id']):
        new_container = {}
        new_container['Id'] = container['Id']
        new_container['Names'] = [container['Name']]
        new_container['Image'] = container['Config']['Image']
        new_container['ImageID'] = container['Image'].split(":")[1]

        if type(container['Config']['Cmd']) is mongoengine.base.datastructures.BaseList:
            new_container['Command'] = ' '.join(container['Config']['Cmd'])
        else:
            if container['Config']['Cmd']:
                new_container['Command'] = container['Config']['Cmd']
            else:
                new_container['Command'] = ''
            
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

@app.route('/images/json', endpoint='view_images')
@app.route('/v<api_version>/images/json', endpoint='view_images')
def view_images(api_version=None):
    images = []
    for image in DockerImage.objects(SensorId=settings['sensor']['id']):
        new_image = {}
        new_image['Containers'] = image['Containers']
        new_image['Created'] =  image['Created']
        new_image['Id'] = 'sha256:{}'.format(image['Id'])
        new_image['Labels'] = image['Labels']
        new_image['ParentId'] =  image['ParentId']
        new_image['RepoDigests'] = image['RepoDigests']
        new_image['RepoTags'] =  image['RepoTags']
        new_image['SharedSize'] =  image['SharedSize']
        new_image['Size'] =  image['Size']
        new_image['VirtualSize'] = image['VirtualSize']

        images.append(new_image)

    return jsonify(images)

#/v1.37/images/9873176a8ff5ac192ce4d7df8a403787558b9f3981a4c4d74afb3edceeda451c/json
#TODO
@app.route('/v<api_version>/images/<image_id>/json', endpoint='image_info')
@app.route('/images/<image_id>/json', endpoint='image_info')
def image_info(api_version, image_id):
    images = DockerImage.objects(SensorId=settings['sensor']['id'])
    return '', 404
    #return jsonify(DockerImage.objects(SensorId=settings['sensor']['id'], Id__startswith='{}'.format(image_id))[0])

if __name__ == "__main__":
    app.run(host='0.0.0.0', port='2375')
