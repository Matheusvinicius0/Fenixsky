import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import re
import logging
import json
import os

# Configuração do logging para ajudar a depurar
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def search_topflix(imdb_id, titles, content_type, season=None, episode=None):
    """
    Busca e resolve streams do Topflix, com prioridade para arquivos JSON locais.
    """
    # --- INÍCIO: LÓGICA DE PESQUISA NO JSON LOCAL ---
    json_file_path = f"{imdb_id}.json"
    if os.path.exists(json_file_path):
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                local_data = json.load(f)
            
            # Confirma se o ID dentro do arquivo é o mesmo que o solicitado
            if local_data.get('id') == imdb_id:
                logging.info(f"Dados encontrados para {imdb_id} no arquivo JSON local.")
                
                # Para séries, procura o episódio específico
                if content_type == 'series' and season and episode:
                    for episode_data in local_data.get('streams', []):
                        if episode_data.get('temporada') == season and episode_data.get('episodio') == episode:
                            # Retorna a lista de streams para o episódio encontrado
                            return episode_data.get('streams', [])
                
                # Para filmes, retorna todos os streams disponíveis
                elif content_type == 'movie':
                    return local_data.get('streams', [])

        except (json.JSONDecodeError, Exception) as e:
            logging.error(f"Erro ao ler o arquivo JSON local {json_file_path}: {e}")
    # --- FIM: LÓGICA DE PESQUISA NO JSON LOCAL ---

    # Se nada foi retornado do JSON, continua com a busca na web (lógica original).
    logging.info(f"Nenhum dado local encontrado para {imdb_id}. Buscando no site Topflix.")
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
        
        page_response = None
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': base_url
            }
            page_response = requests.get(search_url, headers=headers, timeout=20)
            page_response.raise_for_status()
        
        except requests.exceptions.RequestException as e:
            logging.error(f"A conexão direta falhou: {e}")
            continue

        try:
            logging.info(f"Status da resposta de Topflix: {page_response.status_code}")
            page_text = page_response.text

            post_id_match = re.search(r"AddComplaint\('(\d+)',", page_text)
            if not post_id_match:
                logging.warning("ID da postagem (método AddComplaint) não encontrado.")
                continue
            video_id = post_id_match.group(1)

            balancer_match = re.search(r'const VideoBalancerUrl="([^"]+)"', page_text)
            if not balancer_match:
                logging.warning("URL do Balancer não encontrada.")
                continue
            balancer_url = balancer_match.group(1)
            
            logging.info(f"Balancer: {balancer_url}, Video (Post) ID: {video_id}")
            
            player_loader_url = f"{balancer_url}player?id={video_id}"
            
            if content_type == 'series' and season and episode:
                player_loader_url += f"&season={season-1}&series={episode-1}"

            loader_headers = headers.copy()
            loader_headers['Referer'] = search_url
            
            loader_response = requests.get(player_loader_url, headers=loader_headers, timeout=20)
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

        except Exception as e:
            logging.error(f"Erro inesperado no scraper Topflix: {e}", exc_info=True)
            continue

    logging.warning(f"Nenhuma opção de player encontrada no Topflix para '{title}'.")
    return []