"""Calcola la metrica ChrF"""

from sacrebleu.metrics import CHRF
from .eval import Evaluator


class ChrFEvaluator(Evaluator):
    """Implementa metodo per l'evaluation con metrica ChrF"""

    def __init__(self, char_order: int = 6, word_order: int = 0, beta: float = 2.0):
        """Prepara ChrF con gli ordini e il peso scelti"""
        self._chrf = CHRF(char_order=char_order, word_order=word_order, beta=beta)

    def evaluate(self, parsed_text: str, gold_text: str) -> float:
        """Calcola ChrF tra parsed e gold su una scala da zero a uno"""
        result = self._chrf.sentence_score(
            hypothesis=parsed_text,
            references=[gold_text],
        )
        normalized_score = round(result.score / 100, 4)

        return normalized_score
