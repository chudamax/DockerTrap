#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import argparse
import os
import yaml
import json
import pytz
from datetime import datetime, timedelta

import random
from random import randrange

import socket
import multiprocessing

from pymisp import ExpandedPyMISP, MISPEvent, MISPTag

from pymongo import MongoClient
from utils import get_settings, extract_urls

settings = get_settings()

def get_lock(process_name):
    #https://stackoverflow.com/questions/788411/check-to-see-if-python-script-is-running

    # Without holding a reference to our socket somewhere it gets garbage
    # collected when the function exits
    get_lock._lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    try:
        # The null byte (\0) means the the socket is created 
        # in the abstract namespace instead of being created 
        # on the file system itself.
        # Works only in Linux
        get_lock._lock_socket.bind('\0' + process_name)
        print ('I got the lock')
    except socket.error:
        print ('lock exists')
        sys.exit()

def call_with_timeout(func, args, kwargs, timeout):

    #for LINUX only
    manager = multiprocessing.Manager()
    return_dict = manager.dict()
    #define a wrapper of 'return dict' to store the results
    def function(return_dict):
        return_dict['value'] = func(*args, **kwargs)
    p = multiprocessing.Process(target=function, args=(return_dict,))
    p.start()
    #Force a max 'timeout' or wait for the process to finish
    p.join(timeout)
    #If thread is still active, it didn't finish: raise TimeoutError
    if p.is_alive():
        p.terminate()
        p.join()
        raise TimeoutError
    else:
        return return_dict.get('value')

def create_MISP_event(misp, event_name, attributes, to_ids=False):

    event = MISPEvent()
    event.distribution = 0
    event.threat_level_id = 1
    event.analysis = 0
    event.info = event_name
    tag = MISPTag()
    # tag.name = "type:SIR"
    # event.tags = [tag]

    attributes = []
    for artifact in attributes:

        to_ids = False
        
        attribute = None

        if 'src_ip' in artifact['cef']:
            artifact_type = 'ip-src'
            attribute = {
                'type':artifact_type,
                'to_ids':to_ids,
                'value':artifact['cef']['src_ip'],
            }

        elif 'url' in artifact['cef']:
            artifact_type = 'url'
            attribute = {
                'type':artifact_type,
                'to_ids':to_ids,
                'value':artifact['cef']['url'],
            }

        #TODO: need to use an another approach here, to rely only on hash length is not a good idea
        elif 'hash' in artifact['cef']:
            hash_value = artifact['cef']['hash']

            if len(hash_value) == 32:
                hash_type = 'md5'
            elif len(hash_value) == 40:
                hash_type = 'sha1'
            elif len(hash_value) == 64:
                hash_type = 'sha256'

            artifact_type = 'url'
            attribute = {
                'type':hash_type,
                'to_ids':to_ids,
                'value':artifact['cef']['hash'],
            }
            
        if attribute:
            attributes.append(attribute)

    if len (attributes) > 0:
        event = misp.add_event(event, pythonify=True)

        for attribute in attributes:
            misp.add_attribute(event.id, attribute, pythonify=True)

    return event
  
def main():
    parser = argparse.ArgumentParser(description='Push detected IOCs to a MISP instance.')
    parser.add_argument("-l", "--last", required=True, help="can be defined minutes (for example 30m).")
    
    args = parser.parse_args()

    CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
    SETTINGS_PATH = os.path.join(CURRENT_DIR, 'settings', 'settings.yml')
   
    with open(SETTINGS_PATH) as f:
        settings = yaml.safe_load(f)

    misp_settings = settings['misp']

    misp = ExpandedPyMISP(misp_settings['url'], misp_settings['key'], misp_settings['verify'], cert=misp_settings['cert'])

    client = MongoClient(settings['mongodb']['uri'])
    db = client['DockerHoneypot']

    start = datetime.now() - timedelta(minutes=int(args.last))
    request_logs = db.http_request_log.find( {'Date': {'$gte': start}})

    attributes = []
    to_ids = False

    for request in request_logs:
        data_json = request['DataJson']

        if data_json.get('Cmd') and len(data_json['Cmd']) > 0:
            cmd = data_json.get('Cmd')
            cmd_str = ' '.join(cmd)
            urls = extract_urls(cmd_str)

            for url in urls:
                attribute = {
                    'type':'url',
                    'to_ids':to_ids,
                    'value':url,
                    #'comment': '{} requested execution for a new docker container using "Cmd" entry: {}'.format(request['SourceIP'], cmd_str)
                    'comment': str(data_json)
                }
                if not attribute in attributes:
                    attributes.append(attribute)
        else:
            cmd_str = None

        if data_json.get('Entrypoint') and len(data_json['Entrypoint']) > 0:
            entrypoint = data_json.get('Entrypoint')
            entrypoint_str = ' '.join(entrypoint)
            urls = extract_urls(entrypoint_str)

            for url in urls:
                attribute = {
                    'type':'url',
                    'to_ids':to_ids,
                    'value':url,
                    #'comment': '{} requested execution for a new docker container using "Entrypoint" entry: {}'.format(request['SourceIP'], entrypoint_str)
                    'comment': str(data_json)
                }
                if not attribute in attributes:
                    attributes.append(attribute)
        else:
            entrypoint_str = None

        if cmd_str or entrypoint_str:
            attribute = {
                    'type':'ip-src',
                    'to_ids':to_ids,
                    'value':request['SourceIP'],
                   # 'comment': 'Docker command: Cmd:{} Entrypoint:{}'.format(cmd_str, entrypoint_str)
                   'comment': str(data_json)
                }

            if not attribute in attributes:
                attributes.append(attribute)

    event = MISPEvent()
    event.distribution = 0
    event.threat_level_id = 1
    event.analysis = 0
    event.info = f'Docker honeypot (DockerTrap) {datetime.now():%Y-%m-%d}'
    event.add_tag('AutoGenerated')
    event.add_tag('honeypot-basic:interaction-level="high"')
    event = misp.add_event(event, pythonify=True)

    for attribute in attributes:
        misp.add_attribute(event.id, attribute, pythonify=True)

   

if __name__ == '__main__':

    if os.name == 'nt':
        main()
    else:
        get_lock("send_to_misp")
        call_with_timeout(main,(),{},60)
