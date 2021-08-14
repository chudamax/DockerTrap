import os
import datetime
import yaml
import json
import re
import argparse

import colorama
from colorama import init, Fore, Back, Style
colorama.init()

from pymongo import MongoClient
from utils import extract_urls

from pymisp import ExpandedPyMISP, MISPEvent, MISPTag

def detect_action(request):
    path = request['Url']

    if path.endswith('/_ping') or path.endswith('/version') or path.endswith('/info') or path.endswith('/containers/json') or path.endswith('/images/json'):
        print ('{}: Docker instance enumeration'.format(request['SourceIP']))
    elif path.endswith('/containers/create'):
        print ('{}: Docker container creaion attempt'.format(request['SourceIP']))
    elif path.endswith('/images/create'):  
        print ('{}: Docker image creation attempt'.format(request['SourceIP']))
    elif path.endswith('/attach'):  
        pass
    else:
        print ('Unhandled Event')
        print (request)


def handle_change(change):
    request = change['fullDocument']

    #data_json = request['DataJson']

    action = detect_action(request)


    # print_log = '{} [{}]: {} {} {}'.format(
    #         datetime.datetime.now().isoformat(),
    #         request['SensorId'],
    #         request['SourceIP'],
    #         request['Method'], 
    #         request['Url']
    #     )

    # exploitation_attempt = False

    # if data_json.get('Cmd') and len(data_json['Cmd']) > 0:
    #     cmd = data_json.get('Cmd')
    #     cmd_str = ' '.join(cmd)
    # else:
    #     cmd_str = ''
    

    # if data_json.get('Entrypoint') and len(data_json['Entrypoint']) > 0:
    #     entrypoint = data_json.get('Entrypoint')
    #     entrypoint_str = ' '.join(entrypoint)
    # else:
    #     entrypoint_str = ''
    
    # image = data_json.get('Image')

    # if image:
    #     print_log += '\nImage: {}'.format(image)

    # if cmd_str:
    #     exploitation_attempt = True
    #     print_log += '\nCmd: {}'.format(cmd_str)

    #     urls = extract_urls(cmd_str)
    #     if urls:
    #         print_log += '\nURLs: {}'.format(urls)

    # if entrypoint_str:
    #     exploitation_attempt = True
    #     print_log += '\nEntrypoint: {}'.format(entrypoint_str)
        
    #     urls = extract_urls(entrypoint_str)
    #     if urls:
    #         print_log += '\nURLs: {}'.format(urls)

    # if exploitation_attempt:
    #     print(Fore.MAGENTA + '{}'.format(print_log))
    # else:
    #     print(Fore.GREEN + '{}'.format(print_log))


def main():

    parser = argparse.ArgumentParser(description='Push detected IOCs to a MISP instance.')
    parser.add_argument("-e", "--misp-event", help="New events MISP event id, DockerTrap + current date by default")
    
    args = parser.parse_args()

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    SETTINGS_PATH = os.path.join(CURRENT_DIR, 'settings', 'settings.yml')
    with open(SETTINGS_PATH) as file:
        settings = yaml.load(file, Loader=yaml.FullLoader)
    
    client = MongoClient(settings['mongodb']['uri'])

    print ('Waiting for events...')
    for change in client['DockerHoneypot']['http_request_log'].watch():
        try:
            handle_change(change)
        except Exception as err:
            print (err)


if __name__ == "__main__":
    main()
