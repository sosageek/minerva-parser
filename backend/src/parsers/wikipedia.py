import html
import re
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
from .parser import Parser, CrawlError
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class WikipediaParser(Parser):
    """Parser per le pagine di en.wikipedia.org

    * isola il contenuto enciclopedico
    * scarta navboxes, infoboxes e apparato bibliografico

    gli excluded selectors vengono applicati in preprocessing via beautiful soup (non crawl4ai) per proteggere i tail text degli inline
    
    include regole di pulizia specifiche per link IPA, note a fine di pagina, formule latex renderizzate come immagini, e taglio alle sezioni terminali
    """

# ---------------------------------- SELETTORI ----------------------------------

    # da passare a beautiful soup non a crawl4ai!!!
    _EXCLUDED_SELECTORS = (
        ".mw-navigation, #mw-head, #mw-panel, .mw-indicators, .mw-jump-link, "
        "#siteSub, #contentSub, .printfooter, .catlinks, #catlinks, "
        ".mw-hidden-catlinks, "
        ".navbox, .sidebar, .toc, .hatnote, .ambox, .infobox, "
        ".shortdescription, .metadata, [role=\"note\"], "
        ".plainlinks, .portalbox, .portal-bar, "
        ".thumb, .tright, .tleft, .mw-file-description, figure, figcaption, "
        ".gallery, .categorytree, "
        ".geo-dec, .geo-dms, .coordinates, #coordinates, "
        ".reflist, .refbegin, ol.references, .mw-references-wrap, "
        ".mw-editsection, .noprint, .mwe-math-mathml-a11y, .mw-empty-elt, "
        "style, link, noscript"
    )

    _TARGET_ELEMENTS = [".mw-parser-output"]

    # prima wiki richiedeva un sacco di regex a valle perché facevamo uso troppo soft di excluded_selectors
    # ora rimosse perché ho aggiunto più excluded selectors (gabriele)

# ---------------------------------- REGEX ----------------------------------

    _RE_TERMINAL_SECTIONS = re.compile(
        r'^#{1,6}\s+(?:Notes|References|Bibliography|See also|Further reading'
        r'|External links|Categories|Career statistics|Honours|Honors)\s*$',
        re.MULTILINE,
    )

    _RE_IPA_LINK         = re.compile(r'\[\[([^\]]*)\]\]\([^)]*Help:IPA[^)]*\)')
    _RE_BRACKET_LINK     = re.compile(r'\[\[[^\]]*\]\]\([^)]*\)')

    # il md converter di crawl4ai cancella spazi aggressivamente su snippet di codice e prima dei link nel md
    _RE_BACKTICK_GLUE = re.compile(r'(`[^`\n]+`)(?=\w)')
    _RE_LINK_GLUE     = re.compile(r'(?<=[^\W_])(?=\[[^\]\n]+\]\([^)\n]*\))')

    _RE_MATH_IMG           = re.compile(r'!\[((?:[^\]]|\](?!\())*)\]\([^)]*math/render[^)]*\)')
    _RE_MATH_STYLE_WRAPPER = re.compile(
        r'^\{\\(?:display|text|script|scriptscript)style\s+(.*)\}$',
        re.DOTALL,
    )
    _RE_MATH_TOKEN         = re.compile(r'§§MATH§§(\d+)§§') # token opaco per espressioni latex
    _MATH_TOKEN_FORMAT     = '§§MATH§§{}§§'


    def __init__(self):
        super().__init__(
            excluded_selector="", # decompose con beautiful soup
            target_elements=self._TARGET_ELEMENTS,
        )

# ---------------------------------- METODI PUBBLICI ----------------------------------

    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        """Applica la pipeline di fetching-preprocessing-parsing wikipedia-specifica
        a partire dall'url o dall'html della pagina

        Args:
            url(str): url della pagina da scaricare
            raw_html(str | None): HTML sorgente opzionale

        Returns:
            istanza di ``ParsedDocument`` con ``url``, ``domain``, ``title``, ``html_text`` e ``parsed_text``

        Raises:
            CrawlError: se il fetch fallisce, se l'html grezzo non è disponibile dopo il fetch, o se il parsing va in errore per pagine malformate
        """

        try:
            if raw_html is None:
                # fetch neutro per ottenere html grezzo da dare a beautiful soup -> crawl4ai viene invocato senza excluded_selector
                # fatto perché prima crawl4ai mangiava il tail text di alcuni inline tipo .noprint (gabriele)
                raw_fetch = await self._fetch(url, raw_html=None)
                raw_html = raw_fetch.html
                final_url = getattr(raw_fetch, "url", None) or url
            else:
                final_url = url

            if raw_html is None:
                raise CrawlError(url=url, error_message="html grezzo non disponibile dopo il fetch")

            cleaned = self._preprocess_html(raw_html)
            result = await self._fetch(final_url, raw_html=cleaned)

            return ParsedDocument(
                url=final_url,
                domain=urlparse(final_url).netloc,
                title=self._extract_title(final_url),
                html_text=result.cleaned_html,
                parsed_text=self.normalize(result.markdown or ""),
            )
        except CrawlError:
            raise
        except Exception as err:
            raise CrawlError(url=url, error_message=f"parsing wiki fallito: {err}") from err
    

    def normalize(self, text: str) -> str:
        """Applica pipeline di pulizia wikipedia-specifica al testo markdown
        estratto da una pagina Wikipedia con crawl4ai

        include il taglio delle sezioni terminali, il ripristino degli spazi,
        la rimozione del markup residuo e la gestione delle formule matematiche

        Args:
            text(str): testo markdown grezzo generato da crawl4ai

        Returns:
            stringa di testo normalizzato
        """

        text = self._truncate_terminal_sections(text)
        text = self._unglue_whitespace(text)
        text = self._normalize_wiki_links(text)
        text, math_store = self._extract_math(text)
        text = remove_markup(text)
        text = normalize_whitespace(text)
        text = self._restore_math(text, math_store)
        return text.strip()
    
