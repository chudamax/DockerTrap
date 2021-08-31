import random
import os
import yaml
import re

def extract_urls(cmd):
    regex=r"""\b((?:https?://)?(?:(?:www\.)?(?:[\da-z\.-]+)\.(?:[a-z]{2,6})|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])))(?::[0-9]{1,4}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])?(?:/[\w\.-]*)*/?)\b"""
    matches = re.findall(regex, cmd)
    return list(set(matches))

def get_random_name():
    # Open the file in read mode
    words1 = ["admiring","adoring","affectionate","agitated","amazing","angry","awesome","beautiful","blissful","bold","boring","brave","busy","charming","clever","cool","compassionate","competent","condescending","confident","cranky","crazy","dazzling","determined","distracted","dreamy","eager","ecstatic","elastic","elated","elegant","eloquent","epic","exciting","fervent","festive","flamboyant","focused","friendly","frosty","funny","gallant","gifted","goofy","gracious","great","happy","hardcore","heuristic","hopeful","hungry","infallible","inspiring","interesting","intelligent","jolly","jovial","keen","kind","laughing","loving","lucid","magical","mystifying","modest","musing","naughty","nervous","nice","nifty","nostalgic","objective","optimistic","peaceful","pedantic","pensive","practical","priceless","quirky","quizzical","recursing","relaxed","reverent","romantic","sad","serene","sharp","silly","sleepy","stoic","strange","stupefied","suspicious","sweet","tender","thirsty","trusting","unruffled","upbeat","vibrant","vigilant","vigorous","wizardly","wonderful","xenodochial","youthful","zealous","zen"]
    words2 = ["albattani","allen","almeida","antonelli","agnesi","archimedes","ardinghelli","aryabhata","austin","babbage","banach","overthruster","banzai","bardeen","bartik","bassi","beaver","bell","benz","bhabha","bhaskara","black","blackburn","blackwell","bohr","booth","borg","bose","bouman","boyd","brahmagupta","brattain","brown","buck","burnell","cannon","carson","cartwright","carver","cerf","chandrasekhar","chaplygin","chatelet","chatterjee","chebyshev","cohen","chaum","clarke","colden","cori","cray","curran","curie","darwin","davinci","dewdney","dhawan","diffie","dijkstra","dirac","driscoll","dubinsky","easley","edison","einstein","elbakyan","elgamal","elion","ellis","engelbart","euclid","euler","faraday","feistel","fermat","fermi","feynman","franklin","gagarin","galileo","galois","ganguly","gates","gauss","germain","goldberg","goldstine","goldwasser","golick","goodall","gould","greider","grothendieck","haibt","hamilton","haslett","hawking","hellman","heisenberg","hermann","herschel","hertz","heyrovsky","hodgkin","hofstadter","hoover","hopper","hugle","hypatia","ishizaka","jackson","jang","jemison","jennings","jepsen","johnson","joliot","jones","kalam","kapitsa","kare","keldysh","keller","kepler","khayyam","khorana","kilby","kirch","knuth","kowalevski","lalande","lamarr","lamport","leakey","leavitt","lederberg","lehmann","lewin","lichterman","liskov","lovelace","lumiere","mahavira","margulis","matsumoto","maxwell","mayer","mccarthy","mcclintock","mclaren","mclean","mcnulty","mendel","mendeleev","meitner","meninsky","merkle","mestorf","mirzakhani","montalcini","moore","morse","murdock","moser","napier","nash","neumann","newton","nightingale","nobel","noether","northcutt","noyce","panini","pare","pascal","pasteur","payne","perlman","pike","poincare","poitras","proskuriakova","ptolemy","raman","ramanujan","ride","ritchie","rhodes","robinson","roentgen","rosalind","rubin","saha","sammet","sanderson","satoshi","shamir","shannon","shaw","shirley","shockley","shtern","sinoussi","snyder","solomon","spence","stonebraker","sutherland","swanson","swartz","swirles","taussig","tereshkova","tesla","tharp","thompson","torvalds","tu","turing","varahamihira","vaughan","visvesvaraya","volhard","villani","wescoff","wilbur","wiles","williams","williamson","wilson","wing","wozniak","wright","wu","yalow","yonath","zhukovsky"]
  
    return '/{}_{}'.format(random.choice(words1),random.choice(words2))

def get_settings():
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    SETTINGS_PATH = os.path.join(CURRENT_DIR,'settings','settings.yml')

    settings = {
        'sensor':{},
        'mongodb':{},
        'misp':{}
    }

    settings['headers'] = {
        'Server': "Docker/18.05.0-ce (linux)",
        'Docker-Experimental': 'false',
        'Ostype': 'linux'
    }

    if os.path.isfile(SETTINGS_PATH):
        with open(SETTINGS_PATH, 'r') as stream:
            file_settings = yaml.safe_load(stream)
    else:
        file_settings = None

    if os.environ.get('sensor_id'):
        settings['sensor']['id'] = os.environ['sensor_id']
    elif file_settings['sensor']['id']:
        settings['sensor']['id'] = file_settings['sensor']['id']
    else:
        settings['sensor']['id'] = 'sensor_' + get_random_name()[1:]

    if 'log_file' in os.environ:
        if os.environ['log_file'].lower() == 'true':
            settings['sensor']['log_file'] = True
        else:
            settings['sensor']['log_file'] = False
    else:
        settings['sensor']['log_file'] = file_settings['sensor']['log_file']

    if 'mongodb_uri' in os.environ:
        settings['mongodb']['uri'] = os.environ['mongodb_uri']
    else:
        settings['mongodb']['uri'] = file_settings['mongodb']['uri']

    if 'misp_url' in os.environ:
        settings['misp']['url'] = os.environ['misp_url']
    else:
        settings['misp']['url'] = file_settings['misp']['url']

    if 'misp_key' in os.environ:
        settings['misp']['key'] = os.environ['misp_key']
    else:
        settings['misp']['key'] = file_settings['misp']['key']

    if 'misp_verify' in os.environ:
        if os.environ['misp_verify'].lower() == 'true':
            settings['misp']['verify'] = True
        else:
            settings['misp']['verify'] = False
    else:
        settings['misp']['verify'] = file_settings['misp']['verify']

    if 'misp_cert' in os.environ:
        settings['misp']['cert'] = os.environ['misp_cert']
    else:
        settings['misp']['cert'] = file_settings['misp']['cert']

    return settings