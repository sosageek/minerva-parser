import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


logger = logging.getLogger("minerva-parser.frontend")

BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://backend:8003")
REQUEST_TIMEOUT: float = float(os.environ.get("REQUEST_TIMEOUT", "60"))

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_STATIC_DIR = Path(__file__).resolve().parent / "static"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

app = FastAPI(
    title="Minerva Parser Frontend",
    description="input URL, evaluation",
)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def _extract_domain(url: str) -> str | None:
    """
    Estrae il netloc da un URL se ben formato e con schema http/https valido.

    args:
        url: stringa contenente l'URL da analizzare.

    returns:
        Il netloc dell'URL se lo schema è http o https e il netloc è presente;
        altrimenti None.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None                            #scarta scheme malformati, backend risponde 400
    return parsed.netloc


async def _fetch_domains(client: httpx.AsyncClient) -> list[str]:
    """
    Recupera i domini supportati dal backend.

    Args:
        client: httpx.AsyncClient usato per effettuare la richiesta asincrona.

    Returns:
        Lista di stringhe con i domini (netloc) restituiti dal backend, o una
        lista vuota se la richiesta non risponde o fallisce.
    """
    try:
        resp = await client.get(f"{BACKEND_URL}/domains")
        resp.raise_for_status()
        return resp.json().get("domains", [])       #lista netloc
    except httpx.HTTPError as err:
        logger.warning("impossibile recuperare /domains: %s", err)
        return []


async def _fetch_full_gs(
    client: httpx.AsyncClient,
    domains: list[str],
) -> dict[str, list[dict]]:
    """
    Recupera la mappatura dei domini alle voci gold standard per popolare il dropdown a cascata.

    Args:
        client: httpx.AsyncClient utilizzato per effettuare le richieste HTTP.
        domains: lista di domini per cui richiedere il gold standard.

    Returns:
        dict[str, list[dict]]: dizionario che mappa ogni dominio a una lista di elementi
        contenenti le chiavi "url" e "title". In caso di errore HTTP per un dominio,
        quel dominio viene restituito con una lista vuota.
    """
    gs: dict[str, list[dict]] = {}
    for domain in domains:                      # home alla prima visita ci metteva il triplo se parallel (Mazz)
        try:
            resp = await client.get(
                f"{BACKEND_URL}/full_gold_standard",
                params={"domain": domain},
            )
            resp.raise_for_status()
            entries = resp.json().get("gold_standard", [])
            gs[domain] = [
                {"url": e["url"], "title": e["title"]} for e in entries
            ]
        except httpx.HTTPError as err:
            logger.warning("GS non disponibile per %s: %s", domain, err)
            gs[domain] = []
    return gs


# async def _fetch_full_gs_parallel(
#     client: httpx.AsyncClient,
#     domains: list[str],
# ) -> dict[str, list[dict]]:
# 
#     import asyncio
#     coros = [
#         client.get(f"{BACKEND_URL}/full_gold_standard", params={"domain": d})
#         for d in domains
#     ]
#     resps = await asyncio.gather(*coros, return_exceptions=True)
#     gs: dict[str, list[dict]] = {}
#     for domain, resp in zip(domains, resps):
#         if isinstance(resp, Exception) or resp.status_code >= 400:
#             gs[domain] = []
#             continue
#         entries = resp.json().get("gold_standard", [])
#         gs[domain] = [{"url": e["url"], "title": e["title"]} for e in entries]
#     return gs


async def _fetch_gs_entry(
    client: httpx.AsyncClient,
    url: str,
) -> dict | None:
    """
    Recupera l'entry del gold standard per un URL specifico.

    Args:
        client: httpx.AsyncClient utilizzato per effettuare le richieste HTTP.
        url: stringa contenente l'URL per cui recuperare l'entry del gold standard.

    Returns:
        dict | None: L'entry del gold standard se trovata, altrimenti None.
    """
                       #ritorna None se l'URL non in GS o se il backend risponde con errore
    try:
        resp = await client.get(
            f"{BACKEND_URL}/gold_standard",
            params={"url": url},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as err:
        logger.warning("GS lookup fallito per %s: %s", url, err)
        return None


async def _fetch_parse(
    client: httpx.AsyncClient,
    url: str,
) -> tuple[dict | None, str | None]:
    """
    Recupera il risultato del parse per un URL specifico.

    Args:
        client: httpx.AsyncClient utilizzato per effettuare le richieste HTTP.
        url: stringa contenente l'URL per cui recuperare il risultato del parse.

    Returns:
        tuple[dict | None, str | None]: Una tupla contenente il risultato del parse (se trovato) e un messaggio di errore (se presente).
    """
    try:
        resp = await client.get(f"{BACKEND_URL}/parse", params={"url": url})
        if resp.status_code >= 400:
            # Su 5xx, proxy potrebbero ritornare HTML invece di JSON
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            return None, f"backend {resp.status_code}: {detail}"
        return resp.json(), None
    except httpx.HTTPError as err:
        logger.warning("parse fallito per %s: %s", url, err)
        return None, f"backend irraggiungibile: {err}"

    #  provato il retry 502 503
    # ma 502 capita solo durante lifespan del backend (carica i GS dal disco, 10s ). (Mazz)


async def _fetch_evaluate(
    client: httpx.AsyncClient,
    parsed_text: str,
    gold_text: str,
) -> dict | None:                   #chiama post /evaluate da backend
    """
    Valuta il testo parsato rispetto al testo gold standard.

    Args:
        client: httpx.AsyncClient utilizzato per effettuare le richieste HTTP.
        parsed_text: stringa contenente il testo parsato.
        gold_text: stringa contenente il testo gold standard.

    Returns:
        dict | None: Il risultato della valutazione se la chiamata ha successo, altrimenti None.
    """
    try:
        resp = await client.post(
            f"{BACKEND_URL}/evaluate",
            json={"parsed_text": parsed_text, "gold_text": gold_text},
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as err:
        logger.warning("evaluate fallito: %s", err)
        return None


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    url: str | None = Query(default=None, description="URL da parsare"),   #file html
) -> HTMLResponse:
    """
    Pagina principale
    Args:
        request: oggetto Request di Starlette/FastAPI.
        url: URL da parsare; se non fornito, viene renderizzato il form iniziale con il dropdown dei domini Google Sheets.
    Returns:
        HTMLResponse con il template "index.html" popolato con:
          - domains: elenco domini disponibili,
          - full_gs: elenco completo di Google Sheets,
          - url: URL fornito o stringa vuota,
          - parse_result: risultato del parsing se eseguito,
          - gs_entry: voce Google Sheets trovata per l'URL,
          - evaluation: risultato della valutazione se disponibile,
          - error: messaggio di errore in caso di URL malformato o parsing fallito.
    """

    # senza url: renderizza form con il dropdown GS
    #con url esegue il parse

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        domains = await _fetch_domains(client)
        full_gs = await _fetch_full_gs(client, domains)

        context: dict = {
            "request": request,
            "domains": domains,
            "full_gs": full_gs,
            "url": url or "",
            "parse_result": None,
            "gs_entry": None,
            "evaluation": None,
            "error": None,
        }

        if not url:
            return templates.TemplateResponse(request, "index.html", context)

        domain = _extract_domain(url)
        if domain is None:
            context["error"] = "URL malformato: serve uno scheme http/https e un netloc valido"
            return templates.TemplateResponse(request, "index.html", context)

        parse_result, err = await _fetch_parse(client, url)
        if parse_result is None:
            context["error"] = err
            return templates.TemplateResponse(request, "index.html", context)
        context["parse_result"] = parse_result

        gs_entry = await _fetch_gs_entry(client, url)
        if gs_entry is not None:
            context["gs_entry"] = gs_entry
            context["evaluation"] = await _fetch_evaluate(
                client,
                parse_result["parsed_text"],
                gs_entry["gold_text"],
            )

        return templates.TemplateResponse(request, "index.html", context)
