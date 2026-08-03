import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from trafilatura import extract

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class ParsedHtml:
    title: str
    text: str
    links: tuple[str, ...]


class _PublicHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.hrefs: list[str] = []
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.text_parts.append(data)


def parse_public_html(body: bytes, base_url: str) -> ParsedHtml:
    parser = _PublicHtmlParser()
    html = body.decode("utf-8", errors="replace")
    parser.feed(html)
    title = (
        _clean(" ".join(parser.title_parts))[:200] or urlsplit(base_url).hostname or ""
    )
    focused = None
    if len(html) >= 200:
        focused = extract(
            html,
            url=base_url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            output_format="txt",
        )
    text = strip_contact_data(
        _clean(focused or " ".join(parser.text_parts))
    )
    links: list[str] = []
    for href in parser.hrefs:
        resolved = urljoin(base_url, href)
        parsed = urlsplit(resolved)
        if parsed.scheme == "https" and parsed.hostname and not parsed.fragment:
            links.append(resolved)
    return ParsedHtml(
        title=title,
        text=text[:100_000],
        links=tuple(dict.fromkeys(links)),
    )


def _clean(value: str) -> str:
    return _SPACE.sub(" ", value).strip()


def strip_contact_data(value: str) -> str:
    return _PHONE.sub("[contact removed]", _EMAIL.sub("[contact removed]", value))
