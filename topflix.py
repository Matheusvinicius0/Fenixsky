import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import re

def search_topflix(titles, content_type, season=None, episode=None):
    """
    Busca e resolve streams do Topflix num único passo.
    """
    base_url = "https://topflix.watch"
    final_streams = []

    path = 'filmes' if content_type == 'movie' else 'series'

    for title in titles:
        slug_base = title.replace('.', '').replace(' ', '-').lower()
        search_slug = f"assistir-online-{slug_base}"
        search_url = f"{base_url}/{path}/{quote(search_slug)}"
        
        try:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/91.0.4472.124 Safari/537.36'
                )
            }
            page_response = requests.get(search_url, headers=headers, timeout=10)
            if page_response.status_code != 200:
                continue

            soup = BeautifulSoup(page_response.text, 'html.parser')
            scripts = soup.find_all('script')

            balancer_url, video_id = None, None
            for script in scripts:
                if script.string:
                    if not balancer_url:
                        balancer_match = re.search(r'const VideoBalancerUrl="([^"]+)"', script.string)
                        if balancer_match:
                            balancer_url = balancer_match.group(1)
                    
                    if not video_id:
                        id_match = re.search(r'player\?id=(\d+)', script.string)
                        if id_match:
                            video_id = id_match.group(1)
            
            if not (balancer_url and video_id):
                continue

            player_loader_url = f"{balancer_url}player?id={video_id}"
            loader_response = requests.get(player_loader_url, headers=headers, timeout=15)
            loader_response.raise_for_status()
            
            stream_match = re.search(r"flixPlayer\('([^']+)'", loader_response.text)
            if not stream_match:
                continue

            stream_url = stream_match.group(1)
            player_name = "Player"
            name_match = re.search(r'drawSeriesSelectors\({.*?"title":"([^"]+)"', loader_response.text)
            if name_match:
                player_name = name_match.group(1)
            
            final_streams.append({
                "name": f"Topflix - {player_name}",
                "url": stream_url.replace('\\', ''),
                "behaviorHints": {"proxyHeaders": {"request": headers}}
            })

            if final_streams:
                return final_streams

        except:
            continue

    return []
