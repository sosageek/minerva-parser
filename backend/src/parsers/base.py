from abc import ABC, abstractmethod

class BaseParser(ABC):

    @abstractmethod
    async def parse(self, url: str) -> dict:
        pass

    @abstractmethod
    def clean_markdown(self, text: str) -> str:
        pass