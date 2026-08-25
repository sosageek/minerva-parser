"""Trasforma la risposta di Ollama in un giudizio valido"""

import json
import logging

from ..config import LOGGER_NAME, OLLAMA_MODEL
from ..utils import strip_formatting
from .client import OllamaError, generate
from .models import PROMPT_VERSION, JudgeResult
from .prompts import REPAIR_SUFFIX, build_prompt

logger = logging.getLogger(LOGGER_NAME)

# punteggio neutro assegnato quando il modello non produce un giudizio valido:
# la specifica impone un fallback, e un valore centrale non falsa le medie
# quanto un estremo
_FALLBACK_SCORE: int = 3


def _extract_json(raw: str) -> dict | None:
    """Estrae l'oggetto JSON dalla risposta del modello"""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.removeprefix("json").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _to_result(data: dict, model: str, diagnostics: str, latency: float) -> JudgeResult | None:
    """Converte la risposta del modello in JudgeResult, se conforme"""
    score = data.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
        return None

    noise = data.get("extra_noise", "")
    return JudgeResult(
        model_name=model,
        judge_score=score,
        judge_feedback=str(data.get("feedback", ""))[:500],
        extra_noise="" if str(noise).strip().lower() in ("none", "") else str(noise)[:300],
        diagnostics=diagnostics,
        prompt_version=PROMPT_VERSION,
        latency_s=round(latency, 1),
    )


def _fallback(model: str, diagnostics: str, feedback: str) -> JudgeResult:
    """Giudizio conforme prodotto quando il modello non è utilizzabile"""
    logger.warning("judge non disponibile (%s), assegnato punteggio neutro", diagnostics)
    return JudgeResult(
        model_name=model,
        judge_score=_FALLBACK_SCORE,
        judge_feedback=feedback,
        diagnostics=diagnostics,
        prompt_version=PROMPT_VERSION,
    )


def judge(parsed_text: str, gold_text: str, model: str = OLLAMA_MODEL) -> JudgeResult:
    """Valuta la qualità del testo parsato rispetto al Gold Standard"""
    try:
        prompt = build_prompt(strip_formatting(parsed_text), strip_formatting(gold_text))
    except Exception as err:
        logger.exception("preparazione del prompt Judge fallita")
        return _fallback(
            model,
            f"error:{type(err).__name__}",
            "Judge unavailable, neutral score assigned.",
        )

    for attempt, (suffix, diagnostics) in enumerate(
        (("", "ok"), (REPAIR_SUFFIX, "repaired")), start=1
    ):
        try:
            raw, elapsed = generate(prompt + suffix, model)
        except OllamaError as err:
            return _fallback(model, f"error:{err}", "Judge unavailable, neutral score assigned.")
        except Exception as err:
            logger.exception("errore inatteso del client Judge")
            return _fallback(
                model,
                f"error:{type(err).__name__}",
                "Judge unavailable, neutral score assigned.",
            )

        data = _extract_json(raw)
        if data is not None:
            result = _to_result(data, model, diagnostics, elapsed)
            if result is not None:
                return result
        logger.debug("risposta non conforme al tentativo %d", attempt)

    return _fallback(
        model,
        "fallback",
        "Model did not return valid JSON, neutral score assigned.",
    )
