import asyncio
import hashlib
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import mariadb
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query

from ..config import STATUS_CHECK_TIMEOUT, configure_logging
from ..db import (
    close_pool,
    create_pool,
    initialize_schema,
    ping_database,
    seed_gold_standards,
    seed_precomputed_results,
)
from ..db.repositories import (
    evaluation_results as evaluation_repository,
    gold_standard as gold_standard_repository,
    judge_results as judge_repository,
    metadata as metadata_repository,
    web_resources as web_resource_repository,
)
from ..eval import ChrFEvaluator, RougeOneEvaluator, TokenLevelEvaluator
from ..judge import JudgeResult
from ..judge import is_available as judge_is_available
from ..judge import judge
from ..parsers import CrawlError, ParsedDocument, Parser
from ..parsers._crawler import close_crawler
from ..utils import strip_formatting
from .models import (
    CRUDStatus,
    DBSchema,
    DBStats,
    EvaluationInput,
    FullParseEvaluation,
    GoldStandardInput,
    GoldStandardURLs,
    GSEntry,
    JudgeEvaluation,
    ListGSEntry,
    ParseEvaluation,
    ParseInput,
    ParseOutput,
    ServiceStatus,
    StatusOutput,
    SupportedDomains,
    TokenLevelEval,
    URLInput,
    WebResourceInput,
)
from .registry import PARSERS, get_parser, supported_domains

# ---------------------------------- CONF  ----------------------------------

logger = logging.getLogger("minerva-parser.api")

_evaluator = TokenLevelEvaluator()
_chrf = ChrFEvaluator()
_rouge1 = RougeOneEvaluator()

# il tester batte full_gs_eval nove volte su quattro domini, le entry distinte sono 41 ma
# le inferenze sarebbero 92, e a temperature 0 lo stesso input ridà sempre lo stesso voto
_judge_cache: dict[str, JudgeResult] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Avvio e chiusura del server

    * configura il logging (formato e livello centralizzati in ``config.py``)
    * crea il pool, inizializza lo schema e popola il database
    * alla chiusura chiude il crawler condiviso e il pool di connessioni
    """

    configure_logging()

    try:
        create_pool()
        initialize_schema()
        seed_gold_standards()
        seed_precomputed_results()

        yield

    finally:
        try:
            await close_crawler()
        finally:
            close_pool()


app = FastAPI(
    title="Minerva Parser API",
    description="REST API per parsing, gold standard ed evaluation",
    lifespan=lifespan,
)

# ---------------------------------- HELPER  ----------------------------------


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


def _extract_title_from_html(html_text: str) -> str:
    """Estrae il contenuto del tag title da un documento HTML

    Args:
        html_text: HTML grezzo della pagina

    Returns:
        titolo della pagina, oppure stringa vuota se non è presente
    """

    soup = BeautifulSoup(html_text, "html.parser")

    if soup.title is None:
        return ""

    return soup.title.get_text(" ", strip=True)


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

    * ``token_level_eval``: precision, recall, f1 (set)
    * ``x_eval``: `chrf``, ``noise_ratio`` e ``rouge_1``

    Returns:
        ``ParseEvaluation`` con ``token_level_eval`` e ``x_eval``
    """

    parsed_clean = _prepare_for_eval(parsed_text)
    gold_clean = _prepare_for_eval(gold_text)
    token_metrics = _evaluator.evaluate(parsed_clean, gold_clean)
    x_eval = {
        "chrf": _chrf.evaluate(parsed_clean, gold_clean),
        "noise_ratio": _evaluator.noise_ratio(parsed_clean, gold_clean),
        "rouge_1": _rouge1.evaluate(parsed_clean, gold_clean),
    }
    return ParseEvaluation(
        token_level_eval=TokenLevelEval(**token_metrics),
        x_eval=x_eval,
    )


def _judge_key(parsed_text: str, gold_text: str) -> str:
    """Chiave di cache di una coppia (parsed, gold)

    sul contenuto e non sull'url perché i test automatici riscrivono html_text con
    /add_web_resource, quindi lo stesso url può dare un parsed_text diverso da una chiamata
    all'altra e ci ritroveremmo a servire un giudizio calcolato su un testo che non esiste
    più. hashando i due testi, se il testo cambia cambia la chiave e si rigiudica

    Returns:
        digest esadecimale dei due testi
    """

    digest = hashlib.sha256()
    # separatore esplicito, senza coppie diverse collassano sulla stessa concatenazione
    digest.update(parsed_text.encode())
    digest.update(b"\x00")
    digest.update(gold_text.encode())
    return digest.hexdigest()


