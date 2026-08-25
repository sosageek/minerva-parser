"""Definisce il contratto comune delle metriche"""

from abc import ABC, abstractmethod

class Evaluator(ABC):
    
    """Tiene uguale il contratto di tutte le metriche"""
    @abstractmethod
    def evaluate(self, parsed_text: str, gold_text: str) -> dict:
        """Confronta il testo parsato con il gold"""
        pass