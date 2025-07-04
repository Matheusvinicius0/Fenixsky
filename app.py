# app.py
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import logging
# --- IMPORTAÇÕES MODIFICADAS ---
from netcine import catalog_search, search_link, search_term # Importa search_term
import get_channels
from gofilmes import search_gofilmes, resolve_stream as resolve_gofilmes_stream # Importa as novas funções

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
VERSION = "0.0.2" # Versão atualizada para refletir a mudança
logger.info(f"Versão da aplicação: {VERSION}")

templates = Environment(loader=FileSystemLoader("templates"))
limiter = Limiter(key_func=get_remote_address)
rate_limit = '3/second'

app = FastAPI()

MANIFEST = {
    "id": "com.fênixsky",
    "version": VERSION,
    "name": "FÊNIXSKY",
    "description": "Tenha o melhor dos filmes e séries com Fenixsky, agora com mais fontes de conteúdo.",
    "logo": "https://i.imgur.com/qVgkbYn.png",
    "resources": ["catalog", "meta", "stream"],
    "types": ["tv", "movie", "series"],
    "catalogs": [
        # ... (sem alterações aqui)
    ],
    "idPrefixes": ["fenixsky", "tt"]
}

# ... (sem alterações nas funções add_cors, home, manifest, catalog_route, search, meta)
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
        # A lógica de metadados para filmes e séries ainda não está implementada
        m = {}
    return add_cors(JSONResponse(content={"meta": m}))


# --- ROTA DE STREAM MODIFICADA ---
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
        # 1. Buscar títulos a partir do ID do IMDb (função reutilizada do netcine.py)
        # Para séries, o id é "tt12345:1:1", então pegamos apenas a parte do IMDb ID
        imdb_id = id.split(':')[0]
        titles, _ = search_term(imdb_id) # Usamos a função para obter títulos alternativos

        if not titles:
            logger.warning(f"Não foi possível obter títulos para o IMDb ID: {imdb_id}")
            return add_cors(JSONResponse(content={"streams": []}))
        
        # --- FONTE 1: NETCINE (lógica existente) ---
        try:
            logger.info("Buscando streams no Netcine...")
            netcine_streams = search_link(id)
            if netcine_streams:
                logger.info(f"Encontrados {len(netcine_streams)} streams via Netcine.")
                scrape_.extend(netcine_streams)
            else:
                logger.warning(f"Nenhum stream encontrado no Netcine para {id}.")
        except Exception as e:
            logger.error(f"Erro ao buscar em netcine: {e}", exc_info=True)

        # --- FONTE 2: GOFILMES (nova lógica) ---
        try:
            logger.info("Buscando streams no GoFilmes...")
            # Usa os títulos obtidos do IMDb para buscar no GoFilmes
            gofilmes_player_options = search_gofilmes(titles)
            
            if gofilmes_player_options:
                logger.info(f"Encontradas {len(gofilmes_player_options)} opções de player no GoFilmes.")
                for option in gofilmes_player_options:
                    # Para cada opção de player, resolve o stream final
                    stream_url, stream_headers = resolve_gofilmes_stream(option['url'])
                    if stream_url:
                        scrape_.append({
                            "name": option['name'],
                            "url": stream_url,
                            "behaviorHints": {
                                # "notWebReady": True, # Ative se o link não for direto (MP4, etc.)
                                "proxyHeaders": {"request": stream_headers}
                            }
                        })
            else:
                logger.warning(f"Nenhuma opção de player encontrada no GoFilmes para os títulos fornecidos.")
        except Exception as e:
            logger.error(f"Erro ao buscar no GoFilmes: {e}", exc_info=True)

    if not scrape_:
        logger.warning(f"Nenhum stream encontrado para {type}/{id} após buscar em todas as fontes.")

    return add_cors(JSONResponse(content={"streams": scrape_}))

@app.options("/{path:path}")
@limiter.limit(rate_limit)
async def options_handler(path: str, request: Request):
    return add_cors(Response(status_code=204))
