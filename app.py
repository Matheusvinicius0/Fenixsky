from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import logging

# Importações dos nossos módulos
from netcine import catalog_search, search_link, search_term
import get_channels
from gofilmes import search_gofilmes, resolve_stream as resolve_gofilmes_stream
from topflix import search_topflix

# A configuração do logging permanece, mas não será usada ativamente nas rotas
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

VERSION = "0.0.7"

templates = Environment(loader=FileSystemLoader("templates"))
limiter = Limiter(key_func=get_remote_address)
rate_limit = '3/second'

app = FastAPI()

# Definição do Addon para o Stremio
MANIFEST = {
    "id": "com.fenixsky",
    "version": VERSION,
    "name": "FENIXSKY",
    "description": "Tenha o melhor dos filmes e séries com múltiplas fontes de conteúdo.",
    "logo": "https://i.imgur.com/qVgkbYn.png",
    "resources": ["catalog", "meta", "stream"],
    "types": ["tv", "movie", "series"],
    "catalogs": [
        {
            "type": "tv",
            "id": "fenixsky",
            "name": "FENIXSKY",
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
            "id": "fenixsky",
            "name": "FENIXSKY",
            "extraSupported": ["search"]
        },
        {
            "type": "series",
            "id": "fenixsky",
            "name": "FENIXSKY",
            "extraSupported": ["search"]
        }
    ],
    "idPrefixes": ["fenixsky", "tt"]
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
    
    if type == "tv":
        try:
            scrape_ = get_channels.get_stream_tv(id).get('streams', [])
        except:
            pass
            
    elif type in ["movie", "series"]:
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
        if not titles:
            return add_cors(JSONResponse(content={"streams": []}))
        
        # --- FONTE 1: NETCINE ---
        try:
            netcine_streams = search_link(id)
            if netcine_streams: scrape_.extend(netcine_streams)
        except Exception:
            pass

        # --- FONTE 2: GOFILMES ---
        try:
            gofilmes_player_options = search_gofilmes(titles, type, season, episode)
            if gofilmes_player_options:
                for option in gofilmes_player_options:
                    stream_url, stream_headers = resolve_gofilmes_stream(option['url'])
                    if stream_url:
                        scrape_.append({"name": option['name'], "url": stream_url, "behaviorHints": { "proxyHeaders": {"request": stream_headers} }})
        except Exception:
            pass

        # --- FONTE 3: TOPFLIX ---
        try:
            topflix_streams = search_topflix(titles, type, season, episode)
            if topflix_streams:
                scrape_.extend(topflix_streams)
        except Exception:
            pass

    return add_cors(JSONResponse(content={"streams": scrape_}))

@app.options("/{path:path}")
@limiter.limit(rate_limit)
async def options_handler(path: str, request: Request):
    return add_cors(Response(status_code=204))