import re
from crawl4ai import CrawlResult
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class BookerParser(Parser):
    """Parser per le pagine di thebookerprizes.com

    * isola il contenuto editoriale di news, profili autori e schede libro
    * scarta i widget promozionali che il cms Drupal Numiko accende intorno all'articolo (teaser grid, carousel, cta di acquisto)

    gli excluded selectors vengono passati direttamente a crawl4ai (non via beautiful soup come per wikipedia) perché qui i nodi da rimuovere sono section block-level e non mangiano tail text adiacente

    include regole di pulizia per crediti di traduzione a raffica, righe di copyright, spaziatura di virgole e possessivi rotti dal md converter, oltre a un filtro riga per riga per rumore residuo (ceremony, buy, social, editorial inline)
    """

# ---------------------------------- SELETTORI ----------------------------------

    _EXCLUDED_SELECTORS = (
        "nav, footer, header, aside, figcaption, "
        ".cookies-banner, .newsletter-signup-block, "
        ".share-icons, .social-share, "
        "section.youtube-carousel, .c-path, .breadcrumb, "
        ".book_selling_form, .book-selling-retailers, .book-selling-formats, "
        ".c-modal, .flickity-button, .sr-only, "
        "[data-js-paragraph-type-slice-teaser], "
        "[data-js-paragraph-type-asymmetric-teaser], "
        "[data-js-paragraph-type-vertical-teaser], "
        "[data-js-related-carousel]"
    )

    _TARGET_ELEMENTS = ["main"]

# ------------------------------------ REGEX -------------------------------------

    # thebookerprizes ha un sacco di contenuti spazzatura mascherati tra i paragrafi degli articoli come testo normale
    # molte righe di testo semplici (non contenuto filtrabile con excluded selectors) contengono cta e promo varie
    # peggio di nps (gabriele)

    _RE_EDITORIAL_INLINE = re.compile(
        r'(interview|reading guide|extract|book recommendations|'
        r'watch|read more|discover|quiz|competition|information)',
        re.IGNORECASE
    )

    _RE_SOCIAL = re.compile(
        r'(facebook|instagram|twitter|youtube|tiktok)',
        re.IGNORECASE
    )

    _RE_BUY = re.compile(
        r'(buy the book|shop now|hardback|paperback|ebook|audiobook|'
        r'bookkind|amazon|blackwells|waterstones|bookshop\.org)',
        re.IGNORECASE
    )

    _RE_CEREMONY_NOISE = re.compile(
        r'(ceremony|in pictures|reacts to|hugs|holding|trophies|speech|performs)',
        re.IGNORECASE
    )

    _RE_URL = re.compile(r'https?://\S+')

    _RE_TRANSLATOR_CREDITS = re.compile(
        r'^(?:[^\n]*?translated by[^\n]*?){3,}[^\n]*\n?',
        re.IGNORECASE | re.MULTILINE
    )

    _RE_COPYRIGHT_LINES = re.compile(r'^[^\n]*?©[^\n]*\n?', re.MULTILINE)

    _RE_COMMA_SPACING = re.compile(r',([^\s\d])')
    _RE_POSSESSIVE_SPACED = re.compile(r"\s+'s")

# ------------------------------------ SOGLIE ------------------------------------

    _MIN_LINE_LEN = 4                    
    _BOOKS_SECTION_MAX_LEN = 100
    _CEREMONY_MAX_LEN = 200
    _JUNK_INLINE_MAX_LEN = 150
    _DEDUP_LONG_THRESHOLD = 60
    _SHORT_DEDUP_WINDOW = 3
    _EDITORIAL_PREFIX_MAX_START = 30


    def __init__(self):
        super().__init__(
            target_elements=self._TARGET_ELEMENTS,
            excluded_selector=self._EXCLUDED_SELECTORS,
        )

