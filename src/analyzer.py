#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import os
import datetime
import yaml
import json
import re
import argparse
import tarfile, gzip, io

import colorama
from colorama import init, Fore, Back, Style
colorama.init()

from pymongo import MongoClient
from utils import extract_urls, get_settings

def detect_action(request):
    path = request['Path']
    method = request['Method']

    if path.endswith('/_ping') or path.endswith('/version') or path.endswith('/info'):
        action = 'docker_service_enumeration'

    elif path.endswith('/containers/json') or re.match(r'\/v[\d.]*\/containers\/.*\/json', path):
        action = 'docker_containers_enumeration'

    elif path.endswith('/images/json') or re.match(r'\/v[\d.]*\/images\/.*\/json', path):
        action = 'docker_images_enumeration'

    elif path.endswith('/containers/create'):
        action = 'docker_containers_create'

    elif method == 'HEAD' and 'archive' in path:
        action = 'docker_containers_check_file'

    elif method == 'PUT' and 'archive' in path:
        action = 'docker_containers_put_file'

    elif path.endswith('/containers/kill'):
        action = 'docker_containers_kill'

    elif path.endswith('/images/create'):  
        action = 'docker_images_create'

    elif path.endswith('/exec'):
        action = 'docker_container_exec'

    elif path.endswith('/build'):
        action = 'docker_container_build'

    elif path.endswith('/start') or path.endswith('/attach') or path.endswith('/resize') or path.endswith('/events') or \
    path == ('/') or path == ('/favicon.ico') or re.match(r'\/v[\d.]*\/exec\/.*\/json', path):
        action = 'other'

    elif method == 'DELETE' and 'containers' in path:
        action = 'docker_container_delete'

    elif re.match(r'\/v[\d.]*\/containers\/[\d\w]*\/json', path):
        action = 'docker_container_enumeration'
    else:
        action = 'unhandled'
    
    return action

def handle_change(change, misp_event=None):
    request = change['fullDocument']
    data_json = request['DataJson']

    action = detect_action(request)
    dt = datetime.datetime.now().strftime("[%d/%m/%Y %H:%M:%S]")
    path = request['Path']

    if action == 'docker_service_enumeration':
        print (Fore.GREEN + '{} {} Docker service enumeration [{}]'.format(dt, request['SourceIP'], path))

    elif action == 'docker_containers_enumeration':
        print (Fore.GREEN + '{} {} Docker containers enumeration [{}]'.format(dt, request['SourceIP'], path))

    elif action == 'docker_containers_check_file':
        filepath = request.args.get("path")
        print (Fore.GREEN + '{} {} Docker container check file: {} [{}]'.format(dt, request['SourceIP'], filepath, path))

    elif action == 'docker_containers_put_file':
        dirpath = request.args.get("path")
        print (Fore.GREEN + '{} {} Docker container put file to: {} [{}]'.format(dt, request['SourceIP'], dirpath, path))

    elif action == 'docker_images_enumeration':
        print (Fore.GREEN + '{} {} Docker images enumeration [{}]'.format(dt, request['SourceIP'], path))

    elif action == 'docker_containers_create':
        cmd = data_json.get('Cmd')
        entrypoint = data_json.get('Entrypoint')
        env = data_json.get('Env')
        image = data_json.get('Image')

        urls = []

        if cmd:
            cmd = ' '.join(cmd)
            urls += extract_urls(cmd=cmd)

        if entrypoint:
            entrypoint = ' '.join(entrypoint)
            urls += extract_urls(cmd=entrypoint)

        urls = list(set(urls))

        print (Fore.MAGENTA + '{} {} Docker container creation attempt [{}]'.format(dt, request['SourceIP'], path))
        print (Fore.YELLOW + 'Image: {}'.format(image))

        if env:
            print (Fore.YELLOW + 'Env: {}'.format(data_json.get('Env')))

        if cmd:
            print (Fore.YELLOW + 'Cmd: {}'.format(cmd))

        if entrypoint:
            print (Fore.YELLOW + 'Entrypoint: {}'.format(entrypoint))

        if urls:
            print (Fore.YELLOW + 'Extracted URLs: {}'.format(urls))

    elif action == 'docker_images_create':
        print (Fore.MAGENTA + '{} {} Docker image creation attempt [{}]'.format(dt, request['SourceIP'], path))
        print (Fore.YELLOW + 'Image: {} Tag: {}'.format(request['Args']['fromImage'], request['Args']['tag']))

    elif action == 'docker_container_exec':
        cmd = ' '.join(data_json.get('Cmd'))
        urls = extract_urls(cmd=cmd)

        print (Fore.MAGENTA + '{} {} Docker container execution request [{}]'.format(dt, request['SourceIP'], path))

        if cmd:
            print (Fore.YELLOW + 'Cmd: {}'.format(cmd))

        if urls:
            print (Fore.YELLOW + 'Extracted URLs: {}'.format(urls))

    elif action =='docker_container_delete':
        print (Fore.MAGENTA + '{} {} Docker container DELETE request [{}]'.format(dt, request['SourceIP'], path))

    elif action =='docker_container_kill':
        print (Fore.MAGENTA + '{} {} Docker container KILL request [{}]'.format(dt, request['SourceIP'], path))

    elif action == 'docker_container_enumeration':
        print (Fore.GREEN + '{} {} Docker container enumeration[{}]'.format(dt, request['SourceIP'], path))

    elif action == 'docker_container_build':
        print (Fore.MAGENTA + '{} {} Docker container build attempt[{}]'.format(dt, request['SourceIP'], path))

        if request['Data'][:2] == b'\x1f\x8b':
            b = gzip.decompress(request['Data'])
            file_like_object = io.BytesIO(b)
        else:
            file_like_object = io.BytesIO(request['Data'])

        tar = tarfile.open(fileobj=file_like_object)
        dockerfile = tar.extractfile(tar.getmembers()[0]).read().decode('utf-8')
        urls = extract_urls(cmd=dockerfile)

        if dockerfile:
            print (Fore.YELLOW + 'Dockerfile:\n{}'.format(dockerfile))

        if urls:
            print (Fore.YELLOW + 'Extracted URLs: {}'.format(urls))

    elif action == 'unhandled':
        print ('Unhandled Event')
        print (request)

def main():
    settings = get_settings()
    
    client = MongoClient(settings['mongodb']['uri'])

    print ('Waiting for events...')
    for change in client['DockerHoneypot']['http_request_log'].watch():
        try:
            handle_change(change)
        except Exception as err:
            print (err)

if __name__ == "__main__":
    main()
