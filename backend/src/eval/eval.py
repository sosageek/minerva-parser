from abc import ABC, abstractmethod

class Evaluator(ABC):
    
    @abstractmethod
    def evaluate(self, parsed_text: str, gold_text: str) -> str:
        pass