# ---------------------------------- HELPER PRIVATI ----------------------------------
    
    def _preprocess_html(self, raw_html: str) -> str:
        """Rimuove dall'html raw i selettori presenti in ``_EXCLUDED_SELECTORS``

        si usa beautifulsoup per decomporre i nodi corrispondenti ai selettori 
        esclusi per evitare perdite di testo nei nodi adiacenti (come accadeva con crawl4ai)

        Args:
            raw_html(str): HTML grezzo della pagina

        Returns:
            testo HTML pulito per la conversione in md
        """

        soup = BeautifulSoup(raw_html, "lxml")
        for el in soup.select(self._EXCLUDED_SELECTORS):
            el.decompose()
        return str(soup)
    

    def _unglue_whitespace(self, text: str) -> str:
        """Ripristina gli spazi divorati dal md converter di crawl4ai sugli snippet di codice e sui ref link
        
        Args:
            text(str): testo markdown con potenziali errori di spaziatura

        Returns:
            testo con spaziature ripristinate
        """

        text = self._RE_BACKTICK_GLUE.sub(r'\1 ', text)
        text = self._RE_LINK_GLUE.sub(' ', text)
        return text
    

    def _normalize_wiki_links(self, text: str) -> str:
        """Converte link IPA con alfabeto fonetico e cancella i bracket link del footnote

        Args:
            text(str): markdown con link IPA e bracket links

        Returns:
            markdown senza link IPA e bracket links
        """

        text = self._RE_IPA_LINK.sub(r'/\1/', text)
        text = self._RE_BRACKET_LINK.sub('', text)
        return text
    

    def _extract_math(self, text: str) -> tuple[str, list[str]]:
        """Estrae formule matematiche da immagini renderizzate da wiki

        * le formule vengono sostituite da token opachi ``§§MATH§§N§§`` in modo che la pipeline generica non le tocchi
        * latex viene ricostruito da ``_restore_math`` a valle di ``normalize_whitespace``
        * istruzioni di rendering tipo ``{\\displaystyle ...}`` vengono scartate

        Args:
            text(str): markdown contenente immagini ``![LATEX](...)``

        Returns:
            coppia (testo con token al posto delle formule, lista dei latex estratti)
        """

        store: list[str] = []

        def stash(m: re.Match) -> str:
            latex = html.unescape(m.group(1))
            latex = latex.replace('\\\\', '\\')
            unwrapped = self._RE_MATH_STYLE_WRAPPER.match(latex)
            if unwrapped:
                latex = unwrapped.group(1).strip()
            store.append(latex)
            return self._MATH_TOKEN_FORMAT.format(len(store) - 1)

        return self._RE_MATH_IMG.sub(stash, text), store


    def _restore_math(self, text: str, store: list[str]) -> str:
        """Sostituisce i token opachi ``§§MATH§§N§§`` con la relativa sintassi latex tra ``$...$``
        
        Args:
            text(str): testo normalizzato contenente token opachi
            store(list[str]): lista delle formule latex estratte da  ``_extract_math``

        Returns:
            testo finale con formule matematiche ripristinate
        """

        def replace(m: re.Match) -> str:
            idx = int(m.group(1))
            if idx >= len(store):
                return ''
            return f'${store[idx]}$'

        return self._RE_MATH_TOKEN.sub(replace, text)
    

    def _truncate_terminal_sections(self, text: str) -> str:
        """Taglia il testo alla prima sezione terminale (note, references, ...)
        
        le sezioni terminali a partire da cui viene troncato il testo sono definite in ``_RE_TERMINAL_SECTIONS``

        Args:
            text(str): testo informativo con sezioni terminali

        Returns:
            testo senza sezioni terminali
        """

        return self._RE_TERMINAL_SECTIONS.split(text, maxsplit=1)[0]
    

    def _extract_title(self, url: str) -> str:
        """Deduce il titolo della voce dall' URL di Wikipedia

        è possibile estrarre il titolo direttamente dall'URL perché wiki non ha URL opachi
        
        Example:
            >>> _extract_title("https://en.wikipedia.org/wiki/Terry_A._Davis")
            Terry A. Davis

        Args:
            url(str): URL completo della pagina

        Returns:
            il titolo della pagina formattato correttamente
        """

        path = urlparse(url).path
        if "/wiki/" in path:
            title = path.split("/wiki/", 1)[1]
        else:
            title = path.rstrip("/").rsplit("/", 1)[-1]
        return unquote(title).replace("_", " ")
