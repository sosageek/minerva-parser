import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


logger = logging.getLogger("minerva-parser.frontend")

BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://backend:8003")
REQUEST_TIMEOUT: float = float(os.environ.get("REQUEST_TIMEOUT", "60"))
# è la stessa variabile che compose passa a backend e ollama. la leggo di qui
# invece di scrivere il nome del modello dentro al template: se un domani
# cambia modello, cambia in un posto solo e la home non racconta bugie
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "qwen3:4b")

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_STATIC_DIR = Path(__file__).resolve().parent / "static"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

app = FastAPI(
    title="Minerva Parser Frontend",
    description="Home, Parser & Evaluation, Gold Standard Builder, Stats",
)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

TEAM: list[dict] = [
    {"nome": "Cillo Valentina", "matricola": 2109528},
    {"nome": "Lobello Gabriele", "matricola": 2115145},
    {"nome": "Mazzocco Marco", "matricola": 2136444},
]

# il netloc da solo dice poco a chi apre la home, quindi in lista ci metto
# accanto il nome per esteso. è solo presentazione: i domini validi restano
# quelli che risponde il backend su /domains, se ne aggiunge uno che qui non
# ho etichettato viene fuori il netloc e amen
DOMAIN_LABELS: dict[str, str] = {
    "en.wikipedia.org": "Wikipedia",
    "thebookerprizes.com": "The Booker Prizes",
    "www.meteoam.it": "MeteoAM",
    "www.nps.gov": "National Park Service",
}