def _judge_cached(parsed_text: str, gold_text: str) -> JudgeResult:
    """Giudizio del judge, riusato se quella coppia è già passata di qui

    la cache vive solo in memoria di processo, al riavvio del container si riparte da zero

    Returns:
        ``JudgeResult``, dalla cache oppure appena calcolato
    """

    key = _judge_key(parsed_text, gold_text)
    cached = _judge_cache.get(key)
    if cached is not None:
        return cached

    result = judge(parsed_text, gold_text)

    # i fallback sono punteggi neutri, non giudizi: se ollama era giù per un attimo e li
    # cachiamo ce li teniamo fino al riavvio anche dopo che è tornato su
    if result.diagnostics in ("ok", "repaired"):
        _judge_cache[key] = result

    return result


def _mean(values: list[float]) -> float:
    """Media arrotondata come le altre metriche, quattro decimali"""

    return round(sum(values) / len(values), 4)


def _database_is_available() -> bool:
    """Verifica MariaDB tramite il connection pool"""

    return ping_database()


def _ollama_is_available() -> bool:
    """Verifica l'API di Ollama tramite il probe del componente Judge."""

    return judge_is_available(timeout=STATUS_CHECK_TIMEOUT)


def _service_status(
    check: Callable[[], bool],
    service_name: str,
) -> ServiceStatus:
    """Converte ogni errore del probe nello stato degradato previsto dal contratto"""

    try:
        return "ok" if check() else "error"
    except Exception as err:
        logger.warning("status check %s fallito: %s", service_name, err)
        return "error"


# ---------------------------------- API  ----------------------------------


@app.get("/status", response_model=StatusOutput, status_code=200)
async def status() -> StatusOutput:
    """Restituisce sempre lo stato del backend e delle dipendenze esterne"""

    database_status, ollama_status = await asyncio.gather(
        asyncio.to_thread(
            _service_status,
            _database_is_available,
            "database",
        ),
        asyncio.to_thread(
            _service_status,
            _ollama_is_available,
            "ollama",
        ),
    )
    return StatusOutput(
        backend="ok",
        database=database_status,
        ollama=ollama_status,
    )


@app.get("/db_schema", response_model=DBSchema)
def db_schema() -> DBSchema:
    """Schema delle tabelle obbligatorie del database"""

    schema = metadata_repository.get_schema()

    return DBSchema(root=schema)


@app.get("/db_stats", response_model=DBStats)
def db_stats() -> DBStats:
    """Statistiche dei dati salvati nel database"""

    web_resources = web_resource_repository.count_by_domain()
    gold_standard = gold_standard_repository.count_by_domain()
    avg_eval = evaluation_repository.averages_by_domain()
    avg_eval_judge = judge_repository.averages_by_domain()

    return DBStats(
        web_resources=web_resources,
        gold_standard=gold_standard,
        avg_eval=avg_eval,
        avg_eval_judge=avg_eval_judge,
    )


@app.get("/domains", response_model=SupportedDomains)
def domains() -> SupportedDomains:
    """Lista dei domini supportati dal sistema"""

    return SupportedDomains(domains=supported_domains())


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
async def parse_document(payload: ParseInput) -> ParseOutput:
    """Esegue il parser in modalità Live o Local

    In modalità Live scarica la pagina e salva la web resource.
    In modalità Local usa esclusivamente l'HTML presente nel database.

    Args:
        payload: body con URL e modalità di parsing

    Returns:
        ``ParseOutput`` con i dati estratti dal parser

    Raises:
        HTTPException(400): URL malformato o dominio non supportato
        HTTPException(404): URL non presente nel database in modalità Local
        HTTPException(502): URL irraggiungibile in modalità Live
    """

    domain = _extract_domain(payload.url)
    _require_supported_domain(domain)

    if payload.local:
        resource = await asyncio.to_thread(
            web_resource_repository.get_by_url,
            payload.url,
        )

        if resource is None:
            raise HTTPException(
                status_code=404,
                detail=f"URL not in database: {payload.url}",
            )

        document = await _do_parse(
            payload.url,
            html_text=resource["html_text"],
        )

    else:
        document = await _do_parse(payload.url)

        await asyncio.to_thread(
            web_resource_repository.upsert,
            payload.url,
            document.domain,
            document.title,
            document.html_text,
        )

    return ParseOutput(**document.model_dump())


