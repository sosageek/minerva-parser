"""Verifica lo stato dei servizi anche quando non rispondono"""

import asyncio

from backend.src.server import server


def test_status_reports_each_service(monkeypatch):
    """Riporta separatamente lo stato di ogni servizio"""
    monkeypatch.setattr(server, "_database_is_available", lambda: True)
    monkeypatch.setattr(server, "_ollama_is_available", lambda: False)

    response = asyncio.run(server.status())

    assert response.model_dump() == {
        "backend": "ok",
        "database": "ok",
        "ollama": "error",
    }


def test_status_stays_available_when_checks_raise(monkeypatch):
    """Resta disponibile anche quando i controlli falliscono"""
    def unavailable():
        """Finge un servizio non disponibile"""
        raise ConnectionError("service offline")

    monkeypatch.setattr(server, "_database_is_available", unavailable)
    monkeypatch.setattr(server, "_ollama_is_available", unavailable)

    response = asyncio.run(server.status())

    assert response.model_dump() == {
        "backend": "ok",
        "database": "error",
        "ollama": "error",
    }