def _extract_domain(url: str) -> str | None:
    """
    Estrae il netloc da un URL se ben formato e con schema http/https valido.

    Args:
        url: stringa contenente l'URL da analizzare.

    Returns:
        Il netloc dell'URL se lo schema è http o https e il netloc è presente;
        altrimenti None.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None 
    return parsed.netloc


def _error_detail(resp: httpx.Response) -> str:
    """
    Estrae un messaggio d'errore leggibile da una risposta non-2xx del backend.

    Args:
        resp: risposta HTTP del backend con status code >= 400.

    Returns:
        Il campo "detail" se la risposta è JSON, altrimenti il body grezzo.
    """
    try:
        return resp.json().get("detail", resp.text)
    except ValueError:
        return resp.text


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
        return resp.json().get("domains", [])
    except httpx.HTTPError as err:
        logger.warning("impossibile recuperare /domains: %s", err)
        return []


async def _fetch_status(client: httpx.AsyncClient) -> dict | None:
    """
    Recupera lo stato di backend/database/ollama.

    Args:
        client: httpx.AsyncClient usato per effettuare la richiesta asincrona.

    Returns:
        dict con le chiavi "backend", "database", "ollama" (valori "ok"/"error"),
        oppure None se il backend stesso non è raggiungibile.
    """
    try:
        resp = await client.get(f"{BACKEND_URL}/status")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as err:
        logger.warning("impossibile recuperare /status: %s", err)
        return None


async def _fetch_gold_standard_urls(
    client: httpx.AsyncClient,
    domain: str,
) -> list[str]:
    """
    Recupera solo gli URL del Gold Standard per un dominio (senza html/gold text)

    Args:
        client: httpx.AsyncClient usato per effettuare la richiesta asincrona.
        domain: dominio per cui filtrare gli URL.

    Returns:
        Lista di URL, o lista vuota in caso di errore.
    """
    try:
        resp = await client.get(
            f"{BACKEND_URL}/gold_standard_urls",
            params={"domain": domain},
        )
        resp.raise_for_status()
        return resp.json().get("gold_standard_urls", [])
    except httpx.HTTPError as err:
        logger.warning("gold_standard_urls fallito per %s: %s", domain, err)
        return []


async def _fetch_gs_urls_by_domain(
    client: httpx.AsyncClient,
    domains: list[str],
) -> dict[str, list[str]]:
    """
    Costruisce la mappa dominio -> lista di URL GS, usata dal cascading select.

    Args:
        client: httpx.AsyncClient usato per effettuare le richieste asincrone.
        domains: lista di domini supportati.

    Returns:
        dict[str, list[str]] con un URL grezzo (senza titolo) per entry.
    """
    return {domain: await _fetch_gold_standard_urls(client, domain) for domain in domains}


async def _fetch_gold_standard(
    client: httpx.AsyncClient,
    url: str,
) -> dict | None:
    """
    Recupera l'entry del Gold Standard per un URL specifico, se esiste.

    Args:
        client: httpx.AsyncClient usato per effettuare la richiesta asincrona.
        url: URL per cui cercare l'entry.

    Returns:
        dict con l'entry (url, domain, title, html_text, gold_text) se trovata,
        None se l'URL non è nel Gold Standard o se il backend non risponde.
    """
    try:
        resp = await client.get(f"{BACKEND_URL}/gold_standard", params={"url": url})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as err:
        logger.warning("gold_standard lookup fallito per %s: %s", url, err)
        return None


async def _do_parse(
    client: httpx.AsyncClient,
    url: str,
    local: bool,
) -> tuple[dict | None, str | None]:
    """
    Esegue POST /parse in modalità Live o Local.

    Args:
        client: httpx.AsyncClient usato per effettuare la richiesta asincrona.
        url: URL da parsare.
        local: True per leggere solo l'HTML già salvato nel database, senza rete.

    Returns:
        tuple (ParseOutput come dict, None) in caso di successo,
        oppure (None, messaggio d'errore leggibile) in caso di fallimento.
    """
    try:
        resp = await client.post(
            f"{BACKEND_URL}/parse",
            json={"url": url, "local": local},
        )
        if resp.status_code >= 400:
            return None, f"backend {resp.status_code}: {_error_detail(resp)}"
        return resp.json(), None
    except httpx.HTTPError as err:
        logger.warning("parse fallito per %s: %s", url, err)
        return None, f"backend irraggiungibile: {err}"


async def _do_evaluate(
    client: httpx.AsyncClient,
    parsed_text: str,
    gold_text: str,
) -> dict | None:
    """
    Calcola le metriche deterministiche tra parsed_text e gold_text.

    Args:
        client: httpx.AsyncClient usato per effettuare la richiesta asincrona.
        parsed_text: testo estratto dal parser.
        gold_text: testo di riferimento.

    Returns:
        dict con token_level_eval e x_eval, oppure None se la chiamata fallisce.
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


async def _do_evaluate_judge(
    client: httpx.AsyncClient,
    parsed_text: str,
    gold_text: str,
) -> tuple[dict | None, str | None]:
    """
    Richiede la valutazione al modello LLM judge

    Args:
        client: httpx.AsyncClient usato per effettuare la richiesta asincrona.
        parsed_text: testo estratto dal parser.
        gold_text: testo di riferimento.

    Returns:
        tuple (JudgeEvaluation come dict, None) in caso di successo,
        oppure (None, messaggio d'errore leggibile) in caso di fallimento.
    """
    try:
        resp = await client.post(
            f"{BACKEND_URL}/evaluate_judge",
            json={"parsed_text": parsed_text, "gold_text": gold_text},
        )
        if resp.status_code >= 400:
            return None, f"backend {resp.status_code}: {_error_detail(resp)}"
        return resp.json(), None
    except httpx.HTTPError as err:
        logger.warning("evaluate_judge fallito: %s", err)
        return None, f"backend irraggiungibile: {err}"


async def _add_gold_standard(
    client: httpx.AsyncClient,
    url: str,
    gold_text: str,
) -> dict:
    """
    Salva o aggiorna il Gold Standard per una URL.

    Args:
        client: httpx.AsyncClient usato per effettuare la richiesta asincrona.
        url: URL della web resource già salvata.
        gold_text: testo gold da salvare.

    Returns:
        dict {"status": "ok"|"error"}; "error" anche se il backend è
        irraggiungibile, così il template non deve distinguere i due casi.
    """
    try:
        resp = await client.post(
            f"{BACKEND_URL}/add_gold_standard",
            json={"url": url, "gold_text": gold_text},
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as err:
        logger.warning("add_gold_standard fallito per %s: %s", url, err)
        return {"status": "error"}


async def _delete_gold_standard(client: httpx.AsyncClient, url: str) -> dict:
    """Elimina solo il Gold Standard di una URL, lasciando la web resource."""
    try:
        resp = await client.request(
            "DELETE",
            f"{BACKEND_URL}/gold_standard",
            json={"url": url},
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as err:
        logger.warning("delete gold_standard fallito per %s: %s", url, err)
        return {"status": "error"}


async def _delete_web_resource(client: httpx.AsyncClient, url: str) -> dict:
    """Elimina la web resource e, a cascata, l'eventuale Gold Standard collegato."""
    try:
        resp = await client.request(
            "DELETE",
            f"{BACKEND_URL}/web_resource",
            json={"url": url},
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as err:
        logger.warning("delete web_resource fallito per %s: %s", url, err)
        return {"status": "error"}


async def _fetch_db_stats(
    client: httpx.AsyncClient,
) -> tuple[dict | None, str | None]:
    """
    Recupera conteggi e medie persistite per dominio.

    Args:
        client: httpx.AsyncClient usato per effettuare la richiesta asincrona.

    Returns:
        tuple (DBStats come dict, None) in caso di successo,
        oppure (None, messaggio d'errore leggibile) in caso di fallimento.
    """
    try:
        resp = await client.get(f"{BACKEND_URL}/db_stats")
        resp.raise_for_status()
        return resp.json(), None
    except httpx.HTTPError as err:
        logger.warning("db_stats fallito: %s", err)
        return None, f"backend irraggiungibile: {err}"


def _gold_standard_defaults(url: str = "", mode: str = "live") -> dict:
    """Contesto di default per gold_standard.html, sovrascritto dalle singole route."""
    return {
        "url": url,
        "mode": mode,
        "domains": [],
        "selected_domain": None,
        "gs_urls": [],
        "fetch_result": None,
        "fetch_error": None,
        "existing_gold": None,
        "save_status": None,
        "delete_status": None,
    }


async def _load_gs_index(
    client: httpx.AsyncClient,
    context: dict,
    domain: str | None = None,
) -> None:
    """
    Popola il contesto con i domini supportati e con gli URL già nel Gold Standard.

    Viene chiamata da tutte le route della pagina, non solo dalla GET, così la
    lista delle entry esistenti resta visibile anche dopo un salvataggio o una
    cancellazione. Se il dominio non arriva o non è fra quelli supportati si
    ricade sul primo disponibile, per non presentare una tendina vuota al primo
    accesso.

    Args:
        client: httpx.AsyncClient usato per effettuare le richieste asincrone.
        context: contesto del template, modificato sul posto.
        domain: dominio scelto dall'utente, oppure None.
    """
    domains = await _fetch_domains(client)
    context["domains"] = domains

    if domain not in domains:
        domain = domains[0] if domains else None

    context["selected_domain"] = domain
    context["gs_urls"] = await _fetch_gold_standard_urls(client, domain) if domain else []



@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """
    Home: navigazione, membri del team, domini supportati e stato dei servizi.
    """
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        domains = await _fetch_domains(client)
        status = await _fetch_status(client)

    context = {
        "request": request,
        "active_page": "home",
        "domains": [{"host": d, "label": DOMAIN_LABELS.get(d, d)} for d in domains],
        "status": status,
        "team": TEAM,
        "judge_model": OLLAMA_MODEL,
    }
    return templates.TemplateResponse(request, "home.html", context)


@app.get("/parser", response_class=HTMLResponse)
async def parser_page(
    request: Request,
    url: str | None = Query(default=None, description="URL da parsare"),
    mode: str = Query(default="live", description="'live' o 'local'"),
) -> HTMLResponse:
    """
    Parser & Evaluation: URL o selezione dal GS, modalità Live/Local, HTML,
    parsed text, gold text, metriche deterministiche e Judge.
    """
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        domains = await _fetch_domains(client)
        gs_urls = await _fetch_gs_urls_by_domain(client, domains)

        context: dict = {
            "request": request,
            "active_page": "parser",
            "domains": domains,
            "gs_urls": gs_urls,
            "url": url or "",
            "mode": mode,
            "error": None,
            "parse_result": None,
            "gs_entry": None,
            "evaluation": None,
            "judge": None,
            "judge_error": None,
        }

        if not url:
            return templates.TemplateResponse(request, "parser.html", context)

        if _extract_domain(url) is None:
            context["error"] = "URL malformato: serve uno scheme http/https e un netloc valido"
            return templates.TemplateResponse(request, "parser.html", context)

        parse_result, err = await _do_parse(client, url, local=(mode == "local"))
        if parse_result is None:
            context["error"] = err
            return templates.TemplateResponse(request, "parser.html", context)
        context["parse_result"] = parse_result

        gs_entry = await _fetch_gold_standard(client, url)
        if gs_entry is not None:
            context["gs_entry"] = gs_entry
            context["evaluation"] = await _do_evaluate(
                client,
                parse_result["parsed_text"],
                gs_entry["gold_text"],
            )
            judge, judge_error = await _do_evaluate_judge(
                client,
                parse_result["parsed_text"],
                gs_entry["gold_text"],
            )
            context["judge"] = judge
            context["judge_error"] = judge_error

        return templates.TemplateResponse(request, "parser.html", context)


@app.get("/gold-standard", response_class=HTMLResponse)
async def gold_standard_page(
    request: Request,
    url: str | None = Query(default=None, description="URL da acquisire"),
    mode: str = Query(default="live", description="'live' o 'local'"),
    domain: str | None = Query(default=None, description="dominio di cui elencare le entry GS"),
) -> HTMLResponse:
    """
    Gold Standard Builder: selezione del dominio con le entry già presenti,
    acquisizione HTML (Live/Local) e anteprima del parsed text come punto di
    partenza per il gold text.
    """
    context = _gold_standard_defaults(url or "", mode)
    context["request"] = request
    context["active_page"] = "gold_standard"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        # se arrivo qui cliccando una URL della lista il dominio non è nella query,
        # lo ricavo dalla URL così la lista mostrata resta quella giusta
        await _load_gs_index(client, context, domain or _extract_domain(url or ""))

        if url:
            if _extract_domain(url) is None:
                context["fetch_error"] = "URL malformato: serve uno scheme http/https e un netloc valido"
            else:
                fetch_result, err = await _do_parse(client, url, local=(mode == "local"))
                context["fetch_result"] = fetch_result
                context["fetch_error"] = err
                if fetch_result is not None:
                    context["existing_gold"] = await _fetch_gold_standard(client, url)

    return templates.TemplateResponse(request, "gold_standard.html", context)


@app.post("/gold-standard/save", response_class=HTMLResponse)
async def save_gold_standard(
    request: Request,
    url: str = Form(...),
    gold_text: str = Form(...),
) -> HTMLResponse:
    """
    Salva il gold text inviato dal form e ri-mostra la pagina in modalità
    Local (la web resource è già salvata, non serve un nuovo crawl).
    """
    context = _gold_standard_defaults(url, "local")
    context["request"] = request
    context["active_page"] = "gold_standard"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        result = await _add_gold_standard(client, url, gold_text)
        context["save_status"] = {"status": result.get("status", "error"), "url": url}
        await _load_gs_index(client, context, _extract_domain(url))

        fetch_result, err = await _do_parse(client, url, local=True)
        context["fetch_result"] = fetch_result
        context["fetch_error"] = err
        if fetch_result is not None:
            context["existing_gold"] = await _fetch_gold_standard(client, url)

    return templates.TemplateResponse(request, "gold_standard.html", context)


@app.post("/gold-standard/delete-gs", response_class=HTMLResponse)
async def delete_gs_route(request: Request, url: str = Form(...)) -> HTMLResponse:
    """Elimina solo il Gold Standard di una URL."""
    context = _gold_standard_defaults()
    context["request"] = request
    context["active_page"] = "gold_standard"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        result = await _delete_gold_standard(client, url)
        await _load_gs_index(client, context, _extract_domain(url))

    context["delete_status"] = {
        "status": result.get("status", "error"),
        "url": url,
        "kind": "solo Gold Standard",
    }
    return templates.TemplateResponse(request, "gold_standard.html", context)


@app.post("/gold-standard/delete-resource", response_class=HTMLResponse)
async def delete_resource_route(request: Request, url: str = Form(...)) -> HTMLResponse:
    """Elimina la web resource e, a cascata, il Gold Standard collegato."""
    context = _gold_standard_defaults()
    context["request"] = request
    context["active_page"] = "gold_standard"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        result = await _delete_web_resource(client, url)
        await _load_gs_index(client, context, _extract_domain(url))

    context["delete_status"] = {
        "status": result.get("status", "error"),
        "url": url,
        "kind": "web resource + Gold Standard a cascata",
    }
    return templates.TemplateResponse(request, "gold_standard.html", context)


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request) -> HTMLResponse:
    """Stats: conteggi, metriche medie e judge medio per dominio."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        domains = await _fetch_domains(client)
        stats, stats_error = await _fetch_db_stats(client)

    context = {
        "request": request,
        "active_page": "stats",
        "domains": domains,
        "stats": stats or {"web_resources": {}, "gold_standard": {}, "avg_eval": {}, "avg_eval_judge": {}},
        "stats_error": stats_error,
    }
    return templates.TemplateResponse(request, "stats.html", context)
