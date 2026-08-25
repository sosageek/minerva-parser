"""Calcola la metrica ROUGE uno"""

import re
from collections import Counter
from .eval import Evaluator


class RougeOneEvaluator(Evaluator):
    """Classe per valutare ROUGE-1: sovrapposizione di unigrammi con precision, recall, F1"""
    _WORD_RE = re.compile(r"\w+", re.UNICODE) # si può mettere in .eval più tardi

    def evaluate(self, parsed_text: str, gold_text: str) -> dict:
        """Calcola precision recall e f1 con la metrica ROUGE uno"""
        c_p = Counter(self._tokenize(parsed_text))
        c_g = Counter(self._tokenize(gold_text))
        
        match    = sum((c_p & c_g).values())
        n_parsed = sum(c_p.values())
        n_gold   = sum(c_g.values())

        if n_parsed:
            p = match/n_parsed
        else:
            p = 0.0

        if n_gold:
            r = match/n_gold
        else:
            r = 0.0

        f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
        return {
            "precision": round(p,  4),
            "recall":    round(r,  4),
            "f1":        round(f1, 4),
        }

    def _tokenize(self, text: str) -> list:
        """Divide il testo in parole minuscole"""
        return self._WORD_RE.findall(text.lower())




