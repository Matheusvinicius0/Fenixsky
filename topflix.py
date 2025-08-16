import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import re
import json
import os

def search_topflix(imdb_id, titles, content_type, season=None, episode=None):
    """
    Busca e resolve streams do Topflix, priorizando arquivos JSON da pasta 'Json/'.
    """
    json_path = os.path.join("Json", f"{imdb_id}.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                local_data = json.load(f)

            if local_data.get('id') == imdb_id:
                if content_type == 'series' and season and episode:
                    for item in local_data.get('streams', []):
                        if item.get('temporada') == season and item.get('episodio') == episode:
                            return item.get('streams', [])
                elif content_type == 'movie':
                    return local_data.get('streams', [])

        except Exception:
            pass

    
