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
from gofilmes import search_gofilmes, resolve_stream

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Atualizamos a versão para refletir as novas funcionalidades
VERSION = "0.0.4"
logger.info(f"Versão da aplicação: {VERSION}")

templates = Environment(loader=FileSystemLoader("templates"))
limiter = Limiter(key_func=get_remote_address)
rate_limit = '3/second'

app = FastAPI()

# Definição do Addon para o Stremio
MANIFEST = {
    "id": "com.fenixsky",
    "version": VERSION,
    "name": "FENIXSKY",
    "description": "Tenha o melhor dos filmes e séries com Fenixsky, agora com múltiplas fontes de conteúdo e suporte a séries.",
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
    logger.info(f"Solicitação de stream para tipo: '{type}', id: '{id}'")

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
                logger.info(f"Série detectada: Temporada {season}, Episódio {episode}")
            except (IndexError, ValueError):
                logger.error("ID de série mal formatado. Esperado 'imdb:temporada:episódio'.")
                return add_cors(JSONResponse(content={"streams": []}))

        titles, _ = search_term(imdb_id)

        if not titles:
            logger.warning(f"Não foi possível obter títulos para o IMDb ID: {imdb_id}")
            return add_cors(JSONResponse(content={"streams": []}))
        
        # --- FONTE 1: NETCINE ---
        try:
            logger.info("Buscando streams no Netcine...")
            netcine_streams = search_link(id)
            if netcine_streams:
                logger.info(f"Encontrados {len(netcine_streams)} streams via Netcine.")
                scrape_.extend(netcine_streams)
        except Exception as e:
            logger.error(f"Erro ao buscar em netcine: {e}", exc_info=True)

        # --- FONTE 2: GOFILMES ---
        try:
            logger.info("Buscando streams no GoFilmes...")
            gofilmes_player_options = search_gofilmes(titles, type, season, episode)
            
            if gofilmes_player_options:
                logger.info(f"Encontradas {len(gofilmes_player_options)} opções de player no GoFilmes.")
                for option in gofilmes_player_options:
                    stream_url, stream_headers = resolve_stream(option['url'])
                    if stream_url:
                        scrape_.append({
                            "name": option['name'],
                            "url": stream_url,
                            "behaviorHints": { "proxyHeaders": {"request": stream_headers} }
                        })
            else:
                logger.warning(f"Nenhuma opção de player encontrada no GoFilmes.")
        except Exception as e:
            logger.error(f"Erro ao buscar no GoFilmes: {e}", exc_info=True)

    if not scrape_:
        logger.warning(f"Nenhum stream encontrado para {type}/{id} após buscar em todas as fontes.")

    return add_cors(JSONResponse(content={"streams": scrape_}))

@app.options("/{path:path}")
@limiter.limit(rate_limit)
async def options_handler(path: str, request: Request):
    return add_cors(Response(status_code=204))
