"""Parla con il server locale di Ollama"""

import json
import logging
import time
import urllib.error
import urllib.request

from ..config import LOGGER_NAME, OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_URL

logger = logging.getLogger(LOGGER_NAME)


class OllamaError(RuntimeError):
    """Chiamata a Ollama non riuscita: server irraggiungibile, modello assente o timeout"""


# I modelli reasoning come qwen3 instradano la risposta nel campo `thinking`
# lasciando `response` vuoto, a meno che il ragionamento non sia disattivato.
# I modelli che non conoscono il parametro rispondono 400: al primo rifiuto
# smettiamo di inviarlo e memorizziamo la scelta per quel modello.
_supports_think: dict[str, bool] = {}


def _post(payload: dict, timeout: float) -> dict:
    """Esegue la POST a /api/generate"""
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("Ollama response is not a JSON object")
    return body


def generate(
    prompt: str,
    model: str = OLLAMA_MODEL,
    timeout: float = OLLAMA_TIMEOUT,
) -> tuple[str, float]:
    """Invia il prompt al modello e restituisce la risposta grezza"""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 300},
    }

    started = time.perf_counter()
    try:
        if _supports_think.get(model, True):
            try:
                body = _post({**payload, "think": False}, timeout)
                _supports_think[model] = True
            except urllib.error.HTTPError:
                _supports_think[model] = False
                logger.debug("il modello %s non supporta il parametro think", model)
                body = _post(payload, timeout)
        else:
            body = _post(payload, timeout)
    except (
        json.JSONDecodeError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as err:
        raise OllamaError(type(err).__name__) from err
    elapsed = time.perf_counter() - started

    # se il ragionamento resta attivo la risposta finisce in `thinking`:
    # recuperarla da lì è preferibile a scartare un giudizio valido
    raw = body.get("response", "") or ""
    if not raw.strip():
        raw = body.get("thinking", "") or ""
    return raw, elapsed


def is_available(timeout: float = 2.0) -> bool:
    """Verifica che l'API di Ollama risponda, senza richiedere un modello caricato"""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as response:
            return 200 <= response.status < 300
    except Exception:
        return False
