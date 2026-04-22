import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query

from ..config import configure_logging
from ..eval.token_level_eval import TokenLevelEvaluator
from ..parsers._crawler import close_crawler
from ..parsers.parser import CrawlError, Parser
from ..parsers.schema import ParsedDocument
from ..utils import strip_formatting
from .models import (
    EvaluationInput,
    GSEntry,
    ListGSEntry,
    ParseEvaluation,
    ParseInput,
    ParseOutput,
    SupportedDomains,
    TokenLevelEval,
)
from .registry import PARSERS, get_parser, load_gold_standards, supported_domains


logger = logging.getLogger("minerva-parser.api")

_gs_store: dict[str, list[dict]] = {}
_evaluator = TokenLevelEvaluator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Avvio e chiusura del server

    * configura il logging (formato e livello centralizzati in ``config.py``)
    * all'avvio carica in memoria tutti i GS (failfast se manca un file)
    * alla chiusura chiude il crawler condiviso evitando processi zombie
    """
    configure_logging()
    global _gs_store
    _gs_store = load_gold_standards()
    logger.info(
        "GS caricati: %s",
        {d: len(entries) for d, entries in _gs_store.items()},
    )
    try:
        yield
    finally:
        await close_crawler()


app = FastAPI(
    title="Minerva Parser API",
    #version=
    description="REST API per parsing, gold standard ed evaluation",
    lifespan=lifespan,
)


def _extract_domain(url: str) -> str:
    """Estrae netloc da un URL

    Args:
        url: URL fornito dal client

    Returns:
        netloc

    Raises:
        HTTPException(400): se scheme o netloc sono vuoti
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="malformed URL")
    return parsed.netloc


def _require_parser(domain: str) -> Parser:
    """Ritorna il parser per il dominio

    Args:
        domain: netloc del dominio

    Returns:
        istanza di ``Parser``

    Raises:
        HTTPException(400): dominio non in ``registry.PARSERS``
    """
    parser = get_parser(domain)
    if parser is None:
        raise HTTPException(
            status_code=400,
            detail=f"domain {domain} not supported",
        )
    return parser


def _require_supported_domain(domain: str) -> None:
    """Validazione del dominio

    Args:
        domain: netloc del dominio

    Raises:
        HTTPException(400): dominio non in ``registry.PARSERS``
    """
    if domain not in PARSERS:
        raise HTTPException(
            status_code=400,
            detail=f"domain {domain} not supported",
        )


async def _do_parse(url: str, html_text: str | None = None) -> ParsedDocument:
    """Esegue il parsing di un URL scegliendo il parser in base al dominio

    se ``html_text`` è fornito il parser processa direttamente quell'html senza effettuare una richiesta di rete: 
    l'URL viene comunque usato per individuare il parser giusto

    Args:
        url: URL assoluto
        html_text: HTML già scaricato dal client (opzionale)

    Returns:
        ``ParsedDocument``

    Raises:
        HTTPException(400): dominio non supportato o URL malformato
        HTTPException(502): crawl fallisce
    """
    domain = _extract_domain(url)
    parser = _require_parser(domain)
    try:
        return await parser.parse(url, raw_html=html_text)
    except CrawlError as err:
        logger.warning("crawl fallito per %s: %s", url, err)
        raise HTTPException(status_code=502, detail=f"unreachable URL: {url}") from err


def _prepare_for_eval(text: str) -> str:
    """Normalizzazione unica applicata a tutti gli input di evaluation

    * pulizia della formatazzione md inline (grassetto, corsivo, ecc) e di struttura (titoli, intestazioni, ecc)
    * collassa spazi e newline multipli

    nota: la rimozione di markup senza contenuto semantico / con link esterni (tabelle, immagini, link, ecc)
    è gestita dai singoli parsers

    Args:
        text: stringa potenzialmente contenente formattazione markdown

    Returns:
        plain text pronto per la tokenizzazione e l'evaluation
    """
    return strip_formatting(text)


def _do_evaluate(parsed_text: str, gold_text: str) -> ParseEvaluation:
    """Calcola le metriche di evaluation per una coppia (parsed, gold)

    Returns:
        ``ParseEvaluation`` con ``token_level_eval`` e ``x_eval``
    """
    parsed_clean = _prepare_for_eval(parsed_text)
    gold_clean = _prepare_for_eval(gold_text)
    token_metrics = _evaluator.evaluate(parsed_clean, gold_clean)
    return ParseEvaluation(
        token_level_eval=TokenLevelEval(**token_metrics),
        x_eval={},
    )


@app.get("/parse", response_model=ParseOutput)
async def parse(url: str = Query(..., description="URL assoluto da parsare")) -> ParseOutput:
    """Esegue il parser appropriato per l'URL dato

    Args:
        url: URL assoluto passato come query string

    Returns:
        ``ParseOutput`` con ``url``, ``domain``, ``title``, ``html_text`` e ``parsed_text`` (markdown pulito)

    Raises:
        HTTPException(400): dominio non supportato o URL malformato
        HTTPException(502): URL irraggiungibile
    """
    doc = await _do_parse(url)
    return ParseOutput(**doc.model_dump())


