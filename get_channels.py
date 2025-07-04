import requests
import base64
import json
from urllib.parse import unquote

def fix_b64(b64str):
    if not '=' in b64str:
        b64str += "=" * (-len(b64str) % 4)
    return b64str

def encode_id(i):
    id_base64 = base64.urlsafe_b64encode(i.encode()).decode()  # Use urlsafe_b64encode
    id_base64_ = id_base64.rstrip('=')  # Remove padding '='
    return id_base64_

def decode_id(i):
    # NOME ALTERADO
    if 'fenixsky' in i:
        i = i.replace('fenixsky:', '')
    b64decode_ = fix_b64(i)
    dict_ = json.loads(base64.urlsafe_b64decode(b64decode_).decode())  # Use urlsafe_b64decode
    return dict_

def get_meta_tv(i):
    i_ = decode_id(i)
    try:
        iten = {
            "id": i,
            "type": "tv",
            "name": i_.get('name', ''),
            "poster": i_.get('thumb', ''),
            "background": i_.get('thumb', ''),
            "description": f"Canal {i_.get('name', '')} ao vivo.",
            "genres": [i_.get('genre', '')],
        }
        return iten
    except Exception as e:
        return {}

def get_stream_tv(i):
    i_ = decode_id(i)
    return {
        'streams': [{
        'name': 'FenixSky', # NOME ALTERADO
        'title': i_.get('name', "Live Channel"),
        'url': f"https://zoreu-f4mtesterweb.hf.space/proxy?url={i_.get('stream', '')}",
        }],
    }


class xtream_api:
    def __init__(self, dns, username, password):
        self.live_url = '{0}/player_api.php?username={1}&password={2}&action=get_live_categories'.format(dns, username, password)
        self.player_api = '{0}/player_api.php?username={1}&password={2}'.format(dns, username, password)
        self.play_url = '{0}/live/{1}/{2}/'.format(dns,username,password)

    def list_channels(self, category):
        group = {'Abertos': ['sbt', 'abertos', 'globo', 'record'], 
                 'Esportes': ['amazon', 'espn', 'sportv', 'premiere', 'sportv', 'premiere', 'esportes', 'disney', 'max'], 
                 'NBA': ['nba'], 
                 'PPV': ['ppv'], 
                 'Paramount plus': ['paramount'], 
                 'DAZN': ['dazn'], 
                 'Nosso Futebol': ['nosso futebol'], 
                 'UFC': ['ufc'], 
                 'Combate': ['combate'], 
                 'NFL': ['nfl'],
                 'Documentarios': ['documentarios', 'documentários'],
                 'Infantil': ['infantil'],
                 'Filmes e Series': ['filmes e séries', 'filmes e series'],
                 'Telecine': ['telecine'],
                 'HBO': ['hbo'],
                 'Cine Sky': ['cine sky'],
                 'Noticias': ['noticias', 'notícias'],
                 'Musicas': ['musicas', 'músicas'],
                 'Variedades': ['variedades'],
                 'Cine 24h': ['cine 24h'],
                 'Desenhos': ['desenhos'],
                 'Series 24h': ['séries 24h', 'series 24h', '24h series'],
                 'Religiosos': ['religiosos'],
                 '4K': ['4k'],
                 'Radios': ['radios'],
                 'Reality': ['power couple', 'a fazenda', 'bbb', 'big brother']
                 }
        itens = []
        try:
            vod_cat = requests.get(self.live_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.141 Safari/537.36'}).json()
            if vod_cat:
                keys = group.get(category)
                for key in keys:
                    for cat in vod_cat:
                        name = cat['category_name']
                        name2 = name.lower()
                        url = self.player_api + '&action=get_live_streams&category_id=' + str(cat['category_id'])
                        if not 'All' in name:
                            if key in name2:
                                i = self.channels_open(url, category)
                                if i:
                                    for l in i:
                                        itens.append(l)
        except:
            pass
        return itens 

    def generate_id_channel(self, name, url, thumb, genre):
        i = {'name': name, 'stream': url, 'thumb': thumb, 'genre': genre}
        id_json = json.dumps(i)
        # NOME ALTERADO
        stremio_id = 'fenixsky:' + encode_id(id_json)
        return stremio_id


    def channels_open(self, url, category):
        itens = []
        vod_cat = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.141 Safari/537.36'}).json()
        if vod_cat:
            for cat in vod_cat:
                name = cat['name']
                stream_id = str(cat['stream_id'])
                url_ = '{0}{1}.m3u8'.format(self.play_url,stream_id)
                try:
                    thumb = 'https://da5f663b4690-proxyimage.baby-beamup.club/proxy-image/?url=' + cat['stream_icon']
                except:
                    thumb = ''
                iten = {
                    "id": self.generate_id_channel(name, url_, thumb, category),
                    "type": "tv",
                    "name": name,
                    "poster": thumb,
                    "background": thumb,
                    "description": f"Canal {name} ao vivo.",
                    "genres": [category]
                }
                itens.append(iten)
        return itens



def get_api():
    url = 'https://drive.google.com/uc?export=download&id=1rCaCa20V8-IqREXszsqn4rXKlTbpBk4q'
    data = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.141 Safari/537.36'}).json()
    try:
        api = xtream_api(data['host'], data['username'], data['password'])
        return api
    except Exception as e:
        raise f'Erro em {e}'