@app.get("/gold_standard", response_model=GSEntry)
def get_gold_standard(
    url: str = Query(
        ...,
        description="URL presente nel Gold Standard",
    ),
) -> GSEntry:
    """Entry del GS per l'URL dato

    Raises:
        HTTPException(400): dominio non supportato
        HTTPException(404): URL non presente nel GS
    """

    domain = _extract_domain(url)
    entry = gold_standard_repository.get_by_url(url)

    if entry is not None:
        return GSEntry(**entry)

    _require_supported_domain(domain)

    raise HTTPException(
        status_code=404,
        detail=f"URL not in gold standard: {url}",
    )


@app.get("/full_gold_standard", response_model=ListGSEntry)
def full_gold_standard(
    domain: str = Query(
        ...,
        description="Dominio per cui restituire il GS",
    ),
) -> ListGSEntry:
    """Tutte le entry del GS per un dominio

    Raises:
        HTTPException(400): dominio non supportato
    """

    _require_supported_domain(domain)

    entries = gold_standard_repository.list_by_domain(domain)

    return ListGSEntry(
        gold_standard=[
            GSEntry(**entry)
            for entry in entries
        ]
    )


@app.get("/gold_standard_urls", response_model=GoldStandardURLs)
def gold_standard_urls(
    domain: str | None = Query(
        default=None,
        description="Filtra opzionalmente le URL per dominio",
    ),
) -> GoldStandardURLs:
    """Lista degli URL presenti nel GS

    Raises:
        HTTPException(400): dominio non supportato
    """

    if domain is not None:
        _require_supported_domain(domain)

    urls = gold_standard_repository.list_urls(domain)

    return GoldStandardURLs(gold_standard_urls=urls)


@app.post("/add_web_resource", response_model=CRUDStatus)
def add_web_resource(payload: WebResourceInput) -> CRUDStatus:
    """Aggiunge o aggiorna una web resource nel database

    Args:
        payload: body con URL e HTML grezzo della risorsa

    Returns:
        stato dell'operazione
    """

    try:
        domain = _extract_domain(payload.url)

        title = _extract_title_from_html(payload.html_text)

        web_resource_repository.upsert(
            url=payload.url,
            domain=domain,
            title=title,
            html_text=payload.html_text,
        )

    except (HTTPException, mariadb.Error):
        logger.exception(
            "Inserimento web resource fallito: %s",
            payload.url,
        )
        return CRUDStatus(status="error")

    return CRUDStatus(status="ok")


@app.post("/add_gold_standard", response_model=CRUDStatus)
def add_gold_standard(payload: GoldStandardInput) -> CRUDStatus:
    """Aggiunge o aggiorna un Gold Standard

    Args:
        payload: body con URL e testo gold

    Returns:
        stato dell'operazione
    """

    web_resource = web_resource_repository.get_by_url(
        payload.url,
    )

    if web_resource is None:
        return CRUDStatus(status="error")

    try:
        gold_standard_repository.upsert(
            url=payload.url,
            gold_text=payload.gold_text,
        )

    except mariadb.Error:
        logger.exception(
            "Inserimento Gold Standard fallito: %s",
            payload.url,
        )
        return CRUDStatus(status="error")

    return CRUDStatus(status="ok")


@app.delete("/gold_standard", response_model=CRUDStatus)
def delete_gold_standard(payload: URLInput) -> CRUDStatus:
    """Elimina il Gold Standard lasciando la web resource

    Args:
        payload: body con l'URL del Gold Standard

    Returns:
        stato dell'operazione
    """

    try:
        deleted = gold_standard_repository.delete_by_url(
            payload.url,
        )

    except mariadb.Error:
        logger.exception(
            "Cancellazione Gold Standard fallita: %s",
            payload.url,
        )
        return CRUDStatus(status="error")

    if not deleted:
        return CRUDStatus(status="error")

    return CRUDStatus(status="ok")


@app.delete("/web_resource", response_model=CRUDStatus)
def delete_web_resource(payload: URLInput) -> CRUDStatus:
    """Elimina una web resource e il relativo GS a cascata

    Args:
        payload: body con l'URL della web resource

    Returns:
        stato dell'operazione
    """

    try:
        deleted = web_resource_repository.delete_by_url(
            payload.url,
        )

    except mariadb.Error:
        logger.exception(
            "Cancellazione web resource fallita: %s",
            payload.url,
        )
        return CRUDStatus(status="error")

    if not deleted:
        return CRUDStatus(status="error")

    return CRUDStatus(status="ok")