# ---------------------------------- METODI PUBBLICI ----------------------------------

    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        """Applica la pipeline di fetching-parsing specifica per thebookerprizes.com
        a partire dall'url o dall'html della pagina

        Args:
            url(str): url della pagina da scaricare
            raw_html(str | None): HTML sorgente opzionale

        Returns:
            istanza di ``ParsedDocument`` con ``url``, ``domain``, ``title``, ``html_text`` e ``parsed_text``

        Raises:
            CrawlError: se il fetch della pagina fallisce (lo lancia la chiamata interna a ``_fetch``)
        """

        result = await self._fetch(url, raw_html=raw_html)
        final_url = url if raw_html is not None else (getattr(result, "url", None) or url)

        return ParsedDocument(
            url=final_url,
            domain=urlparse(final_url).netloc,
            title=self._extract_title(result, final_url),
            html_text=result.cleaned_html,
            parsed_text=self.normalize(result.markdown or ""),
        )


    def normalize(self, text: str) -> str:
        """Applica pipeline di pulizia specifica al testo markdown
        estratto da una pagina thebookerprizes.com con crawl4ai

        * rimuove crediti di traduzione e copyright
        * riaggiunge spazio dopo le virgole
        * rimuove spazio tra nomi e genitivo sassone
        * filtra righe con testo spazzatura (promo ecc...) che si confondono con il vero contenuto

        Args:
            text(str): testo markdown grezzo generato da crawl4ai

        Returns:
            stringa di testo normalizzato
        """

        text = remove_markup(text)
        text = self._RE_TRANSLATOR_CREDITS.sub('', text)
        text = self._RE_COPYRIGHT_LINES.sub('', text)
        text = self._RE_COMMA_SPACING.sub(r', \1', text)
        text = self._RE_POSSESSIVE_SPACED.sub("'s", text)
        text = self._filter_lines(text)
        text = normalize_whitespace(text)
        return text.strip()
    
# ---------------------------------- HELPER PRIVATI ----------------------------------

    def _is_editorial_noise(self, line: str, lower: str) -> bool:
        """Decide se una riga è una cta o card editoriale (interview, reading guide, ecc)

        una riga è classificata come rumore editoriale se contiene un pattern di ``_RE_EDITORIAL_INLINE``
        e se il match cade nei primi caratteri oppure se la riga è abbastanza corta da non essere un paragrafo vero

        Args:
            line(str): riga originale (case preservato)
            lower(str): riga in minuscolo, passata già computata per evitare di ricalcolarla

        Returns:
            ``True`` se la riga è da scartare, ``False`` altrimenti
        """

        m = self._RE_EDITORIAL_INLINE.search(lower)
        if not m:
            return False
        if m.start() < self._EDITORIAL_PREFIX_MAX_START:
            return True
        return len(line) <= self._JUNK_INLINE_MAX_LEN


    def _filter_lines(self, text: str) -> str:
        """Filtra riga per riga il rumore residuo che non si è riusciti a togliere a monte

        la maggior parte dei predicati è length-gated, meglio non applicare filtri su paragrafi lunghi perché il pattern per cui matcha è quasi sempre legittimo

        Args:
            text(str): testo markdown già pulito dai blocchi regex precedenti

        Returns:
            testo con le righe di rumore rimosse
        """

        lines = text.split('\n')
        cleaned = []
        seen_long = set()
        recent_short = []

        in_books_section = False

        for line in lines:
            line = line.strip()

            if len(line) < self._MIN_LINE_LEN or line.lower() == "play video":
                continue

            lower = line.lower()

            if "other nominated books" in lower:
                in_books_section = True
                cleaned.append(line)
                continue

            if in_books_section and len(line) > self._BOOKS_SECTION_MAX_LEN:
                continue

            if len(line) <= self._CEREMONY_MAX_LEN:
                if self._RE_CEREMONY_NOISE.search(lower):
                    continue

            if len(line) <= self._JUNK_INLINE_MAX_LEN:
                if self._RE_BUY.search(lower):
                    continue
                if self._RE_SOCIAL.search(lower) or self._RE_URL.search(line):
                    continue

            if self._is_editorial_noise(line, lower):
                continue

            if len(line) > self._JUNK_INLINE_MAX_LEN:
                if self._RE_URL.search(line) or self._RE_BUY.search(lower):
                    continue

            if len(line) > self._DEDUP_LONG_THRESHOLD:
                if lower in seen_long:
                    continue
                seen_long.add(lower)
            else:
                if lower in recent_short:
                    continue
                recent_short.append(lower)
                if len(recent_short) > self._SHORT_DEDUP_WINDOW:
                    recent_short.pop(0)

            cleaned.append(line)

        return "\n".join(cleaned)
    

    def _extract_title(self, result: CrawlResult, url: str) -> str:
        """Estrae il titolo della pagina

        * preferisce il contenuto del tag ``<title>`` html
        * se il titolo non è disponibile usa l'ultimo segmento del path come fallback
        (che su thebookerprizes non è particolarmente opaco)

        Args:
            result(CrawlResult): risultato di crawl4ai con il metadata del tag ``<title>``
            url(str): URL completo della pagina (usato come fallback)

        Returns:
            il titolo della pagina pulito dal suffisso, o un fallback estratto dall' URL
        """

        metadata = getattr(result, "metadata", None)
        title = metadata.get("title") if isinstance(metadata, dict) else None

        if title:
            title = title.split('|', 1)[0].strip()
            if title:
                return title

        path = urlparse(url).path
        last = path.rstrip("/").rsplit("/", 1)[-1] or ""
        last = unquote(last).replace("_", " ").replace("-", " ").strip()
        return last or "(thebookerprizes.com)"