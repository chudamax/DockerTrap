from flask.cli import FlaskGroup
from app import app, db
from models import Docker, DockerImage, DockerContainer
from utils import get_random_name, get_settings
from app import MODELS_TEMPLATES_DIR
import yaml

settings = get_settings()

cli = FlaskGroup(app)

@cli.command("seed_db")
def seed_db():
    
    try:
        Docker.objects(SensorId = settings['sensor']['id']).delete()
    except:
        pass

    try:
        DockerImage.objects(SensorId = settings['sensor']['id']).delete()
    except:
        pass

    try:
        DockerContainer.objects(SensorId = settings['sensor']['id']).delete()
    except:
        pass

    with open(MODELS_TEMPLATES_DIR + '/docker.yml') as file:
        docker = yaml.load(file, Loader=yaml.FullLoader)['default']
        docker['SensorId'] = settings['sensor']['id']
        o = Docker(**docker).save()

    with open(MODELS_TEMPLATES_DIR + '/images.yml') as file:
        images = yaml.load(file, Loader=yaml.FullLoader)
        for image in images.values():
            image['SensorId'] = settings['sensor']['id']
            o = DockerImage(**image).save()

    with open(MODELS_TEMPLATES_DIR + '/containers.yml') as file:
        containers = yaml.load(file, Loader=yaml.FullLoader)
        for container in containers.values():
            container['SensorId'] = settings['sensor']['id']
            o = DockerContainer(**container).save()

if __name__ == "__main__":
    cli()