@app.post("/evaluate", response_model=ParseEvaluation)
def evaluate(payload: EvaluationInput) -> ParseEvaluation:
    """Calcola metriche di evaluation confrontando ``parsed_text`` dell'output con ``gold_text`` del GS

    nota: la sintassi md viene rimossa prima della tokenizzazione e dell'evaluation
    """

    return _do_evaluate(payload.parsed_text, payload.gold_text)


@app.post("/evaluate_judge", response_model=JudgeEvaluation)
async def evaluate_judge(payload: EvaluationInput) -> JudgeEvaluation:
    """Valuta una coppia parsed/gold con il componente LLM-as-a-Judge."""

    result = await asyncio.to_thread(judge, payload.parsed_text, payload.gold_text)
    return JudgeEvaluation(
        model_name=result.model_name,
        judge_score=result.judge_score,
        judge_feedback=result.judge_feedback,
        extra_noise=result.extra_noise,
        prompt_version=result.prompt_version,
    )


@app.get("/full_gs_eval", response_model=FullParseEvaluation)
async def full_gs_eval(
    domain: str = Query(..., description="Dominio su cui aggregare la valutazione"),
) -> FullParseEvaluation:
    """Evaluation aggregata su tutto il GS del dominio

    per ogni entry ripassa nel parser l'HTML già salvato nel database, quindi zero richieste di rete,
    e valuta ``parsed_text`` vs ``gold_text``. Metriche e judge_score sono entrambi medie calcolate
    sui singoli elementi come chiede la specifica, dal database arriva solo l'HTML

    i risultati precalcolati restano dove servono davvero, cioè in ``/db_stats``, che la specifica
    vuole esplicitamente costruito su dati già salvati

    Returns:
        ``FullParseEvaluation`` con la media delle metriche e la media dei judge_score

    nota: le entry che falliscono il parsing vengono saltate, l'aggregato è solo su quelle riuscite
    e i conteggi finiscono in ``x_eval``

    Raises:
        HTTPException(400): dominio non supportato
        HTTPException(502): se tutte le entry del GS falliscono il parsing
    """

    _require_supported_domain(domain)
    entries = await asyncio.to_thread(gold_standard_repository.list_by_domain, domain)

    evaluations: list[ParseEvaluation] = []
    judge_scores: list[float] = []
    failed: list[str] = []

    # parsing e giudizio seriali: crawl4ai gira su un browser condiviso e ollama tiene in memoria
    # una sola copia del modello, mandargli dieci richieste insieme non le fa finire prima, le
    # accoda e basta, con il rischio in più di mandarle in timeout tutte quante
    for entry in entries:
        url = entry["url"]
        try:
            doc = await _do_parse(url, entry["html_text"])
        except HTTPException as err:
            logger.warning("full_gs_eval: skip %s (%s)", url, err.detail)
            failed.append(url)
            continue

        evaluations.append(_do_evaluate(doc.parsed_text, entry["gold_text"]))
        verdict = await asyncio.to_thread(_judge_cached, doc.parsed_text, entry["gold_text"])
        judge_scores.append(verdict.judge_score)

    if not evaluations or not judge_scores:
        raise HTTPException(
            status_code=502,
            detail=f"all {len(entries)} URLs in gold standard for {domain} failed to parse",
        )

    token_evals = [item.token_level_eval for item in evaluations]
    rouge_1 = [item.x_eval["rouge_1"] for item in evaluations]
    x_eval: dict = {
        "n_evaluated": len(evaluations),
        "n_total": len(entries),
        "chrf": _mean([item.x_eval["chrf"] for item in evaluations]),
        "noise_ratio": _mean([item.x_eval["noise_ratio"] for item in evaluations]),
        "rouge_1": {
            "precision": _mean([item["precision"] for item in rouge_1]),
            "recall": _mean([item["recall"] for item in rouge_1]),
            "f1": _mean([item["f1"] for item in rouge_1]),
        },
    }
    if failed:
        x_eval["failed_urls"] = failed

    return FullParseEvaluation(
        token_level_eval=TokenLevelEval(
            precision=_mean([item.precision for item in token_evals]),
            recall=_mean([item.recall for item in token_evals]),
            f1=_mean([item.f1 for item in token_evals]),
        ),
        x_eval=x_eval,
        judge_score=_mean(judge_scores),
    )
