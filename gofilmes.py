import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
import logging
import re

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def search_gofilmes(titles, content_type, season=None, episode=None):
    """
    Busca por um filme ou série no GoFilmes e retorna o link do player.
    """
    base_url = "https://gofilmess.top"

    for title in titles:
        if not title or len(title) < 2:
            continue
            
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
                    # Tenta múltiplos seletores para encontrar os painéis das temporadas
                    panels = soup.select('div.panel')
                    if not panels:
                        panels = soup.select('div.seasons > div.season')
                    if not panels:
                        panels = soup.select('div[id^="season-"]')

                    logging.info(f"{len(panels)} painéis de temporada encontrados para '{title}'.")

                    if season is None or episode is None:
                        logging.warning("Temporada e episódio são necessários para séries.")
                        continue

                    if not panels or not (0 < season <= len(panels)):
                        logging.error(f"Temporada {season} não encontrada para o título '{title}'.")
                        continue

                    selected_panel = panels[season - 1]
                    episode_links = selected_panel.select('div.ep a[href], li a[href]')
                    logging.info(f"{len(episode_links)} episódios encontrados na temporada {season}.")

                    if 0 < episode <= len(episode_links):
                        target_link = episode_links[episode - 1]
                        return [{
                            "name": f"GoFilmes - S{season}E{episode}",
                            "url": urljoin(base_url, target_link['href'])
                        }]
                    else:
                        logging.error(f"Episódio {episode} não encontrado na temporada {season}.")
                        continue
                else:
                    player_links = soup.select('div.link a[href]')
                    if player_links:
                        return [{
                            "name": f"GoFilmes - {link.get_text(strip=True)}",
                            "url": urljoin(base_url, link['href'])
                        } for link in player_links]

        except requests.RequestException as e:
            logging.error(f"Erro de requisição para '{title}': {e}")
        except Exception as e:
            logging.error(f"Erro ao processar '{title}': {e}", exc_info=True)

    logging.warning(f"Nenhuma opção de player encontrada para '{titles}' após todas as tentativas.")
    return []


def resolve_stream(player_url):
    """
    Recebe a URL da página do player e extrai o link do stream final, incluindo a chamada de API.
    """
    stream_url = ''
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, como Gecko) Chrome/88.0.4324.96 Safari/537.36"
    }

    try:
        logging.info(f"Resolvendo stream da página do player: {player_url}")
        page_headers = headers.copy()
        page_headers['Referer'] = 'https://gofilmess.top/'
        
        r = requests.get(player_url, headers=page_headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Tentativa 1: iframe
        iframe = soup.find('iframe')
        if iframe and iframe.has_attr('src'):
            stream_url = iframe['src']
            logging.info(f"Link do stream encontrado via IFRAME: {stream_url}")
            return stream_url, headers

        # Tentativa 2: <video><source>
        video_tag = soup.find('video')
        if video_tag and video_tag.find('source') and video_tag.find('source').has_attr('src'):
            stream_url = video_tag.find('source')['src']
            logging.info(f"Link do stream encontrado via VIDEO/SOURCE: {stream_url}")
            return stream_url, headers

        scripts = soup.find_all('script')
        # Tentativa 3: script com "playlist"
        for script in scripts:
            if script.string and 'playlist' in script.string:
                match = re.search(r'"file"\s*:\s*"([^"]+)"', script.string)
                if match:
                    stream_url = match.group(1)
                    logging.info(f"Link do stream encontrado via JS (Playlist): {stream_url}")
                    return stream_url, headers

        # Tentativa 4: script com chamada de API
        for script in scripts:
            if script.string and ('fetchVideoLink' in script.string or 'apiUrl' in script.string):
                match = re.search(r'const apiUrl = `([^`]+)`;', script.string)
                if match:
                    api_url = match.group(1)
                    logging.info(f"Link de API encontrado: {api_url}")

                    api_headers = headers.copy()
                    api_headers['Referer'] = player_url # <-- A CORREÇÃO ESSENCIAL

                    api_response = requests.get(api_url, headers=api_headers, timeout=15)
                    api_response.raise_for_status()
                    stream_url = api_response.text.strip()
                    logging.info(f"Link do stream obtido da API: {stream_url}")
                    return stream_url, headers

    except Exception as e:
        logging.error(f"Erro ao resolver o stream de '{player_url}': {e}", exc_info=True)

    logging.warning(f"Não foi possível resolver o stream para: {player_url}")
    return stream_url, headers