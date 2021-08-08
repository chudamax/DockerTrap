import os
import datetime
import yaml
import json
import re

import colorama
from colorama import init, Fore, Back, Style
colorama.init()

from pymongo import MongoClient

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(CURRENT_DIR, 'settings', 'settings.yml')

def extract_urls(cmd):
    regex=r"""\b((?:https?://)?(?:(?:www\.)?(?:[\da-z\.-]+)\.(?:[a-z]{2,6})|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])))(?::[0-9]{1,4}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])?(?:/[\w\.-]*)*/?)\b"""
    matches = re.findall(regex, cmd)
    return matches

def handle_change(change):
    request = change['fullDocument']

    data_json = request['DataJson']

    print_log = '{} [{}]: {} {} {}'.format(
            datetime.datetime.now().isoformat(),
            request['SensorId'],
            request['SourceIP'],
            request['Method'], 
            request['Url']
        )

    exploitation_attempt = False

    if data_json.get('Cmd') and len(data_json['Cmd']) > 0:
        cmd = data_json.get('Cmd')
        cmd_str = ' '.join(cmd)
    else:
        cmd_str = ''
    

    if data_json.get('Entrypoint') and len(data_json['Entrypoint']) > 0:
        entrypoint = data_json.get('Entrypoint')
        entrypoint_str = ' '.join(entrypoint)
    else:
        entrypoint_str = ''
    
    image = data_json.get('Image')

    if image:
        print_log += '\nImage: {}'.format(image)

    if cmd_str:
        exploitation_attempt = True
        print_log += '\nCmd: {}'.format(cmd_str)

        urls = extract_urls(cmd_str)
        if urls:
            print_log += '\nURLs: {}'.format(urls)

    if entrypoint_str:
        exploitation_attempt = True
        print_log += '\nEntrypoint: {}'.format(entrypoint_str)
        
        urls = extract_urls(entrypoint_str)
        if urls:
            print_log += '\nURLs: {}'.format(urls)

    if exploitation_attempt:
        print(Fore.MAGENTA + '{}'.format(print_log))
    else:
        print(Fore.GREEN + '{}'.format(print_log))

def main():
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
