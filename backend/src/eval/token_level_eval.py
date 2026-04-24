import re

from .eval import Evaluator

class TokenLevelEvaluator(Evaluator):
    """Implementa due metodi ``evaluate`` e ``noise_ratio`` per l'evaluation token-level 

    Formule:
        precision = |token_parsed ∩ token_gold| / |token_parsed|
        recall = |token_parsed ∩ token_gold| / |token_gold|
        f1 = 2 * precision * recall / (precision + recall)
        noise_ratio = 1 - precision

    interpretazione della f1: <0.6 scarso, da 0.6 a 0.8 medio, >0.8 buono
    """

    _WORD_RE = re.compile(r"\w+", re.UNICODE)


    def evaluate(self, parsed_text: str, gold_text: str) -> dict:
        """Precision, recall e f1 sull'overlap dei token con il gold

        * precision: dei token estratti, quanti stanno davvero nel gold
        * recall: dei token del gold, quanti il parser è riuscito a prendere
        * f1: media armonica di precision e recall, come indicatore sintetico

        Args:
            parsed_text(str): testo estratto dal parser
            gold_text(str): testo del gold standard

        Returns:
            dict con chiavi ``precision``, ``recall`` ed ``f1``
            se uno dei due testi è vuoto le metriche corrispondenti valgono zero
        """

        tokens_parsed = self._tokenize(parsed_text)
        tokens_gold = self._tokenize(gold_text)
        intersection = self._intersection(tokens_parsed, tokens_gold)

        return {
            "precision": self._precision(tokens_parsed, intersection),
            "recall": self._recall(tokens_gold, intersection),
            "f1": self._f1(tokens_parsed, tokens_gold, intersection)
        }


    def noise_ratio(self, parsed_text: str, gold_text: str) -> float:
        """Complementare della precision, cioè quanta spazzatura non dal gold è finita nel parsed

        * se il valore è prossimo allo zero vuol dire che c'è poco contenuto spazzatura
        * se il valore approccia 1 vuol dire che c'è molto contenuto spazzatura e il parser è da rivedere

        Args:
            parsed_text(str): testo estratto dal parser
            gold_text(str): testo di riferimento del gold standard

        Returns:
            float tra 0 e 1, arrotondato
            se il parsed è vuoto ritorna zero (non c'è rumore da misurare)
        """

        tokens_parsed = self._tokenize(parsed_text)
        if not tokens_parsed:
            return 0.0
        tokens_gold = self._tokenize(gold_text)
        intersection = self._intersection(tokens_parsed, tokens_gold)
        return round(1.0 - self._precision(tokens_parsed, intersection), 4)


    def _tokenize(self, text: str) -> set:
        return set(self._WORD_RE.findall(text.lower()))


    def _intersection(self, a: set, b: set) -> set:
        return a & b


    def _precision(self, tokens_parsed: set, intersection: set) -> float:
        return round(len(intersection) / len(tokens_parsed), 4) if tokens_parsed else 0.0


    def _recall(self, tokens_gold: set, intersection: set) -> float:
        return round(len(intersection) / len(tokens_gold), 4) if tokens_gold else 0.0


    def _f1(self, tokens_parsed: set, tokens_gold: set, intersection: set) -> float:
        p = self._precision(tokens_parsed, intersection)
        r = self._recall(tokens_gold, intersection)
        return round(2 * p * r / (p + r), 4) if (p + r) > 0 else 0.0