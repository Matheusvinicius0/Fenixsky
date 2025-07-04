import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
import logging
import re

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def search_gofilmes(titles, content_type, season=None, episode=None):
    """
    Busca por um filme ou série no gofilmes e retorna o link do player para o item específico.
    (Esta função está correta e não precisa de alterações)
    """
    logging.info(f"Iniciando busca no GoFilmes para tipo '{content_type}' com os títulos: {titles}")
    
    base_url = "https://gofilmess.top"

    if content_type == 'series':
        path = 'series'
        selector = 'div.ep a[href]'
    else: 
        path = ''
        selector = 'div.link a[href]'

    for title in titles:
        search_slug = title.replace('.', '').replace(' ', '-').lower()

        if path:
            url = f"{base_url}/{path}/{quote(search_slug)}"
        else:
            url = f"{base_url}/{quote(search_slug)}"
        
        logging.info(f"Tentando buscar em: {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            logging.info(f"'{title}' ({path or 'filmes'}) - Status da resposta: {response.status_code}")

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                player_options = []
                
                player_links = soup.select(selector)

                if not player_links:
                    logging.warning(f"Página encontrada, mas nenhum link encontrado com o seletor '{selector}'.")
                    continue

                logging.info(f"Encontrados {len(player_links)} links com o seletor '{selector}'.")
                
                if content_type == 'series':
                    if episode and 0 < episode <= len(player_links):
                        target_link = player_links[episode - 1]
                        logging.info(f"Episódio alvo {episode} encontrado.")
                        player_options.append({
                            "name": f"GoFilmes - S{season}E{episode}",
                            "url": urljoin(base_url, target_link.get('href'))
                        })
                else: 
                    for link in player_links:
                        player_options.append({
                            "name": f"GoFilmes - {link.get_text(strip=True)}",
                            "url": urljoin(base_url, link.get('href'))
                        })

                if player_options:
                    logging.info(f"SUCESSO! {len(player_options)} opções de player prontas para '{title}'.")
                    return player_options
            
        except requests.RequestException as e:
            logging.error(f"Erro de requisição para o título '{title}': {e}")
        except Exception as e:
            logging.error(f"Erro excepcional ao buscar por '{title}': {e}", exc_info=True)
            
    logging.warning(f"Nenhuma opção de player encontrada no GoFilmes para {content_type} após todas as tentativas.")
    return []

def resolve_stream(player_url):
    """
    Recebe a URL da página do player do GoFilmes e extrai o link do stream final.
    """
    stream_url = ''
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, como Gecko) Chrome/88.0.4324.96 Safari/537.36"}
    
    try:
        logging.info(f"Resolvendo stream da página do player: {player_url}")
        page_headers = headers.copy()
        # O Referer para a página do player deve ser a página principal do site
        page_headers.update({'Referer': 'https://gofilmess.top/'})
        
        r = requests.get(player_url, headers=page_headers, timeout=10, allow_redirects=True)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Tentativa 1: Procurar por um iframe
        iframe = soup.find('iframe')
        if iframe and iframe.has_attr('src'):
            stream_url = iframe['src']
            logging.info(f"Link do stream encontrado via IFRAME: {stream_url}")
            return stream_url, headers

        # Tentativa 2: Procurar por uma tag <video> com <source>
        video_tag = soup.find('video')
        if video_tag:
            source_tag = video_tag.find('source')
            if source_tag and source_tag.has_attr('src'):
                stream_url = source_tag['src']
                logging.info(f"Link do stream encontrado via VIDEO/SOURCE: {stream_url}")
                return stream_url, headers

        # Tentativa 3: Procurar o link do JW Player dentro de uma tag <script>
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'playlist' in script.string:
                match = re.search(r'"file"\s*:\s*"([^"]+)"', script.string)
                if match:
                    stream_url = match.group(1)
                    logging.info(f"Link do stream encontrado via JAVASCRIPT/REGEX (JW Player): {stream_url}")
                    return stream_url, headers
        
        # Tentativa 4: Extrair um link de API do JavaScript e chamar essa API
        api_url = None
        for script in scripts:
            if script.string and 'fetchVideoLink' in script.string:
                match = re.search(r'const apiUrl = `([^`]+)`;', script.string)
                if match:
                    api_url = match.group(1)
                    logging.info(f"Link de API encontrado: {api_url}")
                    
                    # --- CORREÇÃO: Adicionar o 'Referer' na chamada da API ---
                    api_headers = headers.copy()
                    api_headers['Referer'] = player_url # O referer é a própria página do player
                    
                    # Faz a chamada à API encontrada com os cabeçalhos corretos
                    api_response = requests.get(api_url, headers=api_headers, timeout=15)
                    api_response.raise_for_status()
                    
                    stream_url = api_response.text.strip()
                    logging.info(f"Link do stream obtido da API: {stream_url}")
                    return stream_url, headers

    except Exception as e:
        logging.error(f"Erro ao resolver o stream de '{player_url}': {e}", exc_info=True)
        
    return stream_url, headers
