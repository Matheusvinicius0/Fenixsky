from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import logging
from netcine import catalog_search, search_link
import os
from urllib.parse import quote_plus
import get_channels

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
VERSION = "1.0.7-final"
logger.info(f"Versão da aplicação: {VERSION}")

templates = Environment(loader=FileSystemLoader("templates"))
limiter = Limiter(key_func=get_remote_address)
rate_limit = '3/second'

app = FastAPI()

MANIFEST = {
    "id": "com.skyflix",
    "version": VERSION,
    "name": "SKYFLIX",
    "description": "Tenha o melhor dos filmes e séries com Skyflix",
    "logo": "https://i.imgur.com/qVgkbYn.png",
    "resources": ["catalog", "meta", "stream"],
    "types": ["tv", "movie", "series"],
    "catalogs": [
        {
            "type": "tv",
            "id": "skyflix",
            "name": "SKYFLIX",
            "extra": [
                {
                    "name": "genre",
                    "options": [
                        "Abertos", "Reality", "Esportes", "NBA", "PPV", "Paramount plus",
                        "DAZN", "Nosso Futebol", "UFC", "Combate", "NFL", "Documentarios",
                        "Infantil", "Filmes e Series", "Telecine", "HBO", "Cine Sky",
                        "Noticias", "Musicas", "Variedades", "Cine 24h", "Desenhos",
                        "Series 24h", "Religiosos", "4K", "Radios"
                    ],
                    "isRequired": False
                }
            ]
        },
        {
            "type": "movie",
            "id": "skyflix",
            "name": "SKYFLIX",
            "extraSupported": ["search"]
        },
        {
            "type": "series",
            "id": "skyflix",
            "name": "SKYFLIX",
            "extraSupported": ["search"]
        }
    ],
    "idPrefixes": ["skyflix", "tt"]
}

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(content={"error": "Too many requests"}, status_code=429)

def add_cors(response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.get("/", response_class=HTMLResponse)
@limiter.limit(rate_limit)
async def home(request: Request):
    template = templates.get_template("index.html")
    response = HTMLResponse(template.render(
        name=MANIFEST['name'],
        types=MANIFEST['types'],
        logo=MANIFEST['logo'],
        description=MANIFEST['description'],
        version=MANIFEST['version']
    ))
    return add_cors(response)

@app.get("/manifest.json")
@limiter.limit(rate_limit)
async def manifest(request: Request):
    return add_cors(JSONResponse(content=MANIFEST))

@app.get("/catalog/{type}/{id}.json")
@limiter.limit(rate_limit)
async def catalog_route(type: str, id: str, request: Request):    
    if type == 'tv':
        try: 
            api = get_channels.get_api()       
            itens = [canal for canal in api.list_channels('Abertos')]
        except:
            itens = []
    else:
        itens = []
    return add_cors(JSONResponse(content={"metas": itens}))

@app.get("/catalog/{type}/skyflix/search={query}.json")
@limiter.limit(rate_limit)
async def search(type: str, query: str, request: Request):
    catalog = catalog_search(query)
    results = [item for item in catalog if item.get("type") == type] if catalog else []
    return add_cors(JSONResponse(content={"metas": results}))

@app.get("/meta/{type}/{id}.json")
@limiter.limit(rate_limit)
async def meta(type: str, id: str, request: Request):
    if type == 'tv':
        try:
            m = get_channels.get_meta_tv(id)
        except:
            m = {}
    else:
        m = {}
    return add_cors(JSONResponse(content={"meta": m}))

@app.get("/stream/{type}/{id}.json")
@limiter.limit(rate_limit)
async def stream(type: str, id: str, request: Request):
    scrape_ = []
    logger.info(f"Solicitação de stream para tipo: '{type}', id: '{id}'")

    if type == "tv":
        try:
            scrape_ = get_channels.get_stream_tv(id).get('streams', [])
        except:
            pass
    elif type in ["movie", "series"]:
        try:
            netcine_streams = search_link(id)
            if netcine_streams:
                logger.info(f"Encontrados {len(netcine_streams)} streams via Netcine.")
                scrape_.extend(netcine_streams)
            else:
                logger.warning(f"Nenhum stream encontrado no Netcine para {id}.")
        except Exception as e:
            logger.error(f"Erro ao buscar em netcine: {e}", exc_info=True)
            
    if not scrape_:
        logger.warning(f"Nenhum stream encontrado para {type}/{id}")

    return add_cors(JSONResponse(content={"streams": scrape_}))

@app.options("/{path:path}")
@limiter.limit(rate_limit)
async def options_handler(path: str, request: Request):
    return add_cors(Response(status_code=204))