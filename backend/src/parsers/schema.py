from pydantic import BaseModel, ConfigDict

class ParsedDocument(BaseModel):
    """Documento parsato, pronto per i consumatori downstream.

    Attributes:
        url: URL assoluto della pagina di origine
        domain: netloc URL
        title: titolo estratto (da pagina o url)
        html_text: HTML pulito restituito dal crawler 
        parsed_text: testo MD normalizzato e pulito dal parser di dominio
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str
