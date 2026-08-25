"""Verifica risposte fallback e gestione errori del Judge"""

import json
import importlib

import pytest
from pydantic import ValidationError

from backend.src.judge import client
from backend.src.judge import judge as judge_function
from backend.src.judge import models
from backend.src.judge.client import OllamaError

judge_module = importlib.import_module("backend.src.judge.judge")


def test_valid_response_is_converted(monkeypatch):
    """Converte una risposta valida nel risultato pubblico"""
    monkeypatch.setattr(
        judge_module,
        "generate",
        lambda prompt, model: (
            json.dumps({"extra_noise": "none", "score": 5, "feedback": "Clean."}),
            1.25,
        ),
    )

    result = judge_function("parsed", "gold")

    assert result.judge_score == 5
    assert result.extra_noise == ""
    assert result.diagnostics == "ok"


def test_invalid_response_is_repaired_once(monkeypatch):
    """Prova una sola riparazione dopo una risposta non valida"""
    replies = iter(
        [
            ("not-json", 0.5),
            ('{"extra_noise":"menu","score":3,"feedback":"Some noise."}', 0.7),
        ]
    )
    monkeypatch.setattr(judge_module, "generate", lambda prompt, model: next(replies))

    result = judge_function("parsed", "gold")

    assert result.judge_score == 3
    assert result.diagnostics == "repaired"


def test_two_invalid_responses_return_neutral_fallback(monkeypatch):
    """Usa il fallback neutro dopo due risposte non valide"""
    monkeypatch.setattr(judge_module, "generate", lambda prompt, model: ("{}", 0.1))

    result = judge_function("parsed", "gold")

    assert result.judge_score == 3
    assert result.diagnostics == "fallback"


def test_ollama_error_never_escapes(monkeypatch):
    """Trasforma un errore Ollama nel fallback neutro"""
    def unavailable(prompt, model):
        """Finge Ollama non disponibile"""
        raise OllamaError("TimeoutError")

    monkeypatch.setattr(judge_module, "generate", unavailable)

    result = judge_function("parsed", "gold")

    assert result.judge_score == 3
    assert result.diagnostics == "error:TimeoutError"


def test_unexpected_client_error_never_escapes(monkeypatch):
    """Trasforma anche un errore inatteso nel fallback neutro"""
    def broken_client(prompt, model):
        """Finge un errore inatteso del client"""
        raise RuntimeError("unexpected")

    monkeypatch.setattr(judge_module, "generate", broken_client)

    result = judge_function("parsed", "gold")

    assert result.judge_score == 3
    assert result.diagnostics == "error:RuntimeError"


def test_judge_score_is_strict_integer():
    """Rifiuta punteggi Judge che non sono interi"""
    with pytest.raises(ValidationError):
        models.JudgeResult(model_name="qwen3:4b", judge_score=4.0)


def test_generate_wraps_invalid_ollama_json(monkeypatch):
    """Trasforma il json Ollama non valido in OllamaError"""
    class Response:
        """Finge una risposta HTTP con json non valido"""
        def __enter__(self):
            """Apre il contesto della risposta finta"""
            return self

        def __exit__(self, *args):
            """Chiude il contesto senza nascondere gli errori"""
            return False

        def read(self):
            """Restituisce un corpo che non contiene json valido"""
            return b"not-json"

    monkeypatch.setattr(client.urllib.request, "urlopen", lambda *args, **kwargs: Response())

    with pytest.raises(OllamaError):
        client.generate("prompt")
