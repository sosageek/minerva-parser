from pydantic import BaseModel, ConfigDict

class ParsedDocument(BaseModel):
    """Documento parsato

    Attributes:
        url(str): URL assoluto della pagina di origine
        domain(str): netloc URL
        title(str): titolo estratto (da pagina o url)
        html_text(str): HTML pulito restituito dal crawler 
        parsed_text(str): testo MD normalizzato e pulito dal parser di dominio
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str