@app.post("/parse", response_model=ParseOutput)
async def parse_html(payload: ParseInput) -> ParseOutput:
    """Esegue il parser appropriato su un HTML fornito dal client

    a differenza di GET /parse non viene fatta alcuna richiesta di rete

    Args:
        payload: body con ``url`` (usato per selezionare il parser) e ``html_text``

    Returns:
        ``ParseOutput`` con ``url``, ``domain``, ``title``, ``html_text`` e ``parsed_text``

    Raises:
        HTTPException(400): dominio non supportato o URL malformato
        HTTPException(422): body mancante o invalido (gestito da FastAPI)
    """
    doc = await _do_parse(payload.url, html_text=payload.html_text)
    return ParseOutput(**doc.model_dump())


@app.get("/domains", response_model=SupportedDomains)
def domains() -> SupportedDomains:
    """Lista dei domini supportati dal sistema"""
    return SupportedDomains(domains=supported_domains())


@app.get("/gold_standard", response_model=GSEntry)
def gold_standard(url: str = Query(..., description="URL presente nel gold standard")) -> GSEntry:
    """Entry del GS per l'url dato

    Raises:
        HTTPException(400): dominio non supportato
        HTTPException(404): URL non presente nel GS
    """
    domain = _extract_domain(url)
    _require_supported_domain(domain)

    for entry in _gs_store.get(domain, []):
        if entry["url"] == url:
            return GSEntry(**entry)
    raise HTTPException(status_code=404, detail=f"URL not in gold standard: {url}")


@app.get("/full_gold_standard", response_model=ListGSEntry)
def full_gold_standard(
    domain: str = Query(..., description="Dominio per cui restituire il GS"),
) -> ListGSEntry:
    """Tutte le entry del GS per un dominio

    Raises:
        HTTPException(400): dominio non supportato
    """
    _require_supported_domain(domain)
    entries = [GSEntry(**e) for e in _gs_store.get(domain, [])]
    return ListGSEntry(gold_standard=entries)


@app.post("/evaluate", response_model=ParseEvaluation)
def evaluate(payload: EvaluationInput) -> ParseEvaluation:
    """Calcola metriche di evaluation confrontando ``parsed_text`` dell'output con ``gold_text`` del GS

    nota: la sintassi md viene rimossa prima della tokenizzazione e dell'evaluation
    """
    return _do_evaluate(payload.parsed_text, payload.gold_text)


@app.get("/full_gs_eval", response_model=ParseEvaluation)
async def full_gs_eval(
    domain: str = Query(..., description="Dominio su cui aggregare la valutazione"),
) -> ParseEvaluation:
    """Evaluation aggregata su tutto il GS del dominio

    * esegue il parsing con ``_do_parse``
    * valuta ``parsed_text`` vs ``gold_text`` con ``_do_evaluate``

    Poi media precision, recall e f1 sulle singole valutazioni.

    Returns:
        ``ParseEvaluation`` con la media delle evaluation effettuate su tutti i domini dove va a buon fine

    nota: se alcuni, ma non tutti, i domini falliscono al crawl si ha in output evaluation aggregata
    solo rispetto ai domini che l'hanno completata con successo

    Raises:
        HTTPException(400): dominio non supportato
        HTTPException(502): se tutti gli URL del GS falliscono al crawl
    """
    _require_supported_domain(domain)
    entries = _gs_store.get(domain, [])

    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
    failed: list[str] = []

    for entry in entries:
        url = entry["url"]
        try:
            doc = await _do_parse(url)
        except HTTPException as err:
            logger.warning("full_gs_eval: skip %s (%s)", url, err.detail)
            failed.append(url)
            continue

        parsed_clean = _prepare_for_eval(doc.parsed_text)
        gold_clean = _prepare_for_eval(entry["gold_text"])
        metrics = _evaluator.evaluate(parsed_clean, gold_clean)
        precisions.append(metrics["precision"])
        recalls.append(metrics["recall"])
        f1s.append(metrics["f1"])

    if not precisions:
        raise HTTPException(
            status_code=502,
            detail=f"all {len(entries)} URLs in gold standard for {domain} failed to parse",
        )

    n = len(precisions)
    aggregated = TokenLevelEval(
        precision=round(sum(precisions) / n, 4),
        recall=round(sum(recalls) / n, 4),
        f1=round(sum(f1s) / n, 4),
    )
    x_eval: dict = {"n_evaluated": n, "n_total": len(entries)}
    if failed:
        x_eval["failed_urls"] = failed
    return ParseEvaluation(token_level_eval=aggregated, x_eval=x_eval)
