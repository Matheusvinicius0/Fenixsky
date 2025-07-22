from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import requests
import re
from html import unescape

# Importações dos seus módulos (sem as de COS.TV)
from netcine import catalog_search, search_link, search_term
from gofilmes import search_gofilmes, resolve_stream as resolve_gofilmes_stream
from topflix import search_topflix

VERSION = "0.0.4" # A versão pode ser atualizada se desejar

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

# --- FUNÇÃO PARA STREAMTAPE (mantida pois pode ser útil para outras fontes) ---
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
        
        # --- Bloco do COS.TV foi removido daqui ---

    return add_cors(JSONResponse(content={"streams": scrape_}))

@app.options("/{path:path}")
@limiter.limit(rate_limit)
async def options_handler(path: str, request: Request):
    return add_cors(Response(status_code=204))
