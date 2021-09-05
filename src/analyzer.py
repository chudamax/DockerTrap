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

def get_action_info(request):
    data_json = request['DataJson']
    method = request['Method']

    path = request['Path']

    action_info = {
        'request': request,
        'action': None,
        'action_type': None,
        'cmd':None,
        'entrypoint': None,
        'image': None,
        'env': None,
        'urls': [],
        'dockerfile': None,
        'filepath': None,
        'dirpath': None
    }

    #Service Enumeration
    if path.endswith('/_ping') or path.endswith('/version') or path.endswith('/info'):
        action_info['action'] = 'Docker service enumeration'
        action_info['type'] = 'Enumeration'
        
    #Container enumeration
    elif path.endswith('/containers/json') or re.match(r'\/v[\d.]*\/containers\/.*\/json', path):
        action_info['action'] = 'Docker containers enumeration'
        action_info['type'] = 'Enumeration'
      
    #Image enumeration
    elif path.endswith('/images/json') or re.match(r'\/v[\d.]*\/images\/.*\/json', path):
        action_info['action'] = 'Docker images enumeration'
        action_info['type'] = 'Enumeration'
       
    #Container check file
    elif method == 'HEAD' and 'archive' in path:
        action_info['action'] = 'Docker container check file'
        action_info['type'] = 'Enumeration'
        action_info['filepath'] = request['Args'].get("path")
       
    #Upload a new file
    elif method == 'PUT' and 'archive' in path:
        action_info['action'] = "Docker container put file"
        action_info['type'] = 'Exploitation'
        action_info['dirpath'] = request['Args'].get("path")

    #Create a new container
    elif path.endswith('/containers/create'):
        action_info['action'] = 'Docker container creation attempt'
        action_info['type'] = 'Exploitation'

        cmd = data_json.get('Cmd')
        entrypoint = data_json.get('Entrypoint')
        env = data_json.get('Env')
        image = data_json.get('Image')
        urls = []

        action_info['image'] = image

        if cmd:
            cmd = ' '.join(cmd)
            urls += extract_urls(cmd=cmd)
            action_info['cmd'] = cmd

        if entrypoint:
            entrypoint = ' '.join(entrypoint)
            urls += extract_urls(cmd=entrypoint)
            action_info['entrypoint'] = entrypoint


        urls = list(set(urls))
        action_info['urls'] = urls
    
    #Create a new image
    elif path.endswith('/images/create'):
        action_info['action'] = 'Docker image creation attempt'
        action_info['type'] = 'Exploitation'

        action_info['image'] = request['Args']['fromImage']
        action_info['tag'] = request['Args']['tag']

    #Execute a command
    elif path.endswith('/exec'):
        action_info['action'] = 'Docker container execution request'
        action_info['type'] = 'Exploitation'

        cmd = ' '.join(data_json.get('Cmd'))
        urls = extract_urls(cmd=cmd)

        if cmd:
            action_info['cmd'] = cmd

        if urls:
            action_info['urls'] = urls

    #Delete container
    elif method == 'DELETE' and 'containers' in path:
        action_info['action'] = 'Docker container DELETE request'
        action_info['type'] = 'Exploitation'

    #Kill container
    elif path.endswith('/containers/kill'):
        action_info['action'] = 'Docker container KILL request'
        action_info['type'] = 'Exploitation'

    #List container properties
    elif re.match(r'\/v[\d.]*\/containers\/[\d\w]*\/json', path):
        action_info['action'] = 'Docker container enumeration'
        action_info['type'] = 'Enumeration'

    #Build a new container from a docker file
    elif path.endswith('/build'):
        action_info['action'] = 'Docker container build attempt'
        action_info['type'] = 'Exploitation'

        if request['Data'][:2] == b'\x1f\x8b':
            b = gzip.decompress(request['Data'])
            file_like_object = io.BytesIO(b)
        else:
            file_like_object = io.BytesIO(request['Data'])

        tar = tarfile.open(fileobj=file_like_object)
        dockerfile = tar.extractfile(tar.getmembers()[0]).read().decode('utf-8')
        urls = extract_urls(cmd=dockerfile)

        if dockerfile:
            action_info['dockerfile'] = dockerfile

        if urls:
            action_info['urls'] = urls

    #system events or just trash
    elif path.endswith('/start') or path.endswith('/attach') or path.endswith('/resize') or path.endswith('/events') or \
    path == ('/') or path == ('/favicon.ico') or re.match(r'\/v[\d.]*\/exec\/.*\/json', path):
        action_info['action'] = 'Ignore'
        action_info['type'] = 'Ignore'

    else:
        action_info['action'] = 'Unhandled'
        action_info['type'] = 'Unhandled'

    return action_info

def handle_change(change):

    dt = datetime.datetime.now().strftime("[%d/%m/%Y %H:%M:%S]")

    request = change['fullDocument']
    action_info = get_action_info(request)

    if action_info['action'] == 'Ignore':
        return
    elif action_info['action'] == 'Unhandled':
        print (Fore.WHITE + 'Unhandled request: {}'.format(action_info['request']))
        print (Fore.WHITE + '{} {} {} [{}]'.format(dt, action_info['request']['SourceIP'], action_info['action'], action_info['request']['Path']))
        return

    if action_info['type'] == 'Exploitation':
        print (Fore.MAGENTA)
    else:
        print (Fore.GREEN)

    print ('{} {} {} [{}]'.format(dt, action_info['request']['SourceIP'], action_info['action'], action_info['request']['Path']))
    print ('Action: {}'.format(action_info['action']))
    print ('Type: {}'.format(action_info['type']))
    
    for name,value in action_info.items():

        if name in ['action','type','request']:
            continue

        if value:
            print (Fore.YELLOW + '{}: {}'.format(name.capitalize(), value))

def main():
    settings = get_settings()
    
    client = MongoClient(settings['mongodb']['uri'])

    print ('Waiting for events...')
    for change in client['DockerHoneypot']['http_request_log'].watch():
        handle_change(change)

        # try:
        #     handle_change(change)
        # except Exception as err:
        #     print (err)

if __name__ == "__main__":
    main()
