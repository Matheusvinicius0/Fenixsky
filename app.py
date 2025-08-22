from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import requests
import re
from html import unescape
import os
import json
import logging

# Importações dos seus módulos
from netcine import catalog_search, search_link, search_term
from gofilmes import search_gofilmes, resolve_stream as resolve_gofilmes_stream

VERSION = "0.0.1"
MANIFEST = {
    "id": "com.fenixsky", "version": VERSION, "name": "FENIXSKY",
    "description": "Sua fonte para filmes e séries.",
    "logo": "https://i.imgur.com/LVNrWUD.png", "resources": ["catalog", "meta", "stream"],
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

        # --- Fonte: JSON Local ---
        json_path = os.path.join("Json", f"{imdb_id}.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)

                if local_data.get('id') == imdb_id:
                    if type == 'series' and season and episode:
                        for item in local_data.get('streams', []):
                            if item.get('temporada') == season and item.get('episodio') == episode:
                                scrape_.extend(item.get('streams', []))
                                break
                    elif type == 'movie':
                        scrape_.extend(local_data.get('streams', []))

            except Exception as e:
                logging.error(f"Erro ao ler JSON de {json_path}: {e}")

        titles, _ = search_term(imdb_id)
        if not titles: return add_cors(JSONResponse(content={"streams": []}))

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
        
    return add_cors(JSONResponse(content={"streams": scrape_}))

@app.options("/{path:path}")
@limiter.limit(rate_limit)
async def options_handler(path: str, request: Request):
    return add_cors(Response(status_code=204))
