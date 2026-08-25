"""Calcola precision recall e f1 sui token"""

import re

from .eval import Evaluator

class TokenLevelEvaluator(Evaluator):
    """Implementa due metodi ``evaluate`` e ``noise_ratio`` per l'evaluation token-level"""

    _WORD_RE = re.compile(r"\w+", re.UNICODE)


    def evaluate(self, parsed_text: str, gold_text: str) -> dict:
        """Precision, recall e f1 sull'overlap dei token con il gold"""

        tokens_parsed = self._tokenize(parsed_text)
        tokens_gold = self._tokenize(gold_text)
        intersection = self._intersection(tokens_parsed, tokens_gold)

        return {
            "precision": self._precision(tokens_parsed, intersection),
            "recall": self._recall(tokens_gold, intersection),
            "f1": self._f1(tokens_parsed, tokens_gold, intersection)
        }


    def noise_ratio(self, parsed_text: str, gold_text: str) -> float:
        """Complementare della precision, cioè quanta spazzatura non dal gold è finita nel parsed"""

        tokens_parsed = self._tokenize(parsed_text)
        if not tokens_parsed:
            return 0.0
        tokens_gold = self._tokenize(gold_text)
        intersection = self._intersection(tokens_parsed, tokens_gold)
        return round(1.0 - self._precision(tokens_parsed, intersection), 4)


    def _tokenize(self, text: str) -> set:
        """Trasforma il testo in token unici minuscoli"""
        return set(self._WORD_RE.findall(text.lower()))


    def _intersection(self, a: set, b: set) -> set:
        """Trova i token presenti in entrambi gli insiemi"""
        return a & b


    def _precision(self, tokens_parsed: set, intersection: set) -> float:
        """Calcola quanti token estratti appartengono al gold"""
        return round(len(intersection) / len(tokens_parsed), 4) if tokens_parsed else 0.0


    def _recall(self, tokens_gold: set, intersection: set) -> float:
        """Calcola quanti token del gold sono stati estratti"""
        return round(len(intersection) / len(tokens_gold), 4) if tokens_gold else 0.0


    def _f1(self, tokens_parsed: set, tokens_gold: set, intersection: set) -> float:
        """Calcola la media armonica di precision e recall"""
        p = self._precision(tokens_parsed, intersection)
        r = self._recall(tokens_gold, intersection)
        return round(2 * p * r / (p + r), 4) if (p + r) > 0 else 0.0