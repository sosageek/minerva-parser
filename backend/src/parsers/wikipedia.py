import html
import re
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class WikipediaParser(Parser):

    _EXCLUDED_SELECTORS = (
        ".mw-navigation, #mw-head, #mw-panel, .navbox, .sidebar, .toc, "
        ".hatnote, .ambox, .infobox, .shortdescription, .geo-dec, "
        ".thumb, .tright, .tleft, .mw-file-description, figcaption, "
        ".gallery, .categorytree, .geo-dms, .coordinates, #coordinates, "
        ".mw-editsection, .noprint, .mwe-math-mathml-a11y"
    )
    _TARGET_ELEMENTS = ["#mw-content-text"]

    # wikipedia ha un sacco di contenuto non semantico non rimuovibile con excluded selectors -> uso massiccio di regex
    # forse possiamo usare beautifulsoup per sfoltire il codice ma eviterei avere troppo bloat tra le dipendenze (gabriele)

    _RE_TERMINAL_SECTIONS = re.compile(
        r'^#{1,6}\s+(?:Notes|References|Bibliography|See also|Further reading'
        r'|External links|Categories|Career statistics|Honours|Honors|Awards'
        r'|Discography|Filmography|Selected works|Publications)\s*$',
        re.MULTILINE,
    )

    _RE_IPA_LINK         = re.compile(r'\[\[([^\]]*)\]\]\([^)]*Help:IPA[^)]*\)')
    _RE_BRACKET_LINK     = re.compile(r'\[\[[^\]]*\]\]\([^)]*\)')

    _RE_FOOTNOTE_REF     = re.compile(
        r'\[(?:'
        r'\d{1,3}'
        r'|[a-z]{1,3}'
        r'|[*\u2020\u2021\u00a7\u00b6]+'
        r'|(?:note|nb|n)\s+\d+'
        r'|citation\s+needed'
        r'|clarification\s+needed'
        r'|better\s+source\s+needed'
        r'|failed\s+verification'
        r'|original\s+research\??'
        r'|according\s+to\s+whom\??'
        r'|dubious(?:\s*[\u2013\u2014\-][^\]]*)?'
        r'|sic\??'
        r'|(?:who|when|where|why|which|what|how)\?'
        r')\](?!\()',
        re.IGNORECASE,
    )

    _RE_MATH_IMG           = re.compile(r'!\[((?:[^\]]|\](?!\())*)\]\([^)]*math/render[^)]*\)')
    _RE_MATH_STYLE_WRAPPER = re.compile(
        r'^\{\\(?:display|text|script|scriptscript)style\s+(.*)\}$',
        re.DOTALL,
    )
    _RE_MATH_TOKEN         = re.compile(r'§§MATH§§(\d+)§§') # token opaco per espressioni latex
    _MATH_TOKEN_FORMAT     = '§§MATH§§{}§§'

    _RE_URL_WITH_CAPTION = re.compile(r'\(https?://(?:[^\s)\\]|\\.)+\)(?=\S)\S*')
    _RE_URL_PAREN        = re.compile(r'\(https?://(?:[^\s)\\]|\\.)+\)')
    _RE_URL_BARE         = re.compile(r'https?://(?:[^\s)\\]|\\.)*[^\s)\\.,;:!?]')

    _RE_DISAMBIG         = re.compile(r'^Disambiguation\s*[–—-][^\n]*\n?', re.MULTILINE)
    _RE_COORDINATES      = re.compile(
        r'^.*(?:WikiMiniAtlas|\d+°\d+[′\']\d+[″"][NSEW]).*\n?',
        re.MULTILINE,
    )
    _RE_SYMBOL_ONLY_LINE = re.compile(r'^[\s\ufeff/;.\d°′″,NSEW-]+$', re.MULTILINE)
    _RE_TITLE_ATTR       = re.compile(r'\( "[^"]*"\)')

    def __init__(self):
        super().__init__(
            excluded_selector=self._EXCLUDED_SELECTORS,
            target_elements=self._TARGET_ELEMENTS,
        )

    async def parse(self, url: str) -> ParsedDocument:
        result = await self._fetch(url)
        final_url = getattr(result, "url", None) or url

        return ParsedDocument(
            url=final_url,
            domain=urlparse(final_url).netloc,
            title=self._extract_title(final_url),
            html_text=result.cleaned_html,
            parsed_text=self.normalize(result.markdown),
        )

    def normalize(self, text: str) -> str:
        text = self._truncate_terminal_sections(text)
        text = self._normalize_wiki_links(text)
        text = self._remove_footnote_refs(text)
        text, math_store = self._extract_math(text)
        text = remove_markup(text)
        text = self._remove_urls(text)
        text = self._remove_wiki_metadata(text)
        text = normalize_whitespace(text)
        text = self._restore_math(text, math_store)
        return text.strip()

    def _normalize_wiki_links(self, text: str) -> str:
        """Converte link IPA con alfabeto fonetico e cancella citazioni con doppie quadre"""
        text = self._RE_IPA_LINK.sub(r'/\1/', text)
        text = self._RE_BRACKET_LINK.sub('', text)
        return text

    def _remove_footnote_refs(self, text: str) -> str:
        """Cancella riferimenti alle note tra quadre"""
        return self._RE_FOOTNOTE_REF.sub('', text)

    def _extract_math(self, text: str) -> tuple[str, list[str]]:
        """Estrae formule matematiche da immagini renderizzate da wiki

        * le formule vengono sostituite da token opachi ``§§MATH§§N§§`` in modo che la pipeline generica non le tocchi
        * latex viene ricostruito da ``_restore_math`` a valle di ``normalize_whitespace``
        * istruzioni di rendering tipo ``{\\displaystyle ...}`` vengono scartate

        Args:
            text: markdown contenente immagini ``![LATEX](...)``

        Returns:
            coppia ``(testo con token al posto delle formule, lista dei LaTeX estratti)``
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
        """Ripristina i token delle formule con la relativa sintassi latex tra ``$...$``"""
        return self._RE_MATH_TOKEN.sub(lambda m: f'${store[int(m.group(1))]}$', text)

    def _remove_urls(self, text: str) -> str:
        """Cancella URL (anche tra parentesi con eventuali caption)"""
        text = self._RE_URL_WITH_CAPTION.sub('', text)
        text = self._RE_URL_PAREN.sub('', text)
        text = self._RE_URL_BARE.sub('', text)
        return text

    def _remove_wiki_metadata(self, text: str) -> str:
        """Cancella disambiguazione, coordinate, attributi title residui"""
        text = self._RE_DISAMBIG.sub('', text)
        text = self._RE_COORDINATES.sub('', text)
        text = self._RE_SYMBOL_ONLY_LINE.sub('', text)
        text = self._RE_TITLE_ATTR.sub('', text)
        return text

    def _truncate_terminal_sections(self, text: str) -> str:
        """Taglia il testo alla prima sezione terminale (note, references, ...)"""
        return self._RE_TERMINAL_SECTIONS.split(text, maxsplit=1)[0]

    def _extract_title(self, url: str) -> str:
        path = urlparse(url).path
        if "/wiki/" in path:
            title = path.split("/wiki/", 1)[1]
        else:
            title = path.rstrip("/").rsplit("/", 1)[-1]
        return unquote(title).replace("_", " ")
