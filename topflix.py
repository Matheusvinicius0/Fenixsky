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

    base_url = "https://topflix.watch"
    path = 'filmes' if content_type == 'movie' else 'series'

    for title in titles:
        if not title:
            continue

        slug = title.replace('.', '').replace(' ', '-').lower()
        search_slug = f"assistir-online-{slug}"

        if content_type == 'series' and season and episode:
            search_url = f"{base_url}/{path}/{quote(search_slug)}/--s{season}e{episode}/"
        else:
            search_url = f"{base_url}/{path}/{quote(search_slug)}/"

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Referer': base_url
            }
            page = requests.get(search_url, headers=headers, timeout=15)
            page.raise_for_status()

            post_id = re.search(r"AddComplaint\('(\d+)',", page.text)
            balancer = re.search(r'const VideoBalancerUrl="([^"]+)"', page.text)
            if not post_id or not balancer:
                continue

            video_id = post_id.group(1)
            balancer_url = balancer.group(1)
            player_url = f"{balancer_url}player?id={video_id}"

            if content_type == 'series' and season and episode:
                player_url += f"&season={season-1}&series={episode-1}"

            loader = requests.get(player_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            loader.raise_for_status()

            stream_match = re.search(r"flixPlayer\('([^']+)'", loader.text)
            if not stream_match:
                continue

            stream_url = stream_match.group(1)
            name_match = re.search(r'drawSeriesSelectors\(\{"folder":\[\{"title":"([^"]+)"', loader.text)
            name = name_match.group(1) if name_match else "Player"

            return [{
                "name": f"Topflix - {name}",
                "url": stream_url.replace('\\', '')
            }]

        except Exception:
            continue

    return []
