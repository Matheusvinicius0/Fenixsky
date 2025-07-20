import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
import logging
import re

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def search_gofilmes(titles, content_type, season=None, episode=None):
    """
    Busca por um filme ou série no GoFilmes e retorna o link da página do player.
    """
    base_url = "https://gofilmess.top"
    for title in titles:
        if not title or len(title) < 2: continue
        search_slug = title.replace('.', '').replace(' ', '-').lower()
        path = 'series' if content_type == 'series' else 'filmes'
        url = f"{base_url}/{path}/{quote(search_slug)}" if content_type == 'series' else f"{base_url}/{quote(search_slug)}"
        logging.info(f"Tentando buscar em: {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            logging.info(f"'{title}' ({path}) - Status da resposta: {response.status_code}")
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                if content_type == 'series':
                    season_selectors = ['div.panel', 'div.seasons > div.season', 'div[id^="season-"]']
                    panels = []
                    for selector in season_selectors:
                        panels = soup.select(selector)
                        if panels:
                            logging.info(f"Encontrados {len(panels)} painéis de temporada com o seletor '{selector}'")
                            break
                    if not panels: continue
                    if not (season and episode and 0 < season <= len(panels)): continue
                    selected_panel = panels[season - 1]
                    episode_links = selected_panel.select('div.ep a[href], li a[href]')
                    if 0 < episode <= len(episode_links):
                        return [{"name": f"GoFilmes - S{season}E{episode}", "url": urljoin(base_url, episode_links[episode - 1]['href'])}]
                else:
                    player_links = soup.select('div.link a[href]')
                    if player_links:
                        return [{"name": f"GoFilmes - {link.get_text(strip=True)}", "url": urljoin(base_url, link['href'])} for link in player_links]
        except Exception as e:
            logging.error(f"Erro ao processar '{title}' no GoFilmes: {e}", exc_info=True)
    logging.warning(f"Nenhuma opção de player encontrada no GoFilmes para {content_type}.")
    return []


def resolve_stream(player_url):
    """
    Resolve o stream com múltiplos métodos, agora retornando links do MediaFire para serem tratados no app.py.
    """
    try:
        logging.info(f"Resolvendo stream do GoFilmes com múltiplos métodos: {player_url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://gofilmess.top/'
        }
        response = requests.get(player_url, headers=headers, timeout=15)
        response.raise_for_status()
        page_html = response.text

        # --- MÉTODO 1 (NOVO E PREFERENCIAL) ---
        match_new = re.search(r"const videoSrc = '([^']+)'", page_html)
        if match_new:
            stream_url = match_new.group(1)
            logging.info(f"Stream encontrado com o MÉTODO NOVO: {stream_url}")
            return stream_url, None

        # --- MÉTODO 2 (ANTIGO, COMO FALLBACK) ---
        logging.warning("Método novo falhou. Tentando o método antigo (fallback).")
        soup = BeautifulSoup(page_html, 'html.parser')
        headers_for_stremio = headers.copy()
        headers_for_stremio['Referer'] = player_url

        iframe = soup.find('iframe')
        if iframe and iframe.has_attr('src'):
            stream_url = iframe['src']
            logging.info(f"Stream encontrado com o MÉTODO ANTIGO (iframe): {stream_url}")
            return stream_url, headers_for_stremio

        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                match_old = re.search(r'"file"\s*:\s*"([^"]+)"', script.string)
                if match_old:
                    stream_url = match_old.group(1)
                    logging.info(f"Stream encontrado com o MÉTODO ANTIGO (JS Playlist): {stream_url}")
                    return stream_url, headers_for_stremio
        
        logging.warning(f"Nenhum método de extração teve sucesso para {player_url}")
        return None, None

    except Exception as e:
        logging.error(f"Erro ao resolver stream do GoFilmes: {e}", exc_info=True)
        return None, None