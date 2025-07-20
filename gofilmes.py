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
    # ... (Esta função está correta e permanece inalterada) ...
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
                    season_selectors = ['div.app-content--single div.card.mb-3', 'div#seasons div.season-item', 'ul.seasons-list > li.season', 'div.panel', 'div.seasons > div.season', 'div[id^="season-"]']
                    panels = []
                    for selector in season_selectors:
                        panels = soup.select(selector)
                        if panels:
                            logging.info(f"Encontrados {len(panels)} painéis de temporada com o seletor '{selector}'")
                            break
                    if not panels:
                        logging.warning(f"Nenhum painel de temporada encontrado para '{title}'.")
                        continue
                    if not (season and episode and 0 < season <= len(panels)): continue
                    selected_panel = panels[season - 1]
                    episode_links = selected_panel.select('ul.episodes-list li a[href], div.ep a[href], li a[href]')
                    if 0 < episode <= len(episode_links):
                        return [{"name": f"GoFilmes - S{season}E{episode}", "url": urljoin(base_url, episode_links[episode - 1]['href'])}]
                else:
                    player_links = soup.select('div.link a[href]')
                    if player_links:
                        return [{"name": f"GoFilmes - {link.get_text(strip=True)}", "url": urljoin(base_url, link['href'])} for link in player_links]
        except requests.RequestException as e:
            logging.error(f"Erro de requisição para '{title}': {e}")
        except Exception as e:
            logging.error(f"Erro ao processar '{title}': {e}", exc_info=True)
    logging.warning(f"Nenhuma opção de player encontrada no GoFilmes para {content_type} após todas as tentativas.")
    return []


def resolve_stream(player_url):
    """
    Recebe a URL da página do player e extrai o link do stream final.
    CORRIGIDO: Agora retorna o 'Referer' junto com os cabeçalhos.
    """
    stream_url = ''
    # Headers base que serão retornados para o Stremio usar
    headers_for_stremio = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, como Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        logging.info(f"Resolvendo stream da página do player: {player_url}")
        
        # Headers para a NOSSA requisição, que inclui o Referer do site principal
        request_headers = headers_for_stremio.copy()
        request_headers['Referer'] = 'https://gofilmess.top/'
        
        r = requests.get(player_url, headers=request_headers, timeout=10, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        iframe = soup.find('iframe')
        if iframe and iframe.has_attr('src'):
            stream_url = iframe['src']
            logging.info(f"Link do stream encontrado via IFRAME: {stream_url}")
            
            # --- AQUI ESTÁ A CORREÇÃO ---
            # Adicionamos o 'Referer' aos headers que o Stremio vai usar.
            # O servidor final (ex: Mixdrop) precisa saber que o pedido veio da página do player do GoFilmes.
            headers_for_stremio['Referer'] = player_url
            
            return stream_url, headers_for_stremio

        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                match = re.search(r'"file"\s*:\s*"([^"]+)"', script.string)
                if match:
                    stream_url = match.group(1)
                    logging.info(f"Link do stream encontrado via JS (Playlist): {stream_url}")
                    headers_for_stremio['Referer'] = player_url # Adiciona o referer aqui também
                    return stream_url, headers_for_stremio
        
    except Exception as e:
        logging.error(f"Erro ao resolver o stream de '{player_url}': {e}", exc_info=True)

    logging.warning(f"Não foi possível resolver o stream para: {player_url}")
    return stream_url, headers_for_stremio
