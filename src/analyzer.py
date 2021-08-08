import os
import yaml
import json
import colorama
from colorama import init, Fore, Back, Style
colorama.init()

from pymongo import MongoClient

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(CURRENT_DIR, 'settings', 'settings.yml')

def main():
    with open(SETTINGS_PATH) as file:
        settings = yaml.load(file, Loader=yaml.FullLoader)
    
    client = MongoClient(settings['mongodb']['uri'])

    print ('Waiting for events...')
    for change in client['DockerHoneypot']['http_request_log'].watch():

        request = change['fullDocument']
        data_json = request['data_json']
        if 'Cmd' in data_json:
            print(Fore.RED + '[{}]: {} {} {}'.format(
                request['sensor_id'],
                request['source_ip'],
                request['method'], 
                request['url']
            ))
            if data_json['Cmd']:
                print ('Cmd: {}'.format(' '.join(data_json['Cmd'])))

            if data_json['Entrypoint']:
                print ('Entrypoint: {}'.format(' '.join(data_json['Entrypoint'])))

        else:
            print(Fore.GREEN + '[{}]: {} {} {}'.format(
                request['sensor_id'],
                request['source_ip'],
                request['method'], 
                request['url']
            ))

    # db = client['honey']
    # for request in db.http_request_log.find():
    #     print (request['source_ip'], request['url'])

    #     if 'Image' in request['data_json']:
    #         image = request['data_json']['Image']
    #         entrypoint = request['data_json']['Entrypoint']
    #         cmd = request['data_json']['Cmd']

    #         print (request['data_json'])

            # if not (cmd or entrypoint):
            #     print ('Malicious image:{}'.format(image))
            #     print (request['data_json'])

            # if cmd:
            #     print ('Malicious cmd:{}'.format(cmd))

            # if entrypoint:
            #     print ('Malicious entrypoint:{}'.format(entrypoint))


if __name__ == "__main__":
    main()
