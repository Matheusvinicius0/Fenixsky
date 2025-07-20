import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import re
import logging

# Configuração do logging para ajudar a depurar
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def search_topflix(titles, content_type, season=None, episode=None):
    """
    Busca e resolve streams do Topflix.
    A lógica foi atualizada para extrair o ID da postagem de um local mais estável.
    """
    base_url = "https://topflix.watch"
    
    path = 'filmes' if content_type == 'movie' else 'series'

    for title in titles:
        if not title:
            continue
        
        slug_base = title.replace('.', '').replace(' ', '-').lower()
        search_slug = f"assistir-online-{slug_base}"
        
        if content_type == 'series' and season and episode:
            search_url = f"{base_url}/{path}/{quote(search_slug)}/--s{season}e{episode}/"
        else:
            search_url = f"{base_url}/{path}/{quote(search_slug)}/"
        
        logging.info(f"Tentando buscar em (Topflix): {search_url}")
        try:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/91.0.4472.124 Safari/537.36'
                )
            }
            page_response = requests.get(search_url, headers=headers, timeout=15)
            logging.info(f"Status da resposta de Topflix: {page_response.status_code}")
            
            if page_response.status_code != 200:
                continue

            page_text = page_response.text

            # --- CORREÇÃO DEFINITIVA ---
            # Método 1: Pega o ID da postagem do link 'AddComplaint', que é mais estável.
            post_id_match = re.search(r"AddComplaint\('(\d+)',", page_text)
            if post_id_match:
                video_id = post_id_match.group(1)
            else:
                logging.warning("ID da postagem (método AddComplaint) não encontrado.")
                continue

            # Método 2: Pega a URL do Balancer, que continua a mesma.
            balancer_match = re.search(r'const VideoBalancerUrl="([^"]+)"', page_text)
            if balancer_match:
                balancer_url = balancer_match.group(1)
            else:
                logging.warning("URL do Balancer não encontrada.")
                continue
            
            logging.info(f"Balancer: {balancer_url}, Video (Post) ID: {video_id}")
            
            player_loader_url = f"{balancer_url}player?id={video_id}"
            
            # Para séries, o player precisa saber qual temporada/episódio carregar
            if content_type == 'series' and season and episode:
                # O player usa indexação baseada em 0 (temporada 1 é 0, episódio 1 é 0)
                player_loader_url += f"&season={season-1}&series={episode-1}"

            loader_response = requests.get(player_loader_url, headers=headers, timeout=15)
            loader_response.raise_for_status()
            
            stream_match = re.search(r"flixPlayer\('([^']+)'", loader_response.text)
            if not stream_match:
                logging.warning("Link final do stream (flixPlayer) não encontrado.")
                continue

            stream_url = stream_match.group(1)
            player_name = "Player"
            name_match = re.search(r'drawSeriesSelectors\(\{"folder":\[\{"title":"([^"]+)"', loader_response.text)
            if name_match:
                player_name = name_match.group(1)
            
            logging.info(f"Stream final encontrado: {stream_url}")
            return [{
                "name": f"Topflix - {player_name}",
                "url": stream_url.replace('\\', ''),
                "behaviorHints": {"proxyHeaders": {"request": {"Referer": search_url}}}
            }]

        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de requisição no Topflix: {e}")
            continue
        except Exception as e:
            logging.error(f"Erro inesperado no scraper Topflix: {e}", exc_info=True)
            continue

    logging.warning(f"Nenhuma opção de player encontrada no Topflix para '{title}'.")
    return []