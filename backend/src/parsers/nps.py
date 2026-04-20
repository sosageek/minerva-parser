from .parser import Parser
from .schema import ParsedDocument

class NpsParser(Parser):

    def __init__(self):
        super.__init__()

    async def parse(self, url: str) -> ParsedDocument:
        result = await self._fetch(url)
        final_url = getattr(result, "url", None) or url

        #TODO: completa implementazione
