# gofilmes.py
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
import logging
import re # Importa o módulo de Expressões Regulares

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def search_gofilmes(titles):
    """
    Busca por um filme no gofilmes e retorna TODOS os links de player encontrados.
    """
    logging.info(f"Iniciando busca no GoFilmes com os títulos: {titles}")
    
    base_url = "https://gofilmess.top"

    for title in titles:
        search_slug = title.replace(' ', '-').lower()
        url = f"{base_url}/{quote(search_slug)}"
        
        logging.info(f"Tentando buscar em: {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            logging.info(f"'{title}' - Status da resposta: {response.status_code}")

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                player_options = []
                
                link_divs = soup.find_all('div', class_='link')

                if not link_divs:
                    logging.warning(f"Página encontrada para '{title}', mas nenhuma <div class='link'> foi encontrada.")
                    continue

                logging.info(f"Encontradas {len(link_divs)} divs com a classe 'link'. Procurando players...")
                
                for div in link_divs:
                    player_link = div.find('a', href=True)
                    if player_link:
                        player_url = player_link.get('href')
                        player_name = player_link.get_text(strip=True)
                        full_player_url = urljoin(base_url, player_url)
                        
                        player_options.append({
                            "name": f"GoFilmes - {player_name}",
                            "url": full_player_url
                        })

                if player_options:
                    logging.info(f"SUCESSO! {len(player_options)} opções de player encontradas para '{title}'.")
                    return player_options
            
        except requests.RequestException as e:
            logging.error(f"Erro de requisição para o título '{title}': {e}")
        except Exception as e:
            logging.error(f"Erro excepcional ao buscar por '{title}': {e}", exc_info=True)
            
    logging.warning("Nenhuma opção de player encontrada no GoFilmes após todas as tentativas.")
    return []

def resolve_stream(player_url):
    """
    Recebe a URL da página do player do GoFilmes e extrai o link do stream final.
    --- VERSÃO FINAL E MAIS PODEROSA ---
    """
    stream_url = ''
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, como Gecko) Chrome/88.0.4324.96 Safari/537.36"}
    
    try:
        logging.info(f"Resolvendo stream da página do player: {player_url}")
        headers.update({'Referer': 'https://gofilmess.top/'})
        
        r = requests.get(player_url, headers=headers, timeout=10, allow_redirects=True)
        soup = BeautifulSoup(r.text, 'html.parser')

        # --- LÓGICA DE BUSCA MELHORADA ---
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

        # Tentativa 3: Procurar o link dentro de uma tag <script> usando Regex
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'playlist' in script.string:
                # Usa Regex para encontrar o valor do campo "file"
                match = re.search(r'"file"\s*:\s*"([^"]+)"', script.string)
                if match:
                    stream_url = match.group(1) # Pega o primeiro grupo capturado (o URL)
                    logging.info(f"Link do stream encontrado via JAVASCRIPT/REGEX: {stream_url}")
                    return stream_url, headers
        
        logging.warning("Nenhuma das tentativas (Iframe, Vídeo, JavaScript) encontrou um link de stream.")

    except Exception as e:
        logging.error(f"Erro ao resolver o stream de '{player_url}': {e}", exc_info=True)
        
    return stream_url, headers