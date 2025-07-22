from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import requests
import re
from html import unescape

# Importações dos seus módulos
from netcine import catalog_search, search_link, search_term
from gofilmes import search_gofilmes, resolve_stream as resolve_gofilmes_stream
from topflix import search_topflix

# --- Novas importações para o COS.TV ---
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

VERSION = "0.0.4"

MANIFEST = {
    "id": "com.fenixsky", "version": VERSION, "name": "FENIXSKY",
    "description": "Fontes: GoFilmes, Topflix, Netcine.",
    "logo": "https://i.imgur.com/qVgkbYn.png", "resources": ["catalog", "meta", "stream"],
    "types": ["movie", "series"], "catalogs": [
        {"type": "movie", "id": "fenixsky", "name": "FENIXSKY", "extraSupported": ["search"]},
        {"type": "series", "id": "fenixsky", "name": "FENIXSKY", "extraSupported": ["search"]}
    ], "idPrefixes": ["fenixsky", "tt"]
}

templates = Environment(loader=FileSystemLoader("templates"))
limiter = Limiter(key_func=get_remote_address)
rate_limit = '5/second'
app = FastAPI()

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(content={"error": "Too many requests"}, status_code=429)

def add_cors(response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# --- FUNÇÃO PARA STREAMTAPE ---
def resolve_streamtape_link(player_url: str):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        page_content = requests.get(player_url, headers=headers).text
        video_url_part = None
        
        match = re.search(r'<div id="robotlink" style="display:none;">(.*?)</div>', page_content)
        if match:
            video_url_part = match.group(1)
        
        if not video_url_part:
            match = re.search(r'<span id="botlink" style="display:none;">(.*?)</span>', page_content)
            if match:
                video_url_part = match.group(1)

        if not video_url_part: return None

        direct_video_url = "https:" + video_url_part
        return {"name": "Streamtape Robusto", "url": direct_video_url, "behaviorHints": {"proxyHeaders": {"request": {"User-Agent": "Mozilla/5.0", "Referer": player_url}}}}
    except Exception:
        return None

# --- FUNÇÕES PARA O COS.TV ---
def resolve_costv_link(page_url: str):
    """
    Extrai o link de vídeo direto da meta tag 'og:video' de uma página de vídeo específica do COS.TV.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        page_content = requests.get(page_url, headers=headers, timeout=10).text
        match = re.search(r'<meta property="og:video" content="(.*?)"', page_content)

        if match:
            video_url = unescape(match.group(1))
            return {"url": video_url}
        else:
            return None
    except Exception:
        return None

def search_costv_channel_with_selenium(channel_url: str, search_title: str):
    """
    Usa Selenium para carregar dinamicamente a página do canal e encontrar vídeos correspondentes.
    """
    found_videos = []
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    driver = None
    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(channel_url)

        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/videos/play/"]')))
        
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        video_cards = soup.find_all('a', href=re.compile(r'^/videos/play/\d+'))

        for card in video_cards:
            title_div = card.find('div', class_='text--primary')
            if title_div:
                video_title = title_div.get_text(strip=True)
                if search_title.lower() == video_title.lower():
                    relative_link = card.get('href')
                    full_url = f"https://cos.tv{relative_link}"
                    result = {"title": video_title, "url": full_url}
                    found_videos.append(result)
    except (TimeoutException, Exception):
        pass # Ignora erros de timeout ou outros erros do Selenium
    finally:
        if driver:
            driver.quit()
    return found_videos

@app.get("/", response_class=HTMLResponse)
@limiter.limit(rate_limit)
async def home(request: Request):
    template = templates.get_template("index.html")
    return add_cors(HTMLResponse(template.render(name=MANIFEST['name'], types=MANIFEST['types'], logo=MANIFEST['logo'], description=MANIFEST['description'], version=MANIFEST['version'])))

@app.get("/manifest.json")
@limiter.limit(rate_limit)
async def manifest(request: Request):
    return add_cors(JSONResponse(content=MANIFEST))

@app.get("/catalog/{type}/skyflix/search={query}.json")
@limiter.limit(rate_limit)
async def search(type: str, query: str, request: Request):
    catalog = catalog_search(query)
    results = [item for item in catalog if item.get("type") == type] if catalog else []
    return add_cors(JSONResponse(content={"metas": results}))

@app.get("/meta/{type}/{id}.json")
@limiter.limit(rate_limit)
async def meta(type: str, id: str, request: Request):
    return add_cors(JSONResponse(content={"meta": {}}))

@app.get("/stream/{type}/{id}.json")
@limiter.limit(rate_limit)
async def stream(type: str, id: str, request: Request):
    scrape_ = []
    
    if type in ["movie", "series"]:
        imdb_id = id.split(':')[0]
        season, episode = None, None

        if type == 'series':
            try:
                parts = id.split(':')
                season = int(parts[1])
                episode = int(parts[2])
            except (IndexError, ValueError):
                return add_cors(JSONResponse(content={"streams": []}))

        titles, _ = search_term(imdb_id)
        if not titles: return add_cors(JSONResponse(content={"streams": []}))
        
        # --- Fonte: Topflix ---
        try:
            topflix_streams = search_topflix(imdb_id, titles, type, season, episode)
            if topflix_streams: scrape_.extend(topflix_streams)
        except Exception:
            pass
        
        # --- Fonte: Netcine ---
        try:
            netcine_streams = search_link(id)
            if netcine_streams: scrape_.extend(netcine_streams)
        except Exception:
            pass

        # --- Fonte: GoFilmes ---
        try:
            gofilmes_player_options = search_gofilmes(titles, type, season, episode)
            for option in gofilmes_player_options:
                stream_url, stream_headers = resolve_gofilmes_stream(option['url'])
                if stream_url:
                    stream_name = option['name']
                    if 'mediafire.com' in stream_url: stream_name += " (Só no Navegador)"
                    stream_obj = {"name": stream_name, "url": stream_url}
                    if stream_headers:
                        stream_obj["behaviorHints"] = {"proxyHeaders": {"request": stream_headers}}
                    scrape_.append(stream_obj)
        except Exception:
            pass
        
        # --- FONTE DINÂMICA: COS.TV ---
        try:
            costv_channel_url = "https://cos.tv/channel/44965443319800832"
            search_title = ""
            if type == 'series' and season and episode:
                search_title = f"{titles[0]} Dublado Temporada {season} Episódio {episode}"
            elif type == 'movie':
                search_title = titles[0]

            if search_title:
                found_videos = search_costv_channel_with_selenium(costv_channel_url, search_title)
                for video_info in found_videos:
                    stream_data = resolve_costv_link(video_info['url'])
                    if stream_data and 'url' in stream_data:
                        stream_name = "COS.TV"
                        title_lower = video_info['title'].lower()
                        if "dublado" in title_lower:
                            stream_name += " - Dublado"
                        elif "legendado" in title_lower:
                            stream_name += " - Legendado"
                        
                        if type == 'series' and season and episode:
                            stream_name += f" S{season} E{episode}"
                        
                        scrape_.append({
                            "name": stream_name,
                            "url": stream_data['url']
                        })
        except Exception:
            pass

    return add_cors(JSONResponse(content={"streams": scrape_}))

@app.options("/{path:path}")
@limiter.limit(rate_limit)
async def options_handler(path: str, request: Request):
    return add_cors(Response(status_code=